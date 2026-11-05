# n8n — G1 Weekly Signal Scout

Owner's n8n: 2.46.6, self-hosted via `npx n8n`, data in `~/.n8n` (D-7). Workflow id `ZsNMHw5Y1QRjFtrI`, 26 nodes.

## Files

| File | What |
|---|---|
| `g1-signal-scout.json` | The importable workflow. Generated; do not hand-edit. |
| `build.py` | Builds the JSON (and `docs/duplication-log.md`). Node ids, credential ids, folder id and prices are constants at the top. `python3 n8n/build.py` |
| `prompts.py` | The three agents' system prompts, models, effort, output ceilings and JSON schemas. The shared rules each agent carries live here once and are copied in at build time (D-5). |
| `push.py` | `push`: build and PUT the workflow into n8n over its public API. `exec [N] [node]`: per-node item counts and errors for the Nth-latest run. Needs `N8N_API_KEY` in `.env` (gitignored). |

## What the workflow expects to exist in n8n

| Thing | Name / id | Used by |
|---|---|---|
| Data Table `seen_items` (`url`, `title`, `source` string; `seen_at` date) | `KY3yNvowzRzwrfgH` | Seen rows, Mark seen |
| Data Table `run_log` (`run_at` date; `agent`, `model`, `status`, `note` string; `input_tokens`, `output_tokens`, `cost_usd` number) | `bxyWHL7tSS1XL5BE` | Run log, Run log (error) |
| Header Auth credential (`x-api-key` = Anthropic key) | `anthropic` / `Bdvgd2nJk9NDSzTC` | Researcher, Summarizer, Editor |
| Google Drive OAuth2 credential | `Google Drive account` / `wAW20JZRMalAkhpe` | Write digest |
| Drive folder "Signal Scout" | `1SguTmcorJEpl3CftOFwr2FpANyhHQAZh` | Write digest |

On another install: create the two Data Tables (Overview → Data Tables) and the two credentials, put their ids in `build.py`, then import.

## Import from scratch

1. **Overview → Workflows → ⋯ → Import from File** → `n8n/g1-signal-scout.json`.
2. Set `WORKFLOW_ID` in `build.py` to the new workflow's id (from its URL) so `push.py` can update it.
3. The Schedule Trigger imports **inactive**. It stays off until the owner says go (D-6, H4).

## Update after a change

`python3 n8n/push.py push`, then reload the workflow page in n8n. (Re-importing by hand creates a second copy; prefer push.)

## How a run goes

```
Schedule Trigger (Mon 06:00 America/Chicago)
  → Feed list (15 feeds, copy of config/feeds.md)
  → RSS Read (one node, runs per feed; a dead feed is skipped, not fatal)
  → Normalize (title, url, source, date, excerpt; last 7 days only; tracking params stripped)
  → Seen rows (all of seen_items) → Drop seen
  → Pack items → Researcher (Haiku 5.5, relevance screen)
  → After Researcher → Summarizer (Haiku 5.5, 2-sentence summary + tag)
  → After Summarizer → Editor (Sonnet 5.5, keep 5–8, post angle, intro)
  → Compose digest (Markdown built in code; links come from the records, never from the model)
  → Log usage → Run log (3 rows: tokens and $ per agent)
  → Write digest (Drive, "Signal Scout — week of YYYY-MM-DD.md")
      success → Unpack picks → Mark seen (only now are items recorded)
      error   → Log error → Run log (error) → Stop: run failed
```

Nothing is marked seen unless the Drive write succeeded (AC 3). A run with no new items stops quietly at Pack items.

## Run it by hand

- **Live:** click **Execute workflow**. On this install that fires the Schedule Trigger once. About $0.03 per run (see `docs/run-log.md`).
- **Fixtures (no feed on the network):** open **Split fixtures** → **Execute step** (Manual Trigger → Read fixtures → Extract JSON → Split fixtures), then **Execute step** on a later node to continue. Fixtures: `fixtures/feed-items.json`; regenerate with `python3 fixtures/make-fixtures.py` when the 7-day window has emptied them. The model calls still cost money on this path.
- **Error path test:** `B9_BREAK_DRIVE=1 python3 n8n/push.py push`, run, expect red at **Stop: run failed** and an `error` row in `run_log`; then `python3 n8n/push.py push` to restore.

## Turning the schedule on (H4, owner only)

1. Toggle the workflow **Active** (top right). n8n 2.x publishes a version when you do.
2. Then set **Settings → Error Workflow** to this workflow itself, so a failure in any node (not only Drive) writes a `run_log` error row. Or set `"errorWorkflow": WORKFLOW_ID` in `build.py`'s settings and push.
3. The Mac must be awake with `npx n8n` running at Monday 06:00 CT, or the run slips to the next time n8n is up.

## Email delivery

Sent by the **Send email** node (Gmail credential `Gmail account`, signed in as shane@labintelligence.co) to shanelabountyai@gmail.com, after Mark seen. The first send on 2026-11-05 reached the inbox, but late. If a Monday email is missing, check the run first: a `SENT` label in the Send email output means Gmail accepted it, so look for a delay or Spam before debugging the workflow.
