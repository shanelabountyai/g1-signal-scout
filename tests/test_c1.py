from scout import db
from scout.items import load_feeds, load_fixtures, normalize


def test_feeds_and_unseen(tmp_path):
    feeds = load_feeds()
    assert 10 <= len(feeds) <= 15
    items = normalize(load_fixtures(), feeds)  # no freshness filter
    assert items and all(i.url and i.source for i in items)
    conn = db.connect(tmp_path / "t.db")
    assert db.unseen(conn, items) == items
    db.mark_seen(conn, items[:2])
    assert db.unseen(conn, items) == items[2:]
