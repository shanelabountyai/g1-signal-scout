#!/usr/bin/env python3
"""Save a sample of live feed items in the shape n8n's RSS Read node emits.

Usage: python3 fixtures/make-fixtures.py [per_feed=3]
Reads the feed URLs from config/feeds.md, takes the newest N items of each,
and writes fixtures/feed-items.json. Stdlib only.

n8n RSS Read (rss-parser) item fields reproduced: title, link, pubDate,
isoDate, content, contentSnippet, guid, creator, categories.
"""
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
DC = "{http://purl.org/dc/elements/1.1/}"


def text(el, *paths):
    for p in paths:
        v = el.findtext(p)
        if v and v.strip():
            return v.strip()
    return ""


def strip_html(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def iso(date: str) -> str:
    if not date:
        return ""
    try:
        return parsedate_to_datetime(date).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(date.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
        except ValueError:
            return date


def items_of(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "g1-signal-scout fixtures"})
    with urllib.request.urlopen(req, timeout=20) as r:
        body = re.sub(rb"&(?![a-zA-Z#][a-zA-Z0-9]*;)", b"&amp;", r.read())
    root = ET.fromstring(body)
    for it in root.findall(".//item"):
        content = text(it, f"{CONTENT}encoded", "description")
        yield {
            "title": text(it, "title"),
            "link": text(it, "link"),
            "pubDate": text(it, "pubDate"),
            "isoDate": iso(text(it, "pubDate")),
            "content": content[:2000],  # keep the repo light; the workflow reads contentSnippet
            "contentSnippet": strip_html(content)[:400],
            "guid": text(it, "guid") or text(it, "link"),
            "creator": text(it, f"{DC}creator", "author"),
            "categories": [c.text.strip() for c in it.findall("category") if c.text],
        }
    for it in root.findall(f".//{ATOM}entry"):
        link_el = it.find(f"{ATOM}link[@rel='alternate']")
        if link_el is None:
            link_el = it.find(f"{ATOM}link")
        link = link_el.get("href", "") if link_el is not None else ""
        content = text(it, f"{ATOM}content", f"{ATOM}summary")
        date = text(it, f"{ATOM}published", f"{ATOM}updated")
        yield {
            "title": text(it, f"{ATOM}title"),
            "link": link,
            "pubDate": date,
            "isoDate": iso(date),
            "content": content[:2000],
            "contentSnippet": strip_html(content)[:400],
            "guid": text(it, f"{ATOM}id") or link,
            "creator": text(it, f"{ATOM}author/{ATOM}name"),
            "categories": [c.get("term", "") for c in it.findall(f"{ATOM}category") if c.get("term")],
        }


def main() -> int:
    per_feed = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    urls = re.findall(r"\| (https?://[^\s|]+) \|", Path("config/feeds.md").read_text())
    out = []
    for url in urls:
        try:
            got = []
            for item in items_of(url):
                got.append(item)
                if len(got) == per_feed:
                    break
            print(f"{len(got)} {url}")
            out.extend(got)
        except Exception as e:  # noqa: BLE001
            print(f"0 {url}  ({e})")
    Path("fixtures/feed-items.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"\nwrote fixtures/feed-items.json with {len(out)} items from {len(urls)} feeds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
