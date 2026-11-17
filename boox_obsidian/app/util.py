import hashlib
import re
from datetime import date, datetime, timezone

_BAD = re.compile(r'[\\/:*?"<>|#^\[\]]')


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_name(name: str) -> str:
    """Goer en tekst brugbar som fil eller mappenavn i en Obsidian vault."""
    cleaned = re.sub(r"\s+", " ", _BAD.sub(" ", name)).strip()
    return cleaned or "Ukendt"


def block_id(name: str) -> str:
    return re.sub(r"\W", "_", name)


def format_date(fmt: str, d: date) -> str:
    """Understoetter tokens YYYY, MM og DD."""
    return fmt.replace("YYYY", f"{d.year:04d}").replace("MM", f"{d.month:02d}").replace("DD", f"{d.day:02d}")


def utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def parse_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
