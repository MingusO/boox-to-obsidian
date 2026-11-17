"""Splitter en notesbog PDF i sider uden at rendere dem.

Siderne identificeres med en hash af indholdet, saa kun nye eller aendrede sider
bliver sendt til AI. Kun pypdf bruges (ren Python, virker paa ARM).
"""
import hashlib
import io
from dataclasses import dataclass
from typing import List, Tuple

from pypdf import PdfReader, PdfWriter


@dataclass
class PageInfo:
    idx: int
    hash: str
    blank: bool


def _hash_xobjects(res, h, depth: int) -> int:
    if res is None or depth > 2:
        return 0
    try:
        res = res.get_object()
        xo = res.get("/XObject")
        if xo is None:
            return 0
        xo = xo.get_object()
    except Exception:
        return 0
    count = 0
    for name in sorted(xo.keys()):
        try:
            obj = xo[name].get_object()
            try:
                data = obj.get_data()
            except Exception:
                data = getattr(obj, "_data", b"") or b""
            h.update(str(name).encode())
            h.update(data)
            count += 1
            if obj.get("/Subtype") == "/Form":
                count += _hash_xobjects(obj.get("/Resources"), h, depth + 1)
        except Exception:
            continue
    return count


def _digest(page) -> Tuple[str, bool]:
    h = hashlib.sha256()
    size = 0
    try:
        contents = page.get_contents()
        if contents is not None:
            data = contents.get_data()
            h.update(data)
            size = len(data)
    except Exception:
        pass
    xcount = _hash_xobjects(page.get("/Resources"), h, 0)
    try:
        box = page.mediabox
        h.update(f"{float(box.width):.1f}x{float(box.height):.1f}".encode())
    except Exception:
        pass
    return h.hexdigest(), (size < 40 and xcount == 0)


def analyze(path: str) -> List[PageInfo]:
    reader = PdfReader(path)
    infos = []
    for i, page in enumerate(reader.pages):
        digest, blank = _digest(page)
        infos.append(PageInfo(i, digest, blank))
    return infos


def page_pdf(path: str, idx: int) -> bytes:
    """Returnerer en enkelt side som en selvstaendig PDF."""
    reader = PdfReader(path)
    writer = PdfWriter()
    writer.add_page(reader.pages[idx])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
