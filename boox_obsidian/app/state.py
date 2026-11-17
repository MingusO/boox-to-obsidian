import json
import os
import sqlite3
from typing import List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  notebook TEXT NOT NULL,
  idx INTEGER NOT NULL,
  pkey TEXT NOT NULL,
  status TEXT NOT NULL,
  first_seen TEXT NOT NULL,
  stable_since TEXT NOT NULL,
  date TEXT,
  title TEXT DEFAULT '',
  text TEXT DEFAULT '',
  raw TEXT DEFAULT '',
  uncertain TEXT DEFAULT '[]',
  tasks TEXT DEFAULT '[]',
  pdf_name TEXT DEFAULT '',
  rendered_hash TEXT DEFAULT '',
  blank INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS pages_nb ON pages(notebook, status);
CREATE TABLE IF NOT EXISTS summaries(
  notebook TEXT NOT NULL,
  date TEXT NOT NULL,
  input_hash TEXT NOT NULL,
  text TEXT NOT NULL,
  rendered_hash TEXT DEFAULT '',
  PRIMARY KEY(notebook, date)
);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""


class State:
    def __init__(self, path: str):
        if path != ":memory:":
            os.makedirs(os.path.dirname(path), exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    def get_meta(self, key: str) -> Optional[str]:
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (key, value))
        self.db.commit()

    def active_pages(self, notebook: str) -> List[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM pages WHERE notebook=? AND status!='removed' ORDER BY idx", (notebook,)
        ).fetchall()

    def add_page(self, notebook, idx, pkey, status, now_iso, blank=False) -> int:
        cur = self.db.execute(
            "INSERT INTO pages(notebook,idx,pkey,status,first_seen,stable_since,blank) VALUES(?,?,?,?,?,?,?)",
            (notebook, idx, pkey, status, now_iso, now_iso, 1 if blank else 0),
        )
        self.db.commit()
        return cur.lastrowid

    def update(self, page_id: int, **fields) -> None:
        for k, v in list(fields.items()):
            if isinstance(v, (list, dict)):
                fields[k] = json.dumps(v, ensure_ascii=False)
        cols = ", ".join(f"{k}=?" for k in fields)
        self.db.execute(f"UPDATE pages SET {cols} WHERE id=?", (*fields.values(), page_id))
        self.db.commit()

    def get(self, page_id: int) -> sqlite3.Row:
        return self.db.execute("SELECT * FROM pages WHERE id=?", (page_id,)).fetchone()

    def activate_skipped(self, notebook: str, now_iso: str) -> int:
        cur = self.db.execute(
            "UPDATE pages SET status='pending', stable_since=? WHERE notebook=? AND status='skipped'",
            (now_iso, notebook),
        )
        self.db.commit()
        return cur.rowcount

    def pending_ready(self, notebook: str, stable_before_iso: str) -> List[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM pages WHERE notebook=? AND status='pending' AND stable_since<=? ORDER BY idx",
            (notebook, stable_before_iso),
        ).fetchall()

    def pages_for_date(self, notebook: str, date: str) -> List[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM pages WHERE notebook=? AND status='done' AND blank=0 AND date=? ORDER BY idx",
            (notebook, date),
        ).fetchall()

    def rendered_pages(self, notebook: str) -> List[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM pages WHERE notebook=? AND rendered_hash!=''", (notebook,)
        ).fetchall()

    def dates_with_pages(self, notebook: str) -> List[str]:
        rows = self.db.execute(
            "SELECT DISTINCT date FROM pages WHERE notebook=? AND status='done' AND blank=0 AND date IS NOT NULL ORDER BY date",
            (notebook,),
        ).fetchall()
        return [r["date"] for r in rows]

    def get_summary(self, notebook: str, date: str) -> Optional[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM summaries WHERE notebook=? AND date=?", (notebook, date)
        ).fetchone()

    def set_summary(self, notebook, date, input_hash, text, rendered_hash=None) -> None:
        old = self.get_summary(notebook, date)
        rh = rendered_hash if rendered_hash is not None else (old["rendered_hash"] if old else "")
        self.db.execute(
            "INSERT OR REPLACE INTO summaries(notebook,date,input_hash,text,rendered_hash) VALUES(?,?,?,?,?)",
            (notebook, date, input_hash, text, rh),
        )
        self.db.commit()

    def set_summary_rendered(self, notebook: str, date: str, rendered_hash: str) -> None:
        self.db.execute(
            "UPDATE summaries SET rendered_hash=? WHERE notebook=? AND date=?",
            (rendered_hash, notebook, date),
        )
        self.db.commit()
