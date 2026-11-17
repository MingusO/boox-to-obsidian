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


MONTHS_DA = ["januar", "februar", "marts", "april", "maj", "juni", "juli", "august",
             "september", "oktober", "november", "december"]
WEEKDAYS_DA = ["mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag"]
_TOKENS = re.compile(r"YYYY|MMMM|MM|M|dddd|DD|D")


def format_date(fmt: str, d: date) -> str:
    """Datoformat i Obsidian stil med danske navne.

    Understoettede dele: YYYY, MMMM (september), MM (09), M (9), dddd (fredag), DD (04), D (4).
    Eksempel: "D. MMMM YYYY dddd" giver "4. september 2026 fredag".
    """
    values = {
        "YYYY": f"{d.year:04d}",
        "MMMM": MONTHS_DA[d.month - 1],
        "MM": f"{d.month:02d}",
        "M": str(d.month),
        "dddd": WEEKDAYS_DA[d.weekday()],
        "DD": f"{d.day:02d}",
        "D": str(d.day),
    }
    return _TOKENS.sub(lambda m: values[m.group(0)], fmt)


def format_folder(fmt: str, d: date) -> str:
    """Til mappestier. Kun YYYY og MM erstattes, saa mappenavne som Dagbog ikke rammes."""
    return fmt.replace("YYYY", f"{d.year:04d}").replace("MM", f"{d.month:02d}")


def utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def parse_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
