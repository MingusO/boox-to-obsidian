import hashlib
import json
import logging
import os
import re
from datetime import date as date_cls
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional
from zoneinfo import ZoneInfo

from . import pdfpages, vault
from .claude import ClaudeError
from .config import Config, Notebook
from .state import State
from .util import block_id, format_date, format_folder, parse_iso, safe_name, sha, utc_iso

log = logging.getLogger("pipeline")

MAX_SUMMARIES_PER_RUN = 10


def _file_sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Pipeline:
    def __init__(
        self,
        cfg: Config,
        state: State,
        claude,
        fetch: Callable[[Notebook], Optional[str]],
        notifier,
        obsidian,
        now_fn: Optional[Callable[[], datetime]] = None,
    ):
        self.cfg = cfg
        self.state = state
        self.claude = claude
        self.fetch = fetch
        self.notifier = notifier
        self.obsidian = obsidian
        self.tz = ZoneInfo(cfg.timezone)
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.changed = False

    # Hovedloeb ---------------------------------------------------------

    def run_cycle(self) -> Dict[str, int]:
        self.changed = False
        now = self.now_fn()
        self.obsidian.sync()
        budget = {"pages": self.cfg.max_pages_per_run, "summaries": MAX_SUMMARIES_PER_RUN}
        report: Dict[str, int] = {}
        for nb in self.cfg.notebooks:
            try:
                self._notebook(nb, now, budget, report)
            except Exception as e:
                log.error("Fejl i notesbogen %s: %s", nb.name, e, exc_info=not _is_api_error(e))
        try:
            self._summaries(now, budget)
        except Exception as e:
            log.error("Fejl ved opsummering: %s", e, exc_info=not _is_api_error(e))
        if self.changed:
            self.obsidian.sync()
        if report:
            parts = ", ".join(f"{n} {count}" for n, count in report.items())
            self.notifier.send("Boox noter", f"Nye sider laest: {parts}")
        return report

    # Notesbog ----------------------------------------------------------

    def _notebook(self, nb: Notebook, now: datetime, budget: dict, report: dict) -> None:
        path = self.fetch(nb)
        if not path or not os.path.exists(path):
            return
        digest = _file_sha(path)
        key = f"filehash:{nb.name}"
        if self.state.get_meta(key) != digest:
            infos = pdfpages.analyze(path)
            first_run = self.state.get_meta(f"init:{nb.name}") is None
            self.reconcile(nb, infos, now, skip_new=first_run and not self.cfg.import_existing)
            self.state.set_meta(f"init:{nb.name}", "1")
            self.state.set_meta(key, digest)
        if self.cfg.import_existing:
            self.state.activate_skipped(nb.name, utc_iso(now))
        cutoff = utc_iso(now - timedelta(minutes=self.cfg.settle_minutes))
        for row in self.state.pending_ready(nb.name, cutoff):
            if budget["pages"] <= 0:
                log.info("Graensen for sider pr. koersel er naaet, resten tages i naeste runde")
                break
            self._process(nb, row, path, now)
            budget["pages"] -= 1
            report[nb.name] = report.get(nb.name, 0) + 1

    def reconcile(self, nb: Notebook, infos, now: datetime, skip_new: bool = False) -> None:
        """Sammenholder PDF'ens sider med det vi kender.

        Samme indhold paa en ny plads er den samme side. En side der har faaet nyt indhold paa
        samme plads er en redigering. Alt andet er nyt eller fjernet.
        """
        now_iso = utc_iso(now)
        occurrences: Dict[str, int] = {}
        keys = []
        for info in infos:
            n = occurrences.get(info.hash, 0)
            occurrences[info.hash] = n + 1
            keys.append(f"{info.hash}:{n}")
        existing = self.state.active_pages(nb.name)
        by_key = {r["pkey"]: r for r in existing}
        key_set = set(keys)
        orphans = {r["idx"]: r for r in existing if r["pkey"] not in key_set}

        for i, (info, key) in enumerate(zip(infos, keys)):
            if key in by_key:
                row = by_key[key]
                if row["idx"] != i:
                    self.state.update(row["id"], idx=i)
            elif i in orphans:
                row = orphans.pop(i)
                if info.blank:
                    self.state.update(row["id"], pkey=key, idx=i, status="done", blank=1, text="", raw="")
                else:
                    self.state.update(
                        row["id"], pkey=key, idx=i, status="pending", blank=0, stable_since=utc_iso(now)
                    )
            else:
                status = "done" if info.blank else ("skipped" if skip_new else "pending")
                self.state.add_page(nb.name, i, key, status, now_iso, blank=info.blank)

        for row in orphans.values():
            self.state.update(row["id"], status="removed")
            self._delete_attachment(nb, row["pdf_name"])
            if row["date"]:
                self._render_note(nb, row["date"])
                self.changed = True

    # Behandling af en side ---------------------------------------------

    def _process(self, nb: Notebook, row, path: str, now: datetime) -> None:
        data = pdfpages.page_pdf(path, row["idx"])
        today_local = now.astimezone(self.tz).date()
        result = self.claude.transcribe(data, nb.name, nb.hint, today_local.isoformat())

        first_seen_local = parse_iso(row["first_seen"]).astimezone(self.tz).date().isoformat()
        page_date = self._valid_date(result.get("date"), today_local) or row["date"] or first_seen_local

        text = (result.get("corrected_text") or "").strip()
        blank = bool(result.get("is_blank")) or not text

        pdf_name = ""
        if not blank:
            pdf_name = f"{safe_name(nb.name)}_{row['id']}_{row['pkey'][:8]}.pdf"
            target = os.path.join(self.cfg.vault_path, self.cfg.attachments_folder, safe_name(nb.name), pdf_name)
            vault.write_bytes(target, data)
        if row["pdf_name"] and row["pdf_name"] != pdf_name:
            self._delete_attachment(nb, row["pdf_name"])

        old_date = row["date"]
        self.state.update(
            row["id"],
            status="done",
            date=page_date,
            title=(result.get("title") or "").strip(),
            text=text,
            raw=(result.get("raw_text") or "").strip(),
            uncertain=result.get("uncertain_words") or [],
            tasks=result.get("tasks") or [],
            pdf_name=pdf_name,
            blank=1 if blank else 0,
        )
        if old_date and old_date != page_date:
            self._render_note(nb, old_date)
        self._render_note(nb, page_date)
        self.changed = True
        log.info("Side %s i %s laest (%s)", row["idx"] + 1, nb.name, page_date)

    def _valid_date(self, value, today: date_cls) -> Optional[str]:
        if not value:
            return None
        try:
            d = date_cls.fromisoformat(str(value).strip())
        except ValueError:
            return None
        if d.year < 2000 or d > today + timedelta(days=1):
            return None
        return d.isoformat()

    def _delete_attachment(self, nb: Notebook, pdf_name: str) -> None:
        if not pdf_name:
            return
        p = os.path.join(self.cfg.vault_path, self.cfg.attachments_folder, safe_name(nb.name), pdf_name)
        try:
            os.remove(p)
        except FileNotFoundError:
            pass

    # Noter i vaulten ---------------------------------------------------

    def _note_basename(self, nb: Notebook, date: str) -> str:
        return f"{safe_name(nb.name)} {date}"

    def _note_path(self, nb: Notebook, date: str) -> str:
        return os.path.join(
            self.cfg.vault_path,
            self.cfg.notes_folder,
            safe_name(nb.category),
            safe_name(nb.name),
            self._note_basename(nb, date) + ".md",
        )

    def _render_note(self, nb: Notebook, date: str) -> None:
        rows = self.state.pages_for_date(nb.name, date)
        desired = {f"p{r['id']}" for r in rows}
        blocks = [
            {
                "id": f"p{r['id']}",
                "order": r["idx"],
                "content": vault.render_page_block(r, r["pdf_name"]),
                "old_hash": r["rendered_hash"],
            }
            for r in rows
        ]
        stale = {
            f"p{r['id']}": r["rendered_hash"]
            for r in self.state.rendered_pages(nb.name)
            if f"p{r['id']}" not in desired
        }
        header = (
            "---\n"
            f"notebook: {nb.name}\n"
            f"category: {nb.category}\n"
            f"date: {date}\n"
            "tags: [boox]\n"
            "kilde: Boox Note Air 5C\n"
            "---\n\n"
            f"# {nb.name} {date}\n\n"
            "Blokke mellem %% markoererne opdateres automatisk. Skriv dine egne noter udenfor dem.\n\n"
        )
        results = vault.sync_note(self._note_path(nb, date), header, blocks, stale)
        for r in rows:
            status, new_hash = results.get(f"p{r['id']}", (None, None))
            if status in ("created", "updated", "unchanged"):
                self.state.update(r["id"], rendered_hash=new_hash)
            elif status == "kept":
                log.warning("Du har rettet side %s i %s, saa den er ikke overskrevet", r["idx"] + 1, nb.name)
        for r in self.state.rendered_pages(nb.name):
            if f"p{r['id']}" not in desired and r["date"] == date and (r["status"] == "removed" or r["blank"]):
                self.state.update(r["id"], rendered_hash="")

    # Daglig opsummering ------------------------------------------------

    def _summaries(self, now: datetime, budget: dict) -> None:
        local = now.astimezone(self.tz)
        today = local.date().isoformat()
        for nb in self.cfg.notebooks:
            for d in self.state.dates_with_pages(nb.name):
                if d > today or (d == today and local.hour < self.cfg.summary_hour):
                    continue
                rows = self.state.pages_for_date(nb.name, d)
                if not rows:
                    continue
                input_hash = sha(json.dumps([[r["id"], r["text"]] for r in rows], ensure_ascii=False))
                existing = self.state.get_summary(nb.name, d)
                if existing and existing["input_hash"] == input_hash:
                    continue
                if budget["summaries"] <= 0:
                    return
                pages = [{"idx": r["idx"], "title": r["title"], "text": r["text"]} for r in rows]
                text = self.claude.summarize(nb.name, d, pages, nb.hint)
                self.state.set_summary(nb.name, d, input_hash, text)
                self._write_daily(nb, d, text)
                budget["summaries"] -= 1
                self.changed = True

    def _daily_path(self, date: str) -> str:
        d = date_cls.fromisoformat(date)
        return os.path.join(
            self.cfg.vault_path,
            format_folder(self.cfg.daily_folder, d),
            format_date(self.cfg.daily_format, d) + ".md",
        )

    def _daily_header(self, date: str) -> str:
        tpl = self.cfg.daily_template
        if not tpl:
            return ""
        p = os.path.join(self.cfg.vault_path, tpl)
        if not os.path.exists(p):
            return ""
        with open(p, encoding="utf-8") as f:
            text = f.read()
        d = date_cls.fromisoformat(date)
        text = re.sub(r"\{\{(?:date|title)(?::([^}]+))?\}\}", lambda m: format_date(m.group(1) or "YYYY-MM-DD", d), text)
        return text.rstrip("\n") + "\n\n"

    def _write_daily(self, nb: Notebook, date: str, summary: str) -> None:
        bid = "day_" + block_id(nb.name)
        content = f"### Boox: {nb.name}\n\n{summary}\n\nSe [[{self._note_basename(nb, date)}]]"
        existing = self.state.get_summary(nb.name, date)
        old_hash = existing["rendered_hash"] if existing else ""
        results = vault.sync_note(
            self._daily_path(date),
            self._daily_header(date),
            [{"id": bid, "order": 0, "content": content, "old_hash": old_hash}],
        )
        status, new_hash = results.get(bid, (None, None))
        if status in ("created", "updated", "unchanged"):
            self.state.set_summary_rendered(nb.name, date, new_hash)
        elif status == "kept":
            log.warning("Du har rettet Boox sektionen i daglig note for %s, saa den er ikke overskrevet", date)


def _is_api_error(e: Exception) -> bool:
    return isinstance(e, ClaudeError)
