# Backlog — G1 Weekly Signal Scout

Each task fits one sitting and ends with a test and a commit on `kickoff`. Acceptance criteria (AC) come from `docs/prd.md` §Acceptance criteria. Owner hand steps are listed separately at the bottom; a task that needs one says so.

Status: `todo` · `doing` · `done` · `blocked`.

## G1·B (n8n)

| # | Task | Done when | Status |
|---|---|---|---|
| B0 | Decisions. Ask the owner the three open decisions (models, fire time, sources) one at a time; record D-10..12. | DECISIONS.md has all three; no "proposed" left in them. | done |
| B1 | Feed list. `config/feeds.md`: 10–15 RSS feeds across marketing-ops/martech, AI vendor blogs, agent-commerce protocol news, each with one line on why. Every URL fetched and parsed as RSS/Atom before it goes in. Must-include sources from the owner added. | `feeds.md` lists 10–15 feeds; a script output in the commit message shows each URL returned 200 and parsed with ≥1 item. | done |
| B2 | Fixtures. `fixtures/feed-items.json`: a saved sample (~40 items across the feeds) in the shape RSS Read emits, plus `fixtures/README.md` on how to load it (a Code node that emits the fixture, wired in place of the RSS nodes when a `TEST` flag is set). | Workflow can run end to end with no network call to a feed. | done (loader wired in B3) |
| B3 | Workflow skeleton. `n8n/g1-signal-scout.json`: Schedule Trigger (inactive) → RSS Read ×N → Merge → Code (normalize: title, url, source, date, excerpt) → Data Table lookup (`seen_items`, key = url) → filter unseen. No LLM yet. | Imported into the owner's n8n; manual run with fixtures outputs only items not in `seen_items`. Owner hand step H1. | done (live run: 2069 → 106 fresh → 106 unseen; seeded-URL dedupe proven in simulation, live at B8) |
| B4 | Researcher agent. AI Agent node + Anthropic Chat Model (model per D-10). System prompt carries: topic brief, claim rule (no claim without a source link), run-log line. Output: item list with title, url, source, date, excerpt. Duplication-log entries started. | Manual run returns a JSON item list; tokens and cost for the call logged to `docs/run-log.md`. | done |
| B5 | Summarizer agent. Two-sentence summary + topic tag (`marketing-ops-ai` / `agent-readiness` / `other`) per item. Same carried rules; duplication log updated. | Manual run: every item has a summary and one of the three tags. | done |
| B6 | Editor agent. Keeps 5–8 best, cuts `other`, adds a one-line post angle per item in brand voice. Carries topic brief, claim rule, brand voice, run log. Produces the digest as Markdown. | Manual run: 5–8 items, each with source link and post angle. (AC 1, content half.) | done |
| B7 | Drive write, then mark seen. Google Drive node writes `Signal Scout — week of YYYY-MM-DD.md` to the owner's folder (D-13). Only on success: Data Table insert of every item in the digest into `seen_items`. | Manual run: file appears in Drive; `seen_items` gains exactly the digest's items. (AC 1.) Owner hand step H2. | done |
| B8 | Dedupe proof. Run twice in a row. | Second run's digest shares no URL with the first. (AC 2.) | done |
| B9 | Error path. Error Trigger workflow + Stop and Error on a failed Drive write: logs the failure (run-log entry) and stops; nothing is marked seen. | Test: point the Drive node at an invalid folder id, run, confirm `seen_items` unchanged and the error logged; restore the folder id. (AC 3.) | done |
| B10 | Duplication log. `docs/duplication-log.md`: every rule copied into more than one agent, which agents carry it, verbatim text. | Lists at least topic brief, claim rule, brand voice, run logging with the agents each appears in. (AC 4.) | done |
| B11 | n8n README. `n8n/README.md`: exact import steps, credential names the JSON expects, Data Table creation, folder id, how to run with fixtures, how to run live, how to turn the schedule on (not done without the owner's go). | Owner can re-import from scratch following only the README. | todo |
| B12 | Cost log. `docs/run-log.md`: per run, per agent, tokens in/out and dollars at D-8 prices; running total against the $10 cap. | Every live run in the build has an entry; total shown. | done |
| B13 | Acceptance. Walk AC 1–4 against the live workflow with the owner and record the result in NEXT.md. Schedule stays off until he says go. | All four pass; NEXT.md says so and names G0 as next. | todo |

## G1·C (code) — starts only after B13 passes (D-1)

| # | Task | Done when | Status |
|---|---|---|---|
| C1 | Project scaffold. Python 3.12, `uv`, Claude Agent SDK, `.env.example` (names only), SQLite `seen_items`, same feeds from `config/feeds.md`. | `uv run scout --dry-run` lists unseen items from the fixtures with no model call. | todo |
| C2 | Typed hand-offs. Pydantic models `Item`, `SummarizedItem`, `DigestItem`, `Digest`. | Unit test: a fixture item round-trips through all three models. | todo |
| C3 | Three agents in sequence, same prompts and models as B4–B6, reading the duplication log so the duplication is identical. | Manual run on fixtures produces a 5–8 item digest. | todo |
| C4 | Drive write then mark seen, error path, same order as B7/B9. | Same tests as B8 and B9 pass against SQLite. (AC 1–3.) | todo |
| C5 | Cost log per run: tokens and dollars per agent, written next to the n8n numbers for the same week of sources. | `docs/run-log.md` has a side-by-side table for one week. (AC 5.) | todo |
| C6 | Scheduler: launchd plist (owner's Mac) at the D-11 fire time, not loaded without the owner's go. | Plist in repo; `launchctl` load is a listed hand step. | todo |

## Owner hand steps

| # | When | Step |
|---|---|---|
| H0 | Before B0 | Confirm n8n version (Settings → About). Confirm an Anthropic credential and a connected Google Drive OAuth2 credential exist (Overview → Credentials). Name the Drive folder for digests (PRD question 3) and any must-include sources (question 2). |
| H1 | B3 | Import `n8n/g1-signal-scout.json` (Workflows → ⋯ → Import from file). Create the `seen_items` Data Table (columns: `url` text, `title` text, `source` text, `seen_at` date). |
| H2 | B7 | Open the Google Drive node, pick the credential, paste the folder id. Open the Anthropic Chat Model nodes, pick the credential. |
| H3 | B8, B9, B13 | Press "Execute workflow" when asked; read back the Drive folder and the Data Table. |
| H4 | After B13 | Say "go" to switch the Schedule Trigger on. Until then it stays off. |
