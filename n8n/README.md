# n8n import — G1 Weekly Signal Scout

Owner's n8n: 2.46.6, self-hosted via `npx n8n`, data in `~/.n8n` (D-7). Filled in task by task; final version at B11.

## What the JSON expects to exist already

| Thing | Name / id | Where it's used |
|---|---|---|
| Data Table `seen_items` (`url` string, `title` string, `source` string, `seen_at` date) | id `KY3yNvowzRzwrfgH` | Seen rows, Mark seen |
| Header Auth credential for Anthropic (`x-api-key`) | `anthropic` (id `Bdvgd2nJk9NDSzTC`) | Researcher, Summarizer, Editor (from B4) |
| Google Drive OAuth2 credential | `Google Drive account` | Write digest (from B7) |

If an id differs in your install, edit the constants at the top of `n8n/build.py` and run `python3 n8n/build.py`.

## Import (or re-import after a change)

1. In n8n: **Overview → Workflows → ⋯ (top right) → Import from File** → pick `n8n/g1-signal-scout.json`.
2. Re-importing creates a second copy; delete the old one first, or open the old one and use **⋯ → Import from File** inside it to replace its nodes.
3. The Schedule Trigger is imported **inactive**. Leave it off until the owner says go (D-6, H4).

## Run live (real feeds)

Click **Execute workflow**. On this install that runs from the Schedule Trigger (fires once, now): Feed list → RSS Read → Normalize → Seen rows → Drop seen → … Nothing is marked seen until the Drive write succeeds (B7). First live run on 2026-11-04: 15 feeds → 2069 RSS items → 106 from the last 7 days.

## Run with fixtures (no network)

Open the **Split fixtures** node and click **Execute step**; n8n runs the fixtures path up to it (Manual Trigger → Read fixtures → Extract JSON → Split fixtures), then Execute step on **Drop seen** continues from there. Fixtures are read from the repo path baked into the Read fixtures node (`fixtures/feed-items.json`); regenerate them with `python3 fixtures/make-fixtures.py` if the 7-day freshness window has emptied them.
