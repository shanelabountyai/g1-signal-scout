"""Normalization matches G1·B's Normalize node; fixtures load; a feed is parsed from XML."""

from __future__ import annotations

from datetime import UTC, datetime

from scout import feeds
from scout.config import Feed


def test_fixtures_normalize_to_fresh_unique_items(items, raw_items):
    assert len(raw_items) == 45
    assert len(items) == 29  # 16 fixture items are older than 7 days before the newest one
    assert [i.id for i in items] == list(range(29))
    assert len({i.url for i in items}) == len(items)
    assert all(len(i.excerpt) <= 300 for i in items)
    assert all(i.title == i.title.strip() for i in items)


def test_clean_url_strips_tracking_and_fragment():
    assert feeds.clean_url("https://a.b/x?utm_source=rss&id=3&ref=home#top") == "https://a.b/x?id=3"
    assert feeds.clean_url("https://a.b/x?utm_source=rss") == "https://a.b/x"
    assert feeds.clean_url("  https://a.b/x  ") == "https://a.b/x"


def test_source_comes_from_feed_list_by_host():
    fl = [Feed(source="MarTech", url="https://martech.org/feed/")]
    raws = [{"title": " T ", "link": "https://martech.org/post/?utm_medium=x", "isoDate": "2026-11-04T00:00:00+00:00", "contentSnippet": "a  b\n c"},
            {"title": "U", "link": "https://other.example/p", "isoDate": "2026-11-04T00:00:00+00:00", "contentSnippet": ""}]
    out = feeds.normalize(raws, fl, as_of=datetime(2026, 11, 5, tzinfo=UTC))
    assert out[0].source == "MarTech" and out[0].title == "T" and out[0].url == "https://martech.org/post/" and out[0].excerpt == "a b c"
    assert out[1].source == "other.example"


def test_freshness_window_and_duplicates():
    fl: list[Feed] = []
    now = datetime(2026, 11, 10, tzinfo=UTC)
    raws = [{"title": "old", "link": "https://x/1", "isoDate": "2026-11-01T00:00:00+00:00"},
            {"title": "new", "link": "https://x/2", "isoDate": "2026-11-09T00:00:00+00:00"},
            {"title": "dup", "link": "https://x/2?utm_source=a", "isoDate": "2026-11-09T00:00:00+00:00"},
            {"title": "undated", "link": "https://x/3"}]
    out = feeds.normalize(raws, fl, as_of=now)
    assert [i.title for i in out] == ["new", "undated"]  # old dropped, dup dropped, undated kept


def test_parse_rss_and_atom():
    rss = b"""<rss><channel><item><title>A &amp; B</title><link>https://x/a</link><pubDate>Wed, 04 Nov 2026 14:29:28 +0000</pubDate>
    <description>&lt;p&gt;Hello&lt;/p&gt;</description><guid>g1</guid></item></channel></rss>"""
    out = feeds.parse_feed(rss)
    assert out[0]["title"] == "A & B" and out[0]["contentSnippet"] == "Hello" and out[0]["isoDate"].startswith("2026-11-04T14:29:28")
    atom = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>T</title><link rel="alternate" href="https://y/t"/>
    <published>2026-11-04T10:00:00Z</published><summary>S</summary><id>id1</id></entry></feed>"""
    out = feeds.parse_feed(atom)
    assert out[0]["link"] == "https://y/t" and out[0]["contentSnippet"] == "S" and out[0]["guid"] == "id1"


def test_renumber_makes_ids_dense(items):
    sub = [items[3], items[7], items[20]]
    assert [i.id for i in feeds.renumber(sub)] == [0, 1, 2]
    assert feeds.renumber(sub)[1].url == items[7].url


def test_fetch_all_skips_a_dead_feed(monkeypatch):
    def boom(feed, timeout=20):
        if feed.source == "dead":
            raise OSError("no route")
        return [{"title": "ok", "link": "https://x/ok", "isoDate": "2026-11-04T00:00:00+00:00"}]

    monkeypatch.setattr(feeds, "fetch_feed", boom)
    errors = []
    out = feeds.fetch_all([Feed("dead", "https://d/f"), Feed("live", "https://l/f")], on_error=lambda f, e: errors.append(f.source))
    assert [r["title"] for r in out] == ["ok"] and errors == ["dead"]
