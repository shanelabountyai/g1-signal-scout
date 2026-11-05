"""SQLite seen_items. Rows are written only after the digest write succeeds (CLAUDE.md rule)."""
import sqlite3
from pathlib import Path

from .items import ROOT, Item

DEFAULT_DB = ROOT / "data" / "scout.db"


def connect(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS seen_items (url TEXT PRIMARY KEY, title TEXT, seen_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    return db


def unseen(db: sqlite3.Connection, items: list[Item]) -> list[Item]:
    seen = {r[0] for r in db.execute("SELECT url FROM seen_items")}
    return [i for i in items if i.url not in seen]


def mark_seen(db: sqlite3.Connection, items: list[Item]) -> None:
    db.executemany("INSERT OR IGNORE INTO seen_items (url, title) VALUES (?, ?)", [(i.url, i.title) for i in items])
    db.commit()
