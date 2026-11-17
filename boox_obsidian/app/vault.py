"""Skriver til Obsidian vaulten.

Alt vi genererer ligger i blokke mellem to Obsidian kommentarer, saa det er skjult i laesevisning:

    %% boox:p12 order=0003 start %%
    ...indhold...
    %% boox:p12 end %%

Alt udenfor blokkene er dit eget og bliver aldrig roert. Hvis du selv har rettet i en blok,
overskrives den ikke.
"""
import json
import os
import re
import tempfile
from typing import Dict, List, Optional, Tuple

from .util import sha

_BLOCK = re.compile(
    r"%% boox:(?P<id>\w+) order=(?P<order>\d+) start %%\n(?P<body>.*?)\n?%% boox:(?P=id) end %%\n?",
    re.S,
)


def atomic_write(path: str, text: str) -> None:
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".boox_", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def write_bytes(path: str, data: bytes) -> None:
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".boox_", suffix=".tmp")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _marker(bid: str, order: int, body: str) -> str:
    return f"%% boox:{bid} order={order:04d} start %%\n{body}\n%% boox:{bid} end %%\n"


def sync_note(
    path: str,
    header: str,
    blocks: List[dict],
    stale: Optional[Dict[str, str]] = None,
) -> Dict[str, Tuple[str, Optional[str]]]:
    """Opdaterer blokke i en note.

    blocks: [{id, order, content, old_hash}] hvor old_hash er hashen af det vi skrev sidst.
    stale: {id: old_hash} for blokke der skal fjernes hvis de ikke er rettet af dig.
    Returnerer {id: (status, ny_hash)} med status created, updated, unchanged eller kept.
    """
    stale = stale or {}
    existed = os.path.exists(path)
    if existed:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    else:
        text = header

    items: List[list] = []
    pos = 0
    for m in _BLOCK.finditer(text):
        if m.start() > pos:
            items.append(["text", text[pos : m.start()]])
        items.append(["block", m.group("id"), int(m.group("order")), m.group("body")])
        pos = m.end()
    if pos < len(text):
        items.append(["text", text[pos:]])

    desired = {b["id"]: b for b in blocks}
    results: Dict[str, Tuple[str, Optional[str]]] = {}
    kept_items: List[list] = []
    placed = set()

    for item in items:
        if item[0] != "block":
            kept_items.append(item)
            continue
        _, bid, order, body = item
        current = body.strip("\n")
        if bid in desired:
            b = desired[bid]
            placed.add(bid)
            new = b["content"].strip("\n")
            old_hash = b.get("old_hash") or ""
            if current == new:
                results[bid] = ("unchanged", sha(new))
            elif old_hash and sha(current) != old_hash:
                results[bid] = ("kept", None)
            else:
                results[bid] = ("updated", sha(new))
                item[3] = new
            kept_items.append(item)
        elif bid in stale:
            if sha(current) == stale[bid]:
                continue
            kept_items.append(item)
        else:
            kept_items.append(item)

    for b in sorted((b for b in blocks if b["id"] not in placed), key=lambda b: b["order"]):
        new = b["content"].strip("\n")
        new_item = ["block", b["id"], b["order"], new]
        insert_at = None
        for i, it in enumerate(kept_items):
            if it[0] == "block" and it[2] > b["order"]:
                insert_at = i
                break
        if insert_at is None:
            last = max((i for i, it in enumerate(kept_items) if it[0] == "block"), default=None)
            insert_at = len(kept_items) if last is None else last + 1
        kept_items.insert(insert_at, new_item)
        results[b["id"]] = ("created", sha(new))

    out = ""
    for it in kept_items:
        if it[0] == "text":
            out += it[1]
        else:
            if out and not out.endswith("\n"):
                out += "\n"
            if out and not out.endswith("\n\n"):
                out += "\n"
            out += _marker(it[1], it[2], it[3].strip("\n"))

    if (not existed and (blocks or out.strip())) or (existed and out != text):
        if blocks or existed:
            atomic_write(path, out)
    return results


def render_page_block(page, embed_name: str = "") -> str:
    """Selve indholdet af en sides blok."""
    title = (page["title"] or "").strip()
    lines = [f"### Side {page['idx'] + 1}" + (f": {title}" if title else ""), ""]
    lines.append((page["text"] or "").strip() or "_Ingen tekst fundet._")
    uncertain = json.loads(page["uncertain"] or "[]")
    if uncertain:
        lines += ["", "> [!question] Usikre ord", "> " + ", ".join(uncertain)]
    tasks = json.loads(page["tasks"] or "[]")
    if tasks:
        lines += ["", "**Opgaver**", ""] + [f"* [ ] {t}" for t in tasks]
    raw = (page["raw"] or "").strip()
    if raw:
        lines += ["", "> [!quote]- Rå transskription"] + ["> " + ln for ln in raw.splitlines()]
    if embed_name:
        lines += ["", "> [!example]- Original side", f"> ![[{embed_name}]]"]
    return "\n".join(lines)
