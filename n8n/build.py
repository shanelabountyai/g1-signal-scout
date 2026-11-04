#!/usr/bin/env python3
"""Build n8n/g1-signal-scout.json from readable pieces.

Usage: python3 n8n/build.py
The JSON is what the owner imports; this file exists so the JavaScript inside
Code nodes is edited as JavaScript, not as escaped JSON strings. Stdlib only.
Node parameter shapes were read from the installed n8n 2.46.6 package (D-7).
"""
import json
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEEDS_MD = ROOT / "config" / "feeds.md"
FIXTURES = ROOT / "fixtures" / "feed-items.json"
SEEN_TABLE = {"id": "KY3yNvowzRzwrfgH", "name": "seen_items"}  # owner's n8n, created 2026-11-04 (H1)
ANTHROPIC_CRED = {"id": "Bdvgd2nJk9NDSzTC", "name": "anthropic"}  # httpHeaderAuth, already in owner's n8n
FRESH_DAYS = 7  # items older than this are dropped before the seen-items check


def feeds():
    rows = re.findall(r"^\| ([^|]+?) \| (https?://[^\s|]+) \|", FEEDS_MD.read_text(), re.M)
    return [{"source": s.strip(), "url": u} for s, u in rows if s.strip() != "Source"]


def nid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"g1-signal-scout/{name}"))


def node(name, type_, version, params, x, y, **extra):
    n = {"parameters": params, "id": nid(name), "name": name, "type": type_, "typeVersion": version, "position": [x, y]}
    n.update(extra)
    return n


# ---------------------------------------------------------------- Code node sources

FEED_LIST_JS = "// Copy of config/feeds.md (n8n cannot read the repo). Rebuilt by n8n/build.py.\n" \
    "const feeds = " + json.dumps(feeds(), indent=2) + ";\n" \
    "return feeds.map(f => ({ json: f }));\n"

SPLIT_FIXTURES_JS = """// Extract From File puts the parsed JSON under .data; turn the array into items.
const d = $input.first().json;
const arr = Array.isArray(d) ? d : (Array.isArray(d.data) ? d.data : [d]);
return arr.map(j => ({ json: j }));
"""

NORMALIZE_JS = f"""// One item per feed entry: title, url, source, date, excerpt. Drops stale and in-run duplicates.
const FRESH_DAYS = {FRESH_DAYS};
const cutoff = Date.now() - FRESH_DAYS * 24 * 60 * 60 * 1000;

// hostname -> source name, from the Feed list node when it ran (live path); else the hostname.
// No URL global in n8n's Code sandbox, so hostnames and query strings are handled with regex.
function hostOf(u) {{ const m = /^https?:\\/\\/([^/?#]+)/i.exec(u || ''); return m ? m[1].toLowerCase() : ''; }}
const sources = {{}};
try {{ for (const f of $('Feed list').all()) sources[hostOf(f.json.url)] = f.json.source; }} catch (e) {{}}

function cleanUrl(u) {{
  const [base, q = ''] = (u || '').trim().split('#')[0].split('?');
  const kept = q.split('&').filter(p => p && !/^(utm_|mc_|ref=|source=)/i.test(p));
  return kept.length ? base + '?' + kept.join('&') : base;
}}

const seen = new Set();
const out = [];
for (const item of $input.all()) {{
  const j = item.json;
  const url = cleanUrl(j.link || j.guid || '');
  if (!url || seen.has(url)) continue;
  const date = j.isoDate || j.pubDate || '';
  const t = Date.parse(date);
  if (!isNaN(t) && t < cutoff) continue;
  seen.add(url);
  const host = hostOf(url);
  out.push({{ json: {{
    title: (j.title || '').trim(),
    url,
    source: sources[host] || host.replace(/^www\\./, ''),
    date: isNaN(t) ? date : new Date(t).toISOString(),
    excerpt: (j.contentSnippet || '').replace(/\\s+/g, ' ').trim().slice(0, 300),
  }} }});
}}
return out;
"""

DROP_SEEN_JS = """// Input: every row of seen_items (one empty item if the table is empty). Output: Normalize items not in it.
const seen = new Set($input.all().map(i => i.json.url).filter(Boolean));
return $('Normalize').all().filter(i => !seen.has(i.json.url));
"""

# ---------------------------------------------------------------- nodes

nodes = [
    node("Schedule Trigger", "n8n-nodes-base.scheduleTrigger", 1.4, {
        "rule": {"interval": [{"field": "weeks", "weeksInterval": 1, "triggerAtDay": [1], "triggerAtHour": 6, "triggerAtMinute": 0}]},
    }, 0, 0),
    node("Feed list", "n8n-nodes-base.code", 2, {"jsCode": FEED_LIST_JS}, 220, 0),
    node("RSS Read", "n8n-nodes-base.rssFeedRead", 1.2, {"url": "={{ $json.url }}", "options": {}}, 440, 0,
         onError="continueRegularOutput"),  # one dead feed must not kill the run

    node("Manual Trigger (fixtures)", "n8n-nodes-base.manualTrigger", 1, {}, 0, 240),
    node("Read fixtures", "n8n-nodes-base.readWriteFile", 1.1, {"fileSelector": str(FIXTURES), "options": {}}, 220, 240),
    node("Extract JSON", "n8n-nodes-base.extractFromFile", 1.2, {"operation": "fromJson", "options": {}}, 440, 240),
    node("Split fixtures", "n8n-nodes-base.code", 2, {"jsCode": SPLIT_FIXTURES_JS}, 660, 240),

    node("Normalize", "n8n-nodes-base.code", 2, {"jsCode": NORMALIZE_JS}, 900, 120),
    node("Seen rows", "n8n-nodes-base.dataTable", 1.1, {
        "resource": "row", "operation": "get", "returnAll": True,
        "dataTableId": {"__rl": True, "mode": "id", "value": SEEN_TABLE["id"], "cachedResultName": SEEN_TABLE["name"]},
        "filters": {}, "matchType": "anyCondition", "options": {},
    }, 1120, 120, executeOnce=True, alwaysOutputData=True),
    node("Drop seen", "n8n-nodes-base.code", 2, {"jsCode": DROP_SEEN_JS}, 1340, 120),
]


def main_connect(src, dst):
    connections.setdefault(src, {"main": [[]]})["main"][0].append({"node": dst, "type": "main", "index": 0})


connections = {}
main_connect("Schedule Trigger", "Feed list")
main_connect("Feed list", "RSS Read")
main_connect("RSS Read", "Normalize")
main_connect("Manual Trigger (fixtures)", "Read fixtures")
main_connect("Read fixtures", "Extract JSON")
main_connect("Extract JSON", "Split fixtures")
main_connect("Split fixtures", "Normalize")
main_connect("Normalize", "Seen rows")
main_connect("Seen rows", "Drop seen")

workflow = {
    "name": "G1 Weekly Signal Scout",
    "nodes": nodes,
    "connections": connections,
    "active": False,
    "settings": {"executionOrder": "v1", "timezone": "America/Chicago"},
    "pinData": {},
    "meta": {"instanceId": ""},
}

if __name__ == "__main__":
    out = ROOT / "n8n" / "g1-signal-scout.json"
    out.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out.relative_to(ROOT)}: {len(nodes)} nodes, {len(feeds())} feeds")
