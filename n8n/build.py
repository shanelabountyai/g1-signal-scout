#!/usr/bin/env python3
"""Build n8n/g1-signal-scout.json from readable pieces.

Usage: python3 n8n/build.py
The JSON is what the owner imports; this file exists so the JavaScript inside
Code nodes is edited as JavaScript, not as escaped JSON strings. Stdlib only.
Node parameter shapes were read from the installed n8n 2.46.6 package (D-7).
"""
import json
import os
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
if os.environ.get("B9_BREAK_DRIVE"):  # error-path test (B9): `B9_BREAK_DRIVE=1 python3 n8n/push.py push`, then push again without it
    DRIVE_FOLDER_ID = "0000-not-a-real-folder-id"
RUN_LOG_TABLE = {"id": "bxyWHL7tSS1XL5BE", "name": "run_log"}  # created over the API 2026-11-04
WORKFLOW_ID = "ZsNMHw5Y1QRjFtrI"  # created by the owner's Import from File on 2026-11-04
EMAIL_TO = "shanelabountyai@gmail.com"  # owner asked for the digest here (2026-11-05)


def _gmail_cred():
    """Gmail OAuth2 credential from the owner's n8n, once he has created it (hand step H5)."""
    import sqlite3
    try:
        con = sqlite3.connect(Path.home() / ".n8n" / "database.sqlite")
        row = con.execute("select id, name from credentials_entity where type = 'gmailOAuth2' order by updatedAt desc limit 1").fetchone()
        return {"id": row[0], "name": row[1]} if row else None
    except sqlite3.Error:
        return None


GMAIL_CRED = _gmail_cred()
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

AFTER_EDITOR_JS = PARSE_JS + """
// Join the Editor's picks to the records, then ask the Writer for up to 3 full drafts.
const summarized = byId(JSON.parse($('After Summarizer').first().json.body.messages[0].content.replace(/^[^\\n]*\\n/, '')));
const out = parsed($input.first().json);
const picks = [];
for (const p of out.picks || []) { const rec = summarized.get(p.id); if (rec) picks.push({ ...rec, post_angle: p.post_angle, why: p.why }); }
if (!picks.length) throw new Error('Editor picked 0 known items');
const forWriter = picks.map(({ id, title, source, summary, tag, post_angle }) => ({ id, title, source, summary, tag, post_angle }));
const user = 'This week\\'s picks as JSON:\\n' + JSON.stringify(forWriter);
""" + ask_js(prompts.WRITER, "user").replace("return [{ json: { body:", "return [{ json: { intro: out.intro || '', picks, body:")

COMPOSE_JS = PARSE_JS + f"""
// Deterministic digest: links and facts come from the item records; models add intro, angles and drafts.
const PRICES = {json.dumps(PRICES)};
const ed = $('After Editor').first().json;
const picks = ed.picks;
const byPick = byId(picks);
const drafts = [];
for (const d of (parsed($input.first().json).drafts || [])) {{ const rec = byPick.get(d.id); if (rec && d.post) drafts.push({{ ...d, rec }}); }}

const now = new Date();
const monday = new Date(now); monday.setUTCDate(now.getUTCDate() - ((now.getUTCDay() + 6) % 7));
const week = monday.toISOString().slice(0, 10);
const runAt = now.toISOString();

const usages = [
  ['Researcher', $('Researcher').first().json],
  ['Summarizer', $('Summarizer').first().json],
  ['Editor', $('Editor').first().json],
  ['Writer', $input.first().json],
].map(([agent, r]) => {{
  const u = r.usage || {{}}; const [pin, pout] = PRICES[r.model] || [0, 0];
  const cost = (u.input_tokens || 0) * pin / 1e6 + (u.output_tokens || 0) * pout / 1e6;
  return {{ run_at: runAt, agent, model: r.model, input_tokens: u.input_tokens || 0, output_tokens: u.output_tokens || 0, cost_usd: Math.round(cost * 1e6) / 1e6, status: 'ok', note: 'stop=' + r.stop_reason }};
}});
const total = usages.reduce((a, u) => a + u.cost_usd, 0);
const counts = {{ fresh: $('Pack items').first().json.count, kept: $('After Researcher').first().json.kept, summarized: $('After Summarizer').first().json.summarized, picked: picks.length, drafted: drafts.length }};

const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const paras = t => String(t || '').split(/\\n\\s*\\n/).map(p => '<p>' + esc(p.trim()).replace(/\\n/g, '<br>') + '</p>').join('');
const hook = t => String(t || '').split('\\n').find(l => l.trim()) || '';
const draftedIds = new Set(drafts.map(d => d.id));

let doc = `<html><head><meta charset="utf-8"></head><body>`;
doc += `<h1>Signal Scout — week of ${{week}}</h1>`;
doc += `<p><i>${{counts.fresh}} new items from ${{$('Feed list').all().length}} feeds · ${{counts.kept}} on topic · ${{counts.picked}} picked · ${{counts.drafted}} drafted · cost $${{total.toFixed(3)}}</i></p>`;
doc += paras(ed.intro);
doc += `<h2>Post drafts</h2>`;
if (!drafts.length) doc += `<p>No pick this week could be anchored honestly to your record, so no drafts. The picks are below.</p>`;
drafts.forEach((d, i) => {{
  doc += `<h3>Draft ${{i + 1}} · ${{esc(d.pillar)}}</h3>`;
  doc += `<p><b>From:</b> <a href="${{esc(d.rec.url)}}">${{esc(d.rec.title)}}</a> (${{esc(d.rec.source)}})<br><b>Anchored to:</b> ${{esc(d.anchor)}}</p>`;
  doc += paras(d.post) + `<p><i>Read it out loud before it ships.</i></p><hr>`;
}});
doc += `<h2>All picks this week</h2>`;
picks.forEach((p, i) => {{
  doc += `<h3>${{i + 1}}. <a href="${{esc(p.url)}}">${{esc(p.title)}}</a>${{draftedIds.has(p.id) ? ' (drafted)' : ''}}</h3>`;
  doc += `<p><b>${{esc(p.source)}}</b> · ${{esc((p.date || '').slice(0, 10))}} · ${{esc(p.tag)}}</p><p>${{esc(p.summary)}}</p>`;
  doc += `<p><b>Angle:</b> ${{esc(p.post_angle)}}<br><i>Why: ${{esc(p.why)}}</i></p>`;
}});
doc += `<hr><p><small>Run ${{runAt}} · ${{usages.map(u => `${{u.agent}} ${{u.model}} ${{u.input_tokens}}→${{u.output_tokens}} tok $${{u.cost_usd.toFixed(4)}}`).join(' · ')}}</small></p></body></html>`;

const fileName = `Signal Scout — week of ${{week}}`;
const B = 'g1scout' + now.getTime();
const uploadBody = `--${{B}}\\r\\nContent-Type: application/json; charset=UTF-8\\r\\n\\r\\n` +
  JSON.stringify({{ name: fileName, mimeType: 'application/vnd.google-apps.document', parents: [{json.dumps(DRIVE_FOLDER_ID)}] }}) +
  `\\r\\n--${{B}}\\r\\nContent-Type: text/html; charset=UTF-8\\r\\n\\r\\n` + doc + `\\r\\n--${{B}}--`;

const subject = `Signal Scout: ${{drafts.length}} post draft${{drafts.length === 1 ? '' : 's'}}, week of ${{week}}`;

return [{{ json: {{ week, run_at: runAt, file_name: fileName, upload_body: uploadBody, boundary: B, subject,
  drafts_preview: drafts.map(d => ({{ pillar: d.pillar, hook: hook(d.post), title: d.rec.title }})), intro: ed.intro,
  picks: picks.map(p => ({{ url: p.url, title: p.title, source: p.source }})), usages, counts, total_cost_usd: total }} }}];
"""

EMAIL_HTML_JS = """// Short Monday email: the thread, the draft hooks, a link to the Doc.
const c = $('Compose digest').first().json;
const docUrl = 'https://docs.google.com/document/d/' + $('Write digest').first().json.id + '/edit';
const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
let h = '<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;font-size:15px;line-height:1.5;max-width:600px">';
h += '<p>' + esc(c.intro) + '</p>';
if (c.drafts_preview.length) {
  h += '<ol>' + c.drafts_preview.map(d => '<li><b>' + esc(d.hook) + '</b><br><span style="color:#666">' + esc(d.pillar) + ' · from ' + esc(d.title) + '</span></li>').join('') + '</ol>';
} else {
  h += '<p>No drafts this week: nothing could be anchored honestly to your record. The picks are in the doc.</p>';
}
h += '<p><a href="' + docUrl + '" style="font-weight:600">Read the drafts and all ' + c.counts.picked + ' picks →</a></p>';
h += '<p style="color:#888;font-size:12px">' + c.counts.fresh + ' new items, ' + c.counts.kept + ' on topic, cost $' + c.total_cost_usd.toFixed(3) + '</p></div>';
return [{ json: { subject: c.subject, html: h, doc_url: docUrl } }];
"""

LOG_USAGE_JS = "return $input.first().json.usages.map(u => ({ json: u }));\n"
UNPACK_PICKS_JS = "return $('Compose digest').first().json.picks.map(p => ({ json: { ...p, seen_at: $('Compose digest').first().json.run_at } }));\n"
LOG_ERROR_JS = """// One run_log row per failure. Reached from an error output (Write digest or Send email) or from the
// Error Trigger (any other node). A Drive failure happens before Mark seen, so nothing is marked seen (AC 3).
const e = $input.first().json;
const fromNode = e.error !== undefined;
const err = fromNode ? e.error : ((e.execution && e.execution.error) || {});
let where = (e.execution && e.execution.lastNodeExecuted) || '?';
if (fromNode) { where = 'Write digest'; try { if ($('Email body').isExecuted) where = 'Send email'; } catch (x) {} }
return [{ json: { run_at: new Date().toISOString(), agent: 'workflow', model: '', input_tokens: 0, output_tokens: 0, cost_usd: 0,
  status: 'error', note: where + ': ' + String((err && err.message) || err).slice(0, 400) } }];
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
    node("After Editor", "n8n-nodes-base.code", 2, {"jsCode": AFTER_EDITOR_JS}, 2880, 120),
    http_node(prompts.WRITER, 3100, 120),
    node("Compose digest", "n8n-nodes-base.code", 2, {"jsCode": COMPOSE_JS}, 3320, 120),
    node("Log usage", "n8n-nodes-base.code", 2, {"jsCode": LOG_USAGE_JS}, 3540, 120),
    table_insert("Run log", RUN_LOG_TABLE, RUN_LOG_COLUMNS, 3760, 120),
    # Upload HTML and let Drive convert it, so the Doc keeps headings, bold and links.
    node("Write digest", "n8n-nodes-base.httpRequest", 4.4, {
        "method": "POST", "url": "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true",
        "authentication": "predefinedCredentialType", "nodeCredentialType": "googleDriveOAuth2Api",
        "sendBody": True, "contentType": "raw",
        "rawContentType": "=multipart/related; boundary={{ $('Compose digest').first().json.boundary }}",
        "body": "={{ $('Compose digest').first().json.upload_body }}",
        "options": {"timeout": 120000},
    }, 3980, 120, executeOnce=True, onError="continueErrorOutput", credentials={"googleDriveOAuth2Api": DRIVE_CRED}),
    node("Unpack picks", "n8n-nodes-base.code", 2, {"jsCode": UNPACK_PICKS_JS}, 4200, 120),
    table_insert("Mark seen", SEEN_TABLE, ["url", "title", "source", "seen_at"], 4420, 120),
    node("Email body", "n8n-nodes-base.code", 2, {"jsCode": EMAIL_HTML_JS}, 4640, 120, executeOnce=True),
    node("Send email", "n8n-nodes-base.gmail", 2.2, {
        "resource": "message", "operation": "send", "sendTo": EMAIL_TO,
        "subject": "={{ $json.subject }}", "emailType": "html", "message": "={{ $json.html }}",
        "options": {"appendAttribution": False, "senderName": "Signal Scout"},
    }, 4860, 120, onError="continueErrorOutput", **({"credentials": {"gmailOAuth2": GMAIL_CRED}} if GMAIL_CRED else {})),

    node("Error Trigger", "n8n-nodes-base.errorTrigger", 1, {}, 0, 480),
    node("Log error", "n8n-nodes-base.code", 2, {"jsCode": LOG_ERROR_JS}, 220, 480),
    table_insert("Run log (error)", RUN_LOG_TABLE, RUN_LOG_COLUMNS, 440, 480),
    node("Stop: run failed", "n8n-nodes-base.stopAndError", 1, {
        "errorMessage": "={{ $('Log error').first().json.note }}"}, 660, 480),  # logged first, then the run goes red
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
             ("Editor", "After Editor"), ("After Editor", "Writer"), ("Writer", "Compose digest"),
             ("Compose digest", "Log usage"), ("Log usage", "Run log"), ("Run log", "Write digest"),
             ("Write digest", "Unpack picks"), ("Unpack picks", "Mark seen"), ("Mark seen", "Email body"), ("Email body", "Send email"),
             ("Error Trigger", "Log error"), ("Log error", "Run log (error)"), ("Run log (error)", "Stop: run failed")]:
    main_connect(a, b)
# Error outputs (index 1) -> Log error. Drive fails before Mark seen (AC 3); email fails after, so the Doc and seen rows stand.
connections["Write digest"]["main"].append([{"node": "Log error", "type": "main", "index": 0}])
connections["Send email"] = {"main": [[], [{"node": "Log error", "type": "main", "index": 0}]]}

workflow = {
    "name": "G1 Weekly Signal Scout",
    "nodes": nodes,
    "connections": connections,
    "active": False,
    # errorWorkflow = itself (Error Trigger node). Accepted only once the workflow has a published version (H4, 2026-11-05).
    "settings": {"executionOrder": "v1", "timezone": "America/Chicago", "errorWorkflow": WORKFLOW_ID},
    "pinData": {},
    "meta": {"instanceId": ""},
}

def duplication_log() -> str:
    """docs/duplication-log.md: every rule carried by more than one agent (D-5; G0's input)."""
    carriers = {k: [a["name"] for a in prompts.AGENTS if k in a["rules"]] for k in prompts.SHARED}
    lines = ["# Duplication log — rules carried by more than one agent", "",
             "Generated by `python3 n8n/build.py` from `n8n/prompts.py`; do not edit by hand. G1 runs without the shared "
             "layer on purpose (D-5), so each agent's system prompt carries its own verbatim copy of these rules. "
             "This list is G0's input: each row is a candidate shared capability.", "",
             "| Rule | Carried by | Copies | Text |", "|---|---|---|---|"]
    for k, who in carriers.items():
        if len(who) > 1:
            lines.append(f"| `{k}` | {', '.join(who)} | {len(who)} | {prompts.SHARED[k]} |")
    lines += ["", "## Duplicated in code, not in prompts", "",
              "| Rule | Where | Copies |", "|---|---|---|",
              "| Join model output back to the original record by id; drop unknown ids (claim rule enforced in code) | After Researcher, After Summarizer, Compose digest | 3 |",
              "| Parse the first text block of a structured-output response | After Researcher, After Summarizer, Compose digest (`PARSE_JS`) | 3 |",
              "| Messages API request shape (model, max_tokens, system, output_config, credential, version header) | Pack items, After Researcher, After Summarizer + the three HTTP Request nodes | 3 |",
              "| Token and cost accounting at D-8 prices | Compose digest (`PRICES`) | 1 in n8n; G1·C will carry a second copy |",
              ""]
    return "\n".join(lines)


def main_write():
    out = ROOT / "n8n" / "g1-signal-scout.json"
    out.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n")
    (ROOT / "docs" / "duplication-log.md").write_text(duplication_log())
    print(f"wrote {out.relative_to(ROOT)}: {len(nodes)} nodes, {len(feeds())} feeds; docs/duplication-log.md")


if __name__ == "__main__":
    main_write()
