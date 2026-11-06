"""Feed items: fetch live RSS/Atom or load the saved fixtures, then normalize.

Normalization is the same as G1·B's Normalize node (n8n/build.py NORMALIZE_JS):
title trimmed; URL without fragment and without utm_/mc_/ref=/source= params;
source from the feed list by hostname, else the hostname; ISO date; excerpt =
contentSnippet with whitespace collapsed, 300 chars; items older than
FRESH_DAYS and in-run duplicate URLs dropped.
"""

from __future__ import annotations

import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from scout.config import FRESH_DAYS, Feed
from scout.models import Item

ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
DC = "{http://purl.org/dc/elements/1.1/}"

RawItem = dict[str, Any]  # the RSS Read shape: title, link, pubDate, isoDate, content, contentSnippet, guid, creator, categories


# ---------------------------------------------------------------- loading


def load_fixtures(path: Path) -> list[RawItem]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        data = data["data"]
    if not isinstance(data, list):
        raise ValueError(f"{path} is not a list of feed items")
    return data


def _text(el: ET.Element, *paths: str) -> str:
    for p in paths:
        v = el.findtext(p)
        if v and v.strip():
            return v.strip()
    return ""


def _strip_html(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _iso(date: str) -> str:
    if not date:
        return ""
    try:
        return parsedate_to_datetime(date).astimezone(UTC).isoformat()
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(date.replace("Z", "+00:00")).astimezone(UTC).isoformat()
        except ValueError:
            return date


def parse_feed(body: bytes) -> list[RawItem]:
    """RSS 2.0 or Atom → RSS Read-shaped dicts. Same field mapping as fixtures/make-fixtures.py."""
    body = re.sub(rb"&(?![a-zA-Z#][a-zA-Z0-9]*;)", b"&amp;", body)
    root = ET.fromstring(body)
    out: list[RawItem] = []
    for it in root.findall(".//item"):
        content = _text(it, f"{CONTENT}encoded", "description")
        pub = _text(it, "pubDate", f"{DC}date")
        out.append({
            "title": _text(it, "title"), "link": _text(it, "link"), "pubDate": pub, "isoDate": _iso(pub),
            "content": content[:2000], "contentSnippet": _strip_html(content)[:2000], "guid": _text(it, "guid"),
            "creator": _text(it, f"{DC}creator", "author"), "categories": [c.text or "" for c in it.findall("category")],
        })
    for e in root.findall(f"{ATOM}entry"):
        link = ""
        for l in e.findall(f"{ATOM}link"):
            if l.get("rel") in (None, "alternate") and l.get("href"):
                link = l.get("href", "")
                break
        content = _text(e, f"{ATOM}content", f"{ATOM}summary")
        pub = _text(e, f"{ATOM}published", f"{ATOM}updated")
        author = e.find(f"{ATOM}author")
        out.append({
            "title": _text(e, f"{ATOM}title"), "link": link, "pubDate": pub, "isoDate": _iso(pub),
            "content": content[:2000], "contentSnippet": _strip_html(content)[:2000], "guid": _text(e, f"{ATOM}id"),
            "creator": _text(author, f"{ATOM}name") if author is not None else "",
            "categories": [c.get("term", "") for c in e.findall(f"{ATOM}category")],
        })
    return out


def fetch_feed(feed: Feed, timeout: float = 20) -> list[RawItem]:
    req = urllib.request.Request(feed.url, headers={"User-Agent": "g1-signal-scout/0.1 (+https://github.com/shanelabountyai/g1-signal-scout)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return parse_feed(r.read())


def fetch_all(feed_list: list[Feed], on_error=None) -> list[RawItem]:
    """One dead feed must not kill the run (G1·B: RSS Read continues on error)."""
    out: list[RawItem] = []
    for f in feed_list:
        try:
            out.extend(fetch_feed(f))
        except Exception as e:  # noqa: BLE001 — logged, not fatal
            if on_error:
                on_error(f, e)
    return out


# ---------------------------------------------------------------- normalizing

_HOST = re.compile(r"^https?://([^/?#]+)", re.I)
_TRACKING = re.compile(r"^(utm_|mc_|ref=|source=)", re.I)


def host_of(url: str) -> str:
    m = _HOST.match(url or "")
    return m.group(1).lower() if m else ""


def clean_url(url: str) -> str:
    base, _, rest = (url or "").strip().split("#")[0].partition("?")
    kept = [p for p in rest.split("&") if p and not _TRACKING.match(p)]
    return base + ("?" + "&".join(kept) if kept else "")


def parse_date(raw: RawItem) -> datetime | None:
    for key in ("isoDate", "pubDate"):
        v = raw.get(key)
        if not v:
            continue
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            try:
                return parsedate_to_datetime(str(v)).astimezone(UTC)
            except (TypeError, ValueError):
                continue
    return None


def newest_date(raws: list[RawItem]) -> datetime | None:
    dates = [d for d in (parse_date(r) for r in raws) if d is not None]
    return max(dates) if dates else None


def normalize(raws: list[RawItem], feed_list: list[Feed], as_of: datetime | None = None, fresh_days: int = FRESH_DAYS) -> list[Item]:
    """RSS Read items → Items. `as_of` is "now" for the freshness window (fixtures pass their newest date, D-33)."""
    now = as_of or datetime.now(UTC)
    cutoff = now - timedelta(days=fresh_days)
    sources = {host_of(f.url): f.source for f in feed_list}
    seen: set[str] = set()
    out: list[Item] = []
    for raw in raws:
        url = clean_url(raw.get("link") or raw.get("guid") or "")
        if not url or url in seen:
            continue
        dt = parse_date(raw)
        if dt is not None and dt < cutoff:
            continue
        seen.add(url)
        host = host_of(url)
        excerpt = re.sub(r"\s+", " ", str(raw.get("contentSnippet") or "")).strip()[:300]
        out.append(Item(
            id=len(out),
            title=str(raw.get("title") or "").strip(),
            url=url,
            source=sources.get(host) or re.sub(r"^www\.", "", host),
            date=dt.isoformat() if dt else str(raw.get("isoDate") or raw.get("pubDate") or ""),
            excerpt=excerpt,
        ))
    return out


def renumber(items: list[Item]) -> list[Item]:
    """Ids are the join key the agents answer with; after dropping seen items they are made dense again."""
    return [it.model_copy(update={"id": i}) for i, it in enumerate(items)]
