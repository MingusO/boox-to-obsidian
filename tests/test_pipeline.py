import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "boox_obsidian"))

from app import pdfpages, vault  # noqa: E402
from app.config import Config, Notebook  # noqa: E402
from app.pipeline import Pipeline  # noqa: E402
from app.state import State  # noqa: E402
from app.notify import NullNotifier  # noqa: E402
from app.obsidian_sync import NullSync  # noqa: E402


def make_pdf(path, texts):
    w = PdfWriter()
    for t in texts:
        page = w.add_blank_page(width=200, height=200)
        if t:
            s = DecodedStreamObject()
            s.set_data(f"BT /F1 12 Tf 10 100 Td ({t}) Tj ET 0 0 m 100 100 l 50 80 l S".encode())
            page[NameObject("/Contents")] = w._add_object(s)
    with open(path, "wb") as f:
        w.write(f)


class FakeClaude:
    def __init__(self):
        self.calls = 0
        self.summaries = 0
        self.date = ""

    def transcribe(self, pdf_bytes, notebook, hint, today):
        self.calls += 1
        return {
            "is_blank": False,
            "date": self.date,
            "title": f"Titel {self.calls}",
            "raw_text": f"raa {self.calls}",
            "corrected_text": f"Rettet tekst {self.calls}",
            "uncertain_words": ["ord"],
            "tasks": ["Aflever opgave"],
        }

    def summarize(self, notebook, date, pages, hint):
        self.summaries += 1
        return f"Opsummering {self.summaries} med {len(pages)} sider"


@pytest.fixture
def env(tmp_path):
    vault_dir = tmp_path / "vault"
    cfg = Config(
        vault_path=str(vault_dir),
        data_dir=str(tmp_path / "data"),
        settle_minutes=30,
        import_existing=True,
        summary_hour=21,
        timezone="Europe/Copenhagen",
        notebooks=[Notebook("Kompan", "x/Kompan.pdf", "Kursus")],
    )
    pdf = tmp_path / "Kompan.pdf"
    clock = {"now": datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)}
    claude = FakeClaude()
    pipe = Pipeline(
        cfg, State(":memory:"), claude, lambda nb: str(pdf), NullNotifier(), NullSync(), lambda: clock["now"]
    )
    return pipe, claude, pdf, clock, vault_dir


def test_hash_is_stable_and_blank_detected(tmp_path):
    p = tmp_path / "a.pdf"
    make_pdf(str(p), ["hej", "", "hej"])
    infos = pdfpages.analyze(str(p))
    assert infos[0].hash == infos[2].hash
    assert infos[0].hash != infos[1].hash
    assert infos[1].blank and not infos[0].blank
    assert pdfpages.page_pdf(str(p), 0).startswith(b"%PDF")


def test_settle_then_process_and_files_written(env):
    pipe, claude, pdf, clock, vault_dir = env
    make_pdf(str(pdf), ["side et", "side to"])
    pipe.run_cycle()
    assert claude.calls == 0  # endnu ikke stabil
    clock["now"] += timedelta(minutes=31)
    report = pipe.run_cycle()
    assert report == {"Kompan": 2}
    note = vault_dir / "Noter" / "Kursus" / "Kompan" / "Kompan 2026-11-17.md"
    text = note.read_text()
    assert "Rettet tekst 1" in text and "Rettet tekst 2" in text
    assert text.index("Rettet tekst 1") < text.index("Rettet tekst 2")
    assert "[[Kompan_1_" in text
    assert len(list((vault_dir / "Noter" / "Bilag" / "Kompan").glob("*.pdf"))) == 2


def test_unchanged_pages_not_reprocessed_after_insert(env):
    pipe, claude, pdf, clock, _ = env
    make_pdf(str(pdf), ["a", "b"])
    pipe.run_cycle()
    clock["now"] += timedelta(minutes=31)
    pipe.run_cycle()
    assert claude.calls == 2
    make_pdf(str(pdf), ["ny", "a", "b"])  # en side indsat foerst
    clock["now"] += timedelta(minutes=1)
    pipe.run_cycle()
    clock["now"] += timedelta(minutes=31)
    pipe.run_cycle()
    assert claude.calls == 3  # kun den nye side


def test_edited_page_replaces_instead_of_duplicates(env):
    pipe, claude, pdf, clock, vault_dir = env
    make_pdf(str(pdf), ["a", "b"])
    pipe.run_cycle()
    clock["now"] += timedelta(minutes=31)
    pipe.run_cycle()
    make_pdf(str(pdf), ["a", "b rettet"])
    clock["now"] += timedelta(minutes=1)
    pipe.run_cycle()
    clock["now"] += timedelta(minutes=31)
    pipe.run_cycle()
    text = (vault_dir / "Noter" / "Kursus" / "Kompan" / "Kompan 2026-11-17.md").read_text()
    assert text.count("### Side 2") == 1
    assert "Rettet tekst 3" in text and "Rettet tekst 2" not in text


def test_removed_page_leaves_note(env):
    pipe, claude, pdf, clock, vault_dir = env
    make_pdf(str(pdf), ["a", "b"])
    pipe.run_cycle()
    clock["now"] += timedelta(minutes=31)
    pipe.run_cycle()
    make_pdf(str(pdf), ["a"])
    clock["now"] += timedelta(minutes=1)
    pipe.run_cycle()
    text = (vault_dir / "Noter" / "Kursus" / "Kompan" / "Kompan 2026-11-17.md").read_text()
    assert "Rettet tekst 2" not in text and "Rettet tekst 1" in text


def test_page_date_from_handwriting(env):
    pipe, claude, pdf, clock, vault_dir = env
    claude.date = "2026-11-10"
    make_pdf(str(pdf), ["a"])
    pipe.run_cycle()
    clock["now"] += timedelta(minutes=31)
    pipe.run_cycle()
    assert (vault_dir / "Noter" / "Kursus" / "Kompan" / "Kompan 2026-11-10.md").exists()


def test_user_edit_is_not_overwritten(env):
    pipe, claude, pdf, clock, vault_dir = env
    make_pdf(str(pdf), ["a"])
    pipe.run_cycle()
    clock["now"] += timedelta(minutes=31)
    pipe.run_cycle()
    note = vault_dir / "Noter" / "Kursus" / "Kompan" / "Kompan 2026-11-17.md"
    note.write_text(note.read_text().replace("Rettet tekst 1", "Min egen rettelse"))
    make_pdf(str(pdf), ["a aendret"])
    clock["now"] += timedelta(minutes=1)
    pipe.run_cycle()
    clock["now"] += timedelta(minutes=31)
    pipe.run_cycle()
    assert "Min egen rettelse" in note.read_text()


def test_daily_summary_after_summary_hour_only(env):
    pipe, claude, pdf, clock, vault_dir = env
    make_pdf(str(pdf), ["a", "b"])
    pipe.run_cycle()
    clock["now"] += timedelta(minutes=31)
    pipe.run_cycle()
    daily = vault_dir / "Daily" / "2026-11-17.md"
    assert not daily.exists()  # klokken er kun 11 dansk tid
    clock["now"] = datetime(2026, 11, 17, 21, 30, tzinfo=timezone.utc)  # 22:30 dansk tid
    pipe.run_cycle()
    text = daily.read_text()
    assert "Opsummering 1 med 2 sider" in text and "[[Kompan 2026-11-17]]" in text
    pipe.run_cycle()
    assert claude.summaries == 1  # ingen ny opsummering uden aendringer


def test_daily_note_keeps_existing_user_text(env):
    pipe, claude, pdf, clock, vault_dir = env
    daily = vault_dir / "Daily" / "2026-11-17.md"
    daily.parent.mkdir(parents=True)
    daily.write_text("# Min dag\n\nVigtigt privat indhold\n")
    make_pdf(str(pdf), ["a"])
    pipe.run_cycle()
    clock["now"] = datetime(2026, 11, 17, 21, 30, tzinfo=timezone.utc)
    pipe.run_cycle()
    text = daily.read_text()
    assert text.startswith("# Min dag\n\nVigtigt privat indhold\n")
    assert "Opsummering" in text


def test_sync_note_is_idempotent_and_ordered(tmp_path):
    p = str(tmp_path / "n.md")
    mk = lambda i, c, h="": {"id": f"p{i}", "order": i, "content": c, "old_hash": h}
    r = vault.sync_note(p, "# Titel\n\n", [mk(2, "to"), mk(1, "et")])
    assert r["p1"][0] == "created"
    first = open(p).read()
    assert first.index("et") < first.index("to")
    again = vault.sync_note(p, "# Titel\n\n", [mk(2, "to", r["p2"][1]), mk(1, "et", r["p1"][1])])
    assert {v[0] for v in again.values()} == {"unchanged"}
    assert open(p).read() == first
    inserted = vault.sync_note(p, "", [mk(1, "et", r["p1"][1]), mk(2, "to", r["p2"][1]), mk(3, "tre")])
    assert inserted["p3"][0] == "created"
    assert open(p).read().rstrip().endswith("%% boox:p3 end %%")


def test_existing_pages_skipped_until_import_enabled(env):
    pipe, claude, pdf, clock, _ = env
    pipe.cfg.import_existing = False
    make_pdf(str(pdf), ["gammel a", "gammel b"])
    pipe.run_cycle()
    clock["now"] += timedelta(minutes=31)
    pipe.run_cycle()
    assert claude.calls == 0
    make_pdf(str(pdf), ["gammel a", "gammel b", "ny side"])
    clock["now"] += timedelta(minutes=1)
    pipe.run_cycle()
    clock["now"] += timedelta(minutes=31)
    pipe.run_cycle()
    assert claude.calls == 1
    pipe.cfg.import_existing = True
    pipe.run_cycle()
    clock["now"] += timedelta(minutes=31)
    pipe.run_cycle()
    assert claude.calls == 3


def test_danish_daily_format_and_nested_folder(env):
    from datetime import date
    from app.util import format_date, format_folder

    assert format_date("D. MMMM YYYY dddd", date(2026, 9, 4)) == "4. september 2026 fredag"
    assert format_date("D. MMMM YYYY dddd", date(2026, 9, 5)) == "5. september 2026 lørdag"
    assert format_date("YYYY-MM-DD", date(2026, 9, 4)) == "2026-09-04"
    assert format_folder("01 PRIVATE/Dagbog/YYYY/MM", date(2026, 9, 4)) == "01 PRIVATE/Dagbog/2026/09"

    pipe, claude, pdf, clock, vault_dir = env
    pipe.cfg.daily_folder = "01 PRIVATE/Dagbog/YYYY/MM"
    pipe.cfg.daily_format = "D. MMMM YYYY dddd"
    make_pdf(str(pdf), ["a"])
    pipe.run_cycle()
    clock["now"] = datetime(2026, 11, 17, 21, 30, tzinfo=timezone.utc)
    pipe.run_cycle()
    expected = vault_dir / "01 PRIVATE" / "Dagbog" / "2026" / "11" / "17. november 2026 tirsdag.md"
    assert expected.exists()
