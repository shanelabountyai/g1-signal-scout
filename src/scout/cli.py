import argparse
from pathlib import Path

from . import db as seen_db
from .items import FRESH_DAYS, load_feeds, load_fixtures, normalize


def main() -> None:
    ap = argparse.ArgumentParser(prog="scout")
    ap.add_argument("--dry-run", action="store_true", help="fixtures, no model call, nothing written")
    ap.add_argument("--fresh-days", type=int, help=f"freshness window (live default {FRESH_DAYS}; dry-run default none, fixtures are old)")
    ap.add_argument("--db", help="SQLite path (default data/scout.db)")
    a = ap.parse_args()
    if not a.dry_run:
        raise SystemExit("live run arrives in C3/C4; use --dry-run")
    feeds = load_feeds()
    items = normalize(load_fixtures(), feeds, a.fresh_days)
    conn = seen_db.connect(*([Path(a.db)] if a.db else []))
    fresh = seen_db.unseen(conn, items)
    for i in fresh:
        print(f"{i.date[:10]}  {i.source}: {i.title}\n            {i.url}")
    print(f"\n{len(feeds)} feeds, {len(items)} items, {len(fresh)} unseen (dry run: no model call, nothing marked seen)")


if __name__ == "__main__":
    main()
