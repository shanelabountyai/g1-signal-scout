#!/usr/bin/env python3
"""Check that every feed URL resolves and parses as RSS/Atom.

Usage: python3 config/check-feeds.py [feeds.md]
Reads every http(s) URL from the file (default config/feeds.md) and prints
one line per feed: status, item count, newest item date. Exit 1 if any fail.
Stdlib only, so it runs anywhere n8n does.
"""
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ATOM = "{http://www.w3.org/2005/Atom}"


def check(url: str) -> tuple[bool, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "g1-signal-scout feed check"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read()
    except Exception as e:  # noqa: BLE001 - report, don't crash
        return False, f"fetch failed: {e}"
    # Feeds often ship bare "&" that n8n's parser tolerates and ElementTree does not.
    body = re.sub(rb"&(?![a-zA-Z#][a-zA-Z0-9]*;)", b"&amp;", body)
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        return False, f"not XML: {e}"
    items = root.findall(".//item") or root.findall(f".//{ATOM}entry")
    if not items:
        return False, f"parsed but 0 items (root <{root.tag}>)"
    first = items[0]
    date = (
        first.findtext("pubDate")
        or first.findtext(f"{ATOM}published")
        or first.findtext(f"{ATOM}updated")
        or "no date"
    )
    return True, f"{len(items)} items, newest {date.strip()}"


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "config/feeds.md")
    urls = re.findall(r"https?://[^\s)>|`]+", path.read_text())
    failed = 0
    for url in dict.fromkeys(urls):  # keep order, drop dupes
        ok, msg = check(url)
        failed += not ok
        print(f"{'OK ' if ok else 'BAD'} {url}  {msg}")
    print(f"\n{len(set(urls)) - failed}/{len(set(urls))} feeds OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
