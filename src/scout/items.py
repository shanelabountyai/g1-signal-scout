"""Feed list, fixtures and normalize. Mirrors the n8n Normalize node (n8n/build.py NORMALIZE_JS)."""
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
FRESH_DAYS = 7


class Item(BaseModel):
    title: str
    url: str
    source: str
    date: str
    excerpt: str


def load_feeds(path: Path = ROOT / "config" / "feeds.md") -> list[tuple[str, str]]:
    """(source, url) from the markdown tables in feeds.md."""
    rows = []
    for line in path.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[1].startswith("http"):
            rows.append((cells[0], cells[1]))
    return rows


def clean_url(u: str) -> str:
    base = u.strip().split("#")[0]
    base, _, q = base.partition("?")
    kept = [p for p in q.split("&") if p and not re.match(r"(utm_|mc_|ref=|source=)", p, re.I)]
    return base + ("?" + "&".join(kept) if kept else "")


def _parse_date(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        try:
            return parsedate_to_datetime(s)
        except (TypeError, ValueError):
            return None


def normalize(raw: list[dict], feeds: list[tuple[str, str]], fresh_days: int | None = FRESH_DAYS) -> list[Item]:
    """One Item per entry; drops stale (if fresh_days) and in-run duplicate URLs."""
    sources = {urlsplit(u).hostname: s for s, u in feeds}
    cutoff = datetime.now(timezone.utc) - timedelta(days=fresh_days) if fresh_days else None
    seen, out = set(), []
    for j in raw:
        url = clean_url(j.get("link") or j.get("guid") or "")
        if not url or url in seen:
            continue
        date = j.get("isoDate") or j.get("pubDate") or ""
        t = _parse_date(date)
        if t and cutoff and t.astimezone(timezone.utc) < cutoff:
            continue
        seen.add(url)
        host = urlsplit(url).hostname or ""
        out.append(Item(
            title=(j.get("title") or "").strip(),
            url=url,
            source=sources.get(host) or host.removeprefix("www."),
            date=t.astimezone(timezone.utc).isoformat() if t else date,
            excerpt=" ".join((j.get("contentSnippet") or "").split())[:300],
        ))
    return out


def load_fixtures() -> list[dict]:
    return json.loads((ROOT / "fixtures" / "feed-items.json").read_text())
