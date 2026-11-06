# g1-signal-scout — Weekly Signal Scout (G1)

The first build in the Agentic AI track: a scout that starts itself on a schedule, runs four agents in sequence (Researcher → Summarizer → Editor → Writer) over 15 RSS feeds, and produces a weekly digest of items worth posting about, each with a source link, a post angle and, for the top three, a LinkedIn draft. A seen-items table makes sure a re-run never repeats an item.

It is built twice on purpose: **G1·B** in n8n (`n8n/`, shipped 2026-11-05, schedule on) and **G1·C** in Python with the Claude Agent SDK (`src/scout/`, this section). G1·B carries every shared rule in every agent's prompt and logs that duplication in `docs/duplication-log.md`; G1·C attaches to the shared capability layer **G0** (`shanelabountyai/g0-shared-layer`) instead. Same feeds, same prompts, same models, same fixtures, so the two are comparable.

Spec: `docs/prd.md`. Every decision is numbered in `docs/DECISIONS.md` (D-23 onward are G1·C). Backlog: `docs/BACKLOG.md`. State and the owner's hand steps: `NEXT.md`. The n8n version has its own `n8n/README.md`.

## G1·C (code) — for a reviewer

### What it is

```
config/feeds.md ─► feeds.py ─► normalize ─► seen.py (drop seen) ─► agents.py ──────────────────────► sinks.py ─► seen.py (mark)
fixtures/*.json ─┘                                                   │  Researcher  haiku-5-5            │ LocalSink  out/<week>/{md,json,html}
                                                                     │  Summarizer  haiku-5-5            │ DriveSink  Google Doc + .md (service account)
                                                                     │  Editor      sonnet-5-5           │
                                                                     │  Writer      sonnet-5-5           └─ written BEFORE anything is marked seen
                                                                     ▼
                                                   layer.py → g0-shared-layer (in-process, SQLite)
                                                   health · observability · claims_registry · brand_policy · evaluation · measurement
```

- **`src/scout/pipeline.py`** is one run, in G1·B's order (D-27): health → items → drop seen → four agents → sink write → `measurement digest.published` → mark seen → `measurement run.completed`. A failed write logs an `observability` error row, records `run.failed` and stops with nothing marked seen (AC 3).
- **`src/scout/agents.py`** holds the four agents. Each is **one structured-output call** through the Claude Agent SDK (`llm.AgentSdkCaller`: no tools, one turn, the G1·B JSON schema as `output_format`), so the answer arrives parsed and the token usage arrives with it. The agents only ever answer with an item's integer id; the orchestrator joins back to the record and drops unknown ids (D-14). URLs and titles can never be rewritten by a model.
- **`src/scout/models.py`** are the typed hand-offs (C2): `Item → SummarizedItem → DigestItem → Digest`, plus `PostDraft`, `Check`, `AgentUsage`, `RunCost`. Closed enums for tags and pillars; extra fields refused.
- **`src/scout/prompts.py`** carries the agent instructions and schemas. `tests/test_prompts.py` pins them to `n8n/prompts.py`, the single source (D-23), and proves the three shared rules are gone (below).
- **`src/scout/llm.py`**: `AgentSdkCaller` (live), `RecordedCaller` (replays `fixtures/recorded-responses.json`), `RecordingCaller` (saves a live run for replay).
- **`src/scout/sinks.py`**: the `DigestSink` interface, `LocalSink` (tested), `DriveSink` (implemented, not live-tested without credentials, D-26), `FailingSink` (the AC 3 probe). The Monday email stays in G1·B.
- **`src/scout/seen.py`**: `seen_items` in SQLite, same columns as G1·B's Data Table. Only `mark_seen` writes, and only the pipeline calls it, after the write.

### How each shared capability is called

G1·B's four agents each carried verbatim copies of `topic_brief`, `claim_rule`, `brand_voice` (Editor, Writer) and `run_logging`. In G1·C (`docs/duplication-log.md`, "After attaching"):

| Rule | G1·B | G1·C |
|---|---|---|
| `topic_brief` | 4 copies | 1 constant (`prompts.TOPIC_BRIEF`), injected into each prompt. G1's topic, not a shared capability. |
| `claim_rule` | 4 copies | **0 in prompts.** `layer.evaluate("claim_rule_v1", text, context=<source item>)` on every summary, angle and draft: a summary that invents a number, URL or quote is **dropped** before the Editor; an angle or draft is **flagged**. `layer.check_claims(text)` (`claims_registry`) runs on the same texts; `unsupported` is shown as a defect, `needs_source` as a note. |
| `brand_voice` | 2 copies | **0 in prompts.** `layer.check_brand(angle, "post_angle")` and `layer.check_brand(post, "linkedin")` (`brand_policy` v1 is G1's text, verbatim, as 12 rules), plus `layer.evaluate("post_angle_v1", angle)`. Violations are flagged in the digest with rule id and fix, never silently dropped (D-32). |
| `run_logging` | 4 copies | **0 in prompts.** `layer.log_call(...)` (`observability`) after every model call with the response usage and the cost computed from **G0's** `evaluation.PRICES_PER_MTOK` — G1·C has no price table (`tests/test_costlog.py` proves it). The run total and `over_cap` come back; at `over_cap` the next agent is not called (D-28). |
| — | — | `layer.record(...)` (`measurement`) for `run.started`, `digest.published`, `run.completed`, `run.failed`, `run.empty`, `run.dry_run`. `layer.require_healthy()` first on every run; a degraded layer refuses to run (exit 3). |

The layer is called **in-process** (`shared_layer.capabilities.*` on `shared_layer.storage.open_database()`, D-31), not over MCP stdio: the agents make no tool calls, so the orchestrator — not the model — enforces the rules, and a `Refusal` becomes `Output(ok=False, error=…)` exactly as G0's server does. Pin: `pyproject.toml` → `g0-shared-layer @ git+https://github.com/shanelabountyai/g0-shared-layer@1cb74df…` (the `kickoff` commit read for this build; move to `v0.1.0` after the owner tags it).

A fixture run (7 picks, 3 drafts) makes **77 shared-layer calls** and zero model calls for them: health 1, observability 4, claims_registry 26, brand_policy 10, evaluation 33, measurement 3. Every one is visible in the digest footer and in G0's SQLite (`run_log`, `events`, `evaluations`).

**Before/after, counted from the source** (`docs/duplication-log.md`): rules carried by more than one agent **7 → 0**; copies of the 8 shared rules in G1's source **24 → 3** (plus 4 built once in G0); integrations **16 → 4**.

### How to run on fixtures

```bash
uv sync --all-groups                 # Python 3.12, G0 from git (needs read access to the private repo), the Agent SDK (~150 MB wheel, bundles the Claude Code CLI)
uv run pytest                        # 54 tests, ~1 s, no network, no model call
uv run scout --dry-run               # G0 health, 45 fixture items → 29 fresh → N unseen; no model call, nothing written
uv run scout --fixtures              # full run: agents answer from fixtures/recorded-responses.json; digest under out/<week>/; items marked seen
uv run scout --fixtures --sink failing   # AC 3 by hand: exit 2, nothing marked seen, an error row in G0's run_log
```

Without `ANTHROPIC_API_KEY`, `--fixtures` replays `fixtures/recorded-responses.json`. **That file is a hand-made sample in each agent's output schema, not a recording of a live model** (D-30): no live G1·C call has been made yet, so its usage is zero and the digest says "cost not measured". State lives in `SCOUT_DB_PATH` (seen items) and `G0_DB_PATH` (the layer); point both at scratch files to replay from a clean slate. Fixture mode measures the 7-day freshness window from the newest fixture item (D-33), so the saved fixtures never go stale.

### How to run live

```bash
export ANTHROPIC_API_KEY=…            # live calls only when set (D-28); confirm model ids and prices on Anthropic's pricing page first
uv run scout --fixtures --record      # one live run on the fixtures, saving real responses over the hand-made file
uv run scout --live                   # real feeds, real models, local sink, cost logged per agent, $10 cap (G0_RUN_CAP_USD)
uv run scout --live --sink drive      # …with SCOUT_DRIVE_SERVICE_ACCOUNT_JSON and SCOUT_DRIVE_FOLDER_ID set (uv sync --extra drive)
```

Exit codes: 0 ok or empty week · 2 run failed before marking seen (sink or agent) · 3 shared layer degraded · 4 live asked for without a key. `scout` prints the run-log rows for `docs/run-log.md` and writes `out/<week>/cost.json`.

### Cost, side by side with G1·B

`docs/run-log.md` has the AC 5 table. G1·B exec 8 (same four agents): Researcher $0.0030 · Summarizer $0.0018 · Editor $0.0254 · Writer $0.0377 · **$0.068 per run**. **G1·C: not measured** — no key was present in the build run. When it runs, expect slightly lower input tokens (the prompts are 35 words shorter for the Haiku pair and 111 shorter for the Editor and Writer with the rules moved out), cache tokens billed at the input price as an upper bound, and no added cost from the shared-layer checks, which make no model call.

### What is not done, said plainly

- No live G1·C model call has happened; the recorded fixture is hand-made and labelled as such. Hand step H5 replaces it.
- `DriveSink` is unit-tested for its preconditions only; the upload path has not run against Drive.
- The Monday email is G1·B's job for now (D-26).
- The launchd plist (`launchd/`) is written and tested, never loaded (D-29). Loading it means two scouts fire on Mondays until G1·B's schedule is turned off — the owner's call.
- `claims_registry` flags one of Shane's own record facts as `unsupported` in a draft because it collides with a seeded third-party stat on topic words; the digest shows it and the owner decides. Candidate change for G0 v1.1, noted in `NEXT.md`.
