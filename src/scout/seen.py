"""seen_items in SQLite (C4, D-26). Same columns as G1·B's Data Table: url, title, source, seen_at.

The only writer is `mark_seen`, and the pipeline calls it only after the sink
write succeeded. Nothing here deletes.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from scout.models import Item

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_items (
    url TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    run_id TEXT
);
"""


class SeenStore:
    def __init__(self, path: str) -> None:
        self.path = path
        if path != ":memory:":
            Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(Path(path).expanduser()) if path != ":memory:" else path)
        self.conn.executescript(SCHEMA)

    def urls(self) -> set[str]:
        return {r[0] for r in self.conn.execute("SELECT url FROM seen_items")}

    def count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM seen_items").fetchone()[0])

    def drop_seen(self, items: list[Item]) -> list[Item]:
        seen = self.urls()
        return [it for it in items if it.url not in seen]

    def mark_seen(self, items: list[Item], run_id: str, at: datetime | None = None) -> int:
        """Insert every item (ignore an already-seen URL). Returns the number of new rows."""
        ts = (at or datetime.now(UTC)).isoformat()
        before = self.count()
        with self.conn:
            self.conn.executemany(
                "INSERT OR IGNORE INTO seen_items (url, title, source, seen_at, run_id) VALUES (?,?,?,?,?)",
                [(it.url, it.title, it.source, ts, run_id) for it in items],
            )
        return self.count() - before

    def close(self) -> None:
        self.conn.close()
