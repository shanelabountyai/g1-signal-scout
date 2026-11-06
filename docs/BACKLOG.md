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
| B11 | n8n README. `n8n/README.md`: exact import steps, credential names the JSON expects, Data Table creation, folder id, how to run with fixtures, how to run live, how to turn the schedule on (not done without the owner's go). | Owner can re-import from scratch following only the README. | done |
| B12 | Cost log. `docs/run-log.md`: per run, per agent, tokens in/out and dollars at D-8 prices; running total against the $10 cap. | Every live run in the build has an entry; total shown. | done |
| B13 | Acceptance. Walk AC 1–4 against the live workflow with the owner and record the result in NEXT.md. Schedule stays off until he says go. | All four pass; NEXT.md says so and names G0 as next. | done (all four pass; see NEXT.md; schedule stays off until H4) |

## G1·C (code) — started 2026-11-06 after B13 passed (D-1, D-22); work on branch `g1c`

Refreshed 2026-11-06 to D-22..D-32. G1·C attaches to the shared layer G0·C (D-23) instead of carrying the duplicated rules.

| # | Task | Done when | Status |
|---|---|---|---|
| C1 | Project scaffold. Python 3.12, `uv`, `pyproject.toml`, src layout (`src/scout/`), Claude Agent SDK, **G0 pinned as a git dependency to the exact `kickoff` commit** (D-23), `.env.example` (names only), SQLite `seen_items`, same feeds from `config/feeds.md`, same fixtures. | `uv run scout --dry-run` calls G0 `health`, loads the fixtures, and lists unseen items with no model call. | todo |
| C2 | Typed hand-offs. Pydantic models `Item`, `SummarizedItem`, `DigestItem`, `PostDraft`, `Digest`, plus `AgentUsage`/`RunCost`. | Unit test: a fixture item round-trips `Item → SummarizedItem → DigestItem → Digest` and the digest JSON round-trips. | todo |
| C3 | **Four** agents in sequence (Researcher, Summarizer, Editor, Writer; D-20, D-24) with the Claude Agent SDK, same instructions, schemas and models as `n8n/prompts.py`, **attached to G0**: the shared rules are not in the prompts (one-line pointers instead); `claims_registry` + `evaluation(claim_rule_v1)` on every item and draft, `brand_policy` + `evaluation(post_angle_v1)` on every angle and draft, `observability` for every model call, `measurement` for the run and the digest (D-23, D-31). Without a key the agents answer from `fixtures/recorded-responses.json` (D-29). | Run on fixtures produces a 5–8 item digest with up to 3 drafts; every shared-layer call is visible in the digest footer and in G0's SQLite; a test shows a banned phrase in an angle is flagged and an invented number in a summary is dropped. | todo |
| C4 | `DigestSink` (D-25): `LocalSink` (Markdown + JSON under `out/<week>/`) and `DriveSink` (service account; not live-tested without credentials). Seen items marked only after the sink write succeeds; error path in the same order as B7/B9 (D-26). | Same tests as B8 and B9 against SQLite: two runs share no URL; a failing sink leaves `seen_items` unchanged and writes an `error` observability row. (AC 1–3.) | todo |
| C5 | Cost log per run: tokens and dollars per agent from the response `usage` at G0's prices (no second price table, D-27), the run total and the cap, written to `out/<week>/cost.json` and to `docs/run-log.md` next to the n8n numbers for the same week of sources. Live only with `ANTHROPIC_API_KEY`; otherwise "not measured". | `docs/run-log.md` has the side-by-side table for one week. (AC 5.) | todo |
| C6 | Scheduler: launchd plist (owner's Mac) at the D-11 fire time, written, never loaded (D-28). | Plist in repo; `launchctl bootstrap` is a listed hand step. | todo |
| C7 | Reviewer docs: `README.md` G1·C section (architecture, how each capability is called, fixtures and live runs, before/after counts, cost side by side), `docs/duplication-log.md` after-attach section with the real G1 numbers, NEXT.md hand steps; one PR `g1c` → `main`, not merged. | PR open; all tests green; NEXT.md names the owner's next step. | todo |

## Owner hand steps

| # | When | Step |
|---|---|---|
| H0 | Before B0 | Confirm n8n version (Settings → About). Confirm an Anthropic credential and a connected Google Drive OAuth2 credential exist (Overview → Credentials). Name the Drive folder for digests (PRD question 3) and any must-include sources (question 2). |
| H1 | B3 | Import `n8n/g1-signal-scout.json` (Workflows → ⋯ → Import from file). Create the `seen_items` Data Table (columns: `url` text, `title` text, `source` text, `seen_at` date). |
| H2 | B7 | Open the Google Drive node, pick the credential, paste the folder id. Open the Anthropic Chat Model nodes, pick the credential. |
| H3 | B8, B9, B13 | Press "Execute workflow" when asked; read back the Drive folder and the Data Table. |
| H4 | After B13 | Say "go" to switch the Schedule Trigger on. Until then it stays off. |
| H5 | C5 | Export `ANTHROPIC_API_KEY` and run `uv run scout --fixtures --record` once, then `uv run scout --live` for the comparison week; confirm model ids and prices on Anthropic's pricing page first (D-27). |
| H6 | C4 | For the Drive sink: create a Google Cloud service account, share the Signal Scout Drive folder with its email, download its JSON key, set `SCOUT_DRIVE_SERVICE_ACCOUNT_JSON` and `SCOUT_DRIVE_FOLDER_ID` in `.env`. |
| H7 | C6 | `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.labintelligence.g1-signal-scout.plist` after copying the plist there and editing the paths. Only when you want two scouts running on Mondays. |
