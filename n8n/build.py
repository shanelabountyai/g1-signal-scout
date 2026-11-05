#!/usr/bin/env python3
"""Build n8n/g1-signal-scout.json from readable pieces.

Usage: python3 n8n/build.py
The JSON is what the owner imports; this file exists so the JavaScript inside
Code nodes is edited as JavaScript, not as escaped JSON strings. Stdlib only.
Node parameter shapes were read from the installed n8n 2.46.6 package (D-7).
"""
import json
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prompts  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FEEDS_MD = ROOT / "config" / "feeds.md"
FIXTURES = ROOT / "fixtures" / "feed-items.json"
SEEN_TABLE = {"id": "KY3yNvowzRzwrfgH", "name": "seen_items"}  # owner's n8n, created 2026-11-04 (H1)
ANTHROPIC_CRED = {"id": "Bdvgd2nJk9NDSzTC", "name": "anthropic"}  # httpHeaderAuth, already in owner's n8n
DRIVE_CRED = {"id": "wAW20JZRMalAkhpe", "name": "Google Drive account"}  # googleDriveOAuth2Api, already in owner's n8n
DRIVE_FOLDER_ID = "1SguTmcorJEpl3CftOFwr2FpANyhHQAZh"  # 'Signal Scout' in the owner's My Drive (H0c)
RUN_LOG_TABLE = {"id": "bxyWHL7tSS1XL5BE", "name": "run_log"}  # created over the API 2026-11-04
WORKFLOW_ID = "ZsNMHw5Y1QRjFtrI"  # created by the owner's Import from File on 2026-11-04
PRICES = {"claude-haiku-5-5": [0.10, 0.50], "claude-sonnet-5-5": [2.0, 10.0]}  # $/MTok in, out (D-8)
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


# ---------------------------------------------------------------- agent chain

def ask_js(agent, user_content_js):
    """Code node: build the Messages API request body for one agent as $json.body."""
    return "return [{ json: { body: " + prompts.request_body(agent, user_content_js) + " } }];\n"

PACK_JS = """// All unseen items -> one request to the Researcher. No items -> stop quietly (nothing to digest).
const items = $input.all().map((i, idx) => ({ id: idx, ...i.json }));  // id = join key the agents answer with
if (!items.length) return [];
const user = 'Week items as JSON:\\n' + JSON.stringify(items);
""" + ask_js(prompts.RESEARCHER, "user").replace("return [{ json: { body:", "return [{ json: { count: items.length, body:")

PARSE_JS = """// Structured outputs: first content block is text holding valid JSON.
function parsed(resp) {
  const block = (resp.content || []).find(b => b.type === 'text');
  if (!block) throw new Error('No text block in model response: stop_reason=' + resp.stop_reason);
  return JSON.parse(block.text);
}
function byId(items) { const m = new Map(); for (const i of items) m.set(i.id, i); return m; }
"""

AFTER_RESEARCHER_JS = PARSE_JS + """
// Join the Researcher's verdicts back onto the original records: the model never rewrites an item.
const input = byId(JSON.parse($('Pack items').first().json.body.messages[0].content.replace(/^[^\\n]*\\n/, '')));
const out = parsed($input.first().json);
const kept = [];
for (const v of out.items || []) if (v.keep && input.has(v.id)) kept.push(input.get(v.id));
if (!kept.length) throw new Error('Researcher kept 0 of ' + input.size + ' items');
const user = 'Items as JSON:\\n' + JSON.stringify(kept);
""" + ask_js(prompts.SUMMARIZER, "user").replace("return [{ json: { body:", "return [{ json: { kept: kept.length, body:")

AFTER_SUMMARIZER_JS = PARSE_JS + """
const kept = byId(JSON.parse($('After Researcher').first().json.body.messages[0].content.replace(/^[^\\n]*\\n/, '')));
const out = parsed($input.first().json);
const summarized = [];
for (const s of out.items || []) {
  const rec = kept.get(s.id);
  if (!rec) continue;  // claim rule: unknown id, dropped
  summarized.push({ ...rec, summary: s.summary, tag: s.tag });
}
if (!summarized.length) throw new Error('Summarizer returned 0 known items');
const user = 'Summarized items as JSON:\\n' + JSON.stringify(summarized);
""" + ask_js(prompts.EDITOR, "user").replace("return [{ json: { body:", "return [{ json: { summarized: summarized.length, body:")

COMPOSE_JS = PARSE_JS + f"""
// Deterministic digest: every link and fact comes from the item record, the model only adds angle, why, intro.
const PRICES = {json.dumps(PRICES)};
const summarized = byId(JSON.parse($('After Summarizer').first().json.body.messages[0].content.replace(/^[^\\n]*\\n/, '')));
const out = parsed($input.first().json);
const picks = [];
for (const p of out.picks || []) {{ const rec = summarized.get(p.id); if (rec) picks.push({{ ...rec, post_angle: p.post_angle, why: p.why }}); }}
if (!picks.length) throw new Error('Editor picked 0 known items');

const now = new Date();
const monday = new Date(now); monday.setUTCDate(now.getUTCDate() - ((now.getUTCDay() + 6) % 7));
const week = monday.toISOString().slice(0, 10);
const runAt = now.toISOString();

const usages = [
  ['Researcher', $('Researcher').first().json],
  ['Summarizer', $('Summarizer').first().json],
  ['Editor', $input.first().json],
].map(([agent, r]) => {{
  const u = r.usage || {{}}; const [pin, pout] = PRICES[r.model] || [0, 0];
  const cost = (u.input_tokens || 0) * pin / 1e6 + (u.output_tokens || 0) * pout / 1e6;
  return {{ run_at: runAt, agent, model: r.model, input_tokens: u.input_tokens || 0, output_tokens: u.output_tokens || 0, cost_usd: Math.round(cost * 1e6) / 1e6, status: 'ok', note: 'stop=' + r.stop_reason }};
}});
const total = usages.reduce((a, u) => a + u.cost_usd, 0);
const counts = {{ fresh: $('Pack items').first().json.count, kept: $('After Researcher').first().json.kept, summarized: $('After Summarizer').first().json.summarized, picked: picks.length }};

const lines = [`# Signal Scout — week of ${{week}}`, '',
  `_Run ${{runAt}} · ${{counts.fresh}} new items from ${{$('Feed list').all().length || 'the'}} feeds · ${{counts.kept}} passed the Researcher · ${{counts.picked}} picked._`, '',
  out.intro || '', ''];
picks.forEach((p, i) => {{
  lines.push(`## ${{i + 1}}. ${{p.title}}`, `**${{p.source}}** · ${{(p.date || '').slice(0, 10)}} · ${{p.url}}`, '', p.summary, '',
    `Tag: ${{p.tag}}`, '', `**Post angle:** ${{p.post_angle}}`, '', `_Why: ${{p.why}}_`, '');
}});
lines.push('---', `Cost this run: ${{usages.map(u => `${{u.agent}} ${{u.model}} ${{u.input_tokens}}→${{u.output_tokens}} tok $${{u.cost_usd.toFixed(4)}}`).join(' · ')}} · total $${{total.toFixed(4)}}`, '');

return [{{ json: {{ week, run_at: runAt, file_name: `Signal Scout — week of ${{week}}.md`, digest_md: lines.join('\\n'), picks: picks.map(p => ({{ url: p.url, title: p.title, source: p.source }})), usages, counts, total_cost_usd: total }} }}];
"""

LOG_USAGE_JS = "return $input.first().json.usages.map(u => ({ json: u }));\n"
UNPACK_PICKS_JS = "return $('Compose digest').first().json.picks.map(p => ({ json: { ...p, seen_at: $('Compose digest').first().json.run_at } }));\n"
LOG_ERROR_JS = """// Error Trigger payload -> one run_log row. Nothing is marked seen on this path (AC 3).
const e = $input.first().json;
const err = (e.execution && e.execution.error) || {};
return [{ json: { run_at: new Date().toISOString(), agent: 'workflow', model: '', input_tokens: 0, output_tokens: 0, cost_usd: 0,
  status: 'error', note: ((e.execution && e.execution.lastNodeExecuted) || '?') + ': ' + String(err.message || err).slice(0, 400) } }];
"""


def http_node(agent, x, y):
    return node(agent["name"], "n8n-nodes-base.httpRequest", 4.4, {
        "method": "POST", "url": "https://api.anthropic.com/v1/messages",
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "sendHeaders": True, "headerParameters": {"parameters": [{"name": "anthropic-version", "value": "2023-06-01"}]},
        "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify($json.body) }}",
        "options": {"timeout": 300000},
    }, x, y, credentials={"httpHeaderAuth": ANTHROPIC_CRED})


def table_insert(name, table, columns, x, y, **extra):
    return node(name, "n8n-nodes-base.dataTable", 1.1, {
        "resource": "row", "operation": "insert",
        "dataTableId": {"__rl": True, "mode": "id", "value": table["id"], "cachedResultName": table["name"]},
        "columns": {"mappingMode": "defineBelow", "value": {c: f"={{{{ $json.{c} }}}}" for c in columns}, "matchingColumns": [],
                    "schema": [{"id": c, "displayName": c, "required": False, "defaultMatch": False, "display": True, "type": "string", "canBeUsedToMatch": True, "removed": False} for c in columns]},
        "options": {},
    }, x, y, **extra)


RUN_LOG_COLUMNS = ["run_at", "agent", "model", "input_tokens", "output_tokens", "cost_usd", "status", "note"]

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

    node("Pack items", "n8n-nodes-base.code", 2, {"jsCode": PACK_JS}, 1560, 120),
    http_node(prompts.RESEARCHER, 1780, 120),
    node("After Researcher", "n8n-nodes-base.code", 2, {"jsCode": AFTER_RESEARCHER_JS}, 2000, 120),
    http_node(prompts.SUMMARIZER, 2220, 120),
    node("After Summarizer", "n8n-nodes-base.code", 2, {"jsCode": AFTER_SUMMARIZER_JS}, 2440, 120),
    http_node(prompts.EDITOR, 2660, 120),
    node("Compose digest", "n8n-nodes-base.code", 2, {"jsCode": COMPOSE_JS}, 2880, 120),
    node("Log usage", "n8n-nodes-base.code", 2, {"jsCode": LOG_USAGE_JS}, 3100, 120),
    table_insert("Run log", RUN_LOG_TABLE, RUN_LOG_COLUMNS, 3320, 120),
    node("Write digest", "n8n-nodes-base.googleDrive", 3, {
        "resource": "file", "operation": "createFromText",
        "content": "={{ $('Compose digest').first().json.digest_md }}",
        "name": "={{ $('Compose digest').first().json.file_name }}",
        "driveId": {"__rl": True, "mode": "list", "value": "My Drive"},
        "folderId": {"__rl": True, "mode": "id", "value": DRIVE_FOLDER_ID},
        "options": {},
    }, 3540, 120, executeOnce=True, credentials={"googleDriveOAuth2Api": DRIVE_CRED}),
    node("Unpack picks", "n8n-nodes-base.code", 2, {"jsCode": UNPACK_PICKS_JS}, 3760, 120),
    table_insert("Mark seen", SEEN_TABLE, ["url", "title", "source", "seen_at"], 3980, 120),

    node("Error Trigger", "n8n-nodes-base.errorTrigger", 1, {}, 0, 480),
    node("Log error", "n8n-nodes-base.code", 2, {"jsCode": LOG_ERROR_JS}, 220, 480),
    table_insert("Run log (error)", RUN_LOG_TABLE, RUN_LOG_COLUMNS, 440, 480),
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
for a, b in [("Drop seen", "Pack items"), ("Pack items", "Researcher"), ("Researcher", "After Researcher"),
             ("After Researcher", "Summarizer"), ("Summarizer", "After Summarizer"), ("After Summarizer", "Editor"),
             ("Editor", "Compose digest"), ("Compose digest", "Log usage"), ("Log usage", "Run log"), ("Run log", "Write digest"),
             ("Write digest", "Unpack picks"), ("Unpack picks", "Mark seen"),
             ("Error Trigger", "Log error"), ("Log error", "Run log (error)")]:
    main_connect(a, b)

workflow = {
    "name": "G1 Weekly Signal Scout",
    "nodes": nodes,
    "connections": connections,
    "active": False,
    # errorWorkflow: WORKFLOW_ID is set at H4 — n8n refuses it until the workflow has a published version.
    "settings": {"executionOrder": "v1", "timezone": "America/Chicago"},
    "pinData": {},
    "meta": {"instanceId": ""},
}

def main_write():
    out = ROOT / "n8n" / "g1-signal-scout.json"
    out.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out.relative_to(ROOT)}: {len(nodes)} nodes, {len(feeds())} feeds")


if __name__ == "__main__":
    main_write()
