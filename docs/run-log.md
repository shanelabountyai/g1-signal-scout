# Run log — G1·B live model calls

Prices per MTok (D-8): Haiku 5.5 $0.10 in / $0.50 out; Sonnet 5.5 $2 / $10. Hard cap for the build: **$10** (D-9).
Source of truth is the `run_log` Data Table in the owner's n8n (one row per agent call, plus `status=error` rows from the error path); this file is the human copy, updated after each build session.

| Date (UTC) | Exec | Agent | Model | In | Out | Cost | Result |
|---|---|---|---|---|---|---|---|
| 2026-11-05 00:0x | 3 | Researcher | claude-haiku-5-5 | 16,619 | 8,000 | $0.0057 | **error**: hit max_tokens echoing 106 URLs; fixed by answering with ids |
| 2026-11-05 00:12 | 4 | Researcher | claude-haiku-5-5 | 17,275 | 3,414 | $0.0034 | ok, 106 → 29 kept |
| 2026-11-05 00:12 | 4 | Summarizer | claude-haiku-5-5 | 5,865 | 3,707 | $0.0024 | ok, 29 summarized |
| 2026-11-05 00:12 | 4 | Editor | claude-sonnet-5-5 | 8,525 | 765 | $0.0247 | ok, 8 picked; digest in Drive `1tewKrCX-4yEu97KbAoe81fwZ9iDsugXF` |

| 2026-11-05 00:15 | 5 | Researcher | claude-haiku-5-5 | 15,946 | 4,879 | $0.0040 | ok, 98 → 29 kept (second run, AC 2) |
| 2026-11-05 00:15 | 5 | Summarizer | claude-haiku-5-5 | 6,016 | 4,102 | $0.0027 | ok |
| 2026-11-05 00:15 | 5 | Editor | claude-sonnet-5-5 | 8,388 | 534 | $0.0221 | ok, 5 picked (only 5 on topic left); **0 URLs shared with run 4** |
| 2026-11-05 00:18 | 6 | all three | — | ~30k | ~9k | ~$0.03 | model calls ok; Drive write failed on purpose (bogus folder, AC 3); 0 rows marked seen |
| 2026-11-05 00:2x | 7 | all three | — | ~30k | ~9k | ~$0.03 | same test with the error path wired: `run_log` error row written, run stopped red, 0 rows marked seen |

| 2026-11-05 00:4x | 8 | Researcher | claude-haiku-5-5 | 15,056 | 3,060 | $0.0030 | ok, 93 → 20 kept |
| 2026-11-05 00:4x | 8 | Summarizer | claude-haiku-5-5 | 4,366 | 2,815 | $0.0018 | ok |
| 2026-11-05 00:4x | 8 | Editor | claude-sonnet-5-5 | 6,329 | 1,270 | $0.0254 | ok, 5 picked |
| 2026-11-05 00:4x | 8 | Writer | claude-sonnet-5-5 | 3,432 | 3,082 | $0.0377 | ok, 3 drafts (AI Integration, MarTech, Scale); Doc `1M5Xvp8q2xxaDUlSYEQ3y0ltmmR6ZI0f3HbF9UImMH8w`; email sent |

**Cost per run with drafts (D-20): ~$0.07** (~$3.50/year at one run a week). Running total of the build: **~$0.20** of $10.

Shape of a run (2026-11-05): 15 feeds → 2,072 RSS items → 106 from the last 7 days → 29 on-topic → 8 picked. The Editor is 80% of the cost; the two Haiku passes together are under a cent.

## G1·C (code) — side by side with G1·B for the same week of sources (AC 5)

Prices: G1·C has no price table of its own; cost is computed from the response `usage` with G0's `evaluation.PRICES_PER_MTOK` (D-28), which equals D-8. Model ids and prices re-checked 2026-11-06 against secondary sources (Anthropic's own page not fetchable unattended): Haiku 5.5 $0.10/$0.50 (≤100K prompt), Sonnet 5.5 $2/$10. Source of truth for G1·C is G0's `run_log` table (`G0_DB_PATH`), one row per agent call with `run_id = g1c-<week>-<HHMMSS>`; `out/<week>/cost.json` is the per-run copy.

**Status 2026-11-06: no `ANTHROPIC_API_KEY` was present in the G1·C build run, so no live G1·C call has been made. G1·C is "not measured" below.** The G1·B column is exec 8 of 2026-11-05 (the run with the Writer, the same shape as G1·C). The G1·C column fills in after hand step H5 (`uv run scout --fixtures --record`, then `uv run scout --live`); paste the rows `scout` prints.

| Agent | Model | G1·B (n8n, exec 8) in → out | G1·B cost | G1·C (code) in → out | G1·C cost |
|---|---|---|---|---|---|
| Researcher | claude-haiku-5-5 | 15,056 → 3,060 | $0.0030 | not measured | not measured |
| Summarizer | claude-haiku-5-5 | 4,366 → 2,815 | $0.0018 | not measured | not measured |
| Editor | claude-sonnet-5-5 | 6,329 → 1,270 | $0.0254 | not measured | not measured |
| Writer | claude-sonnet-5-5 | 3,432 → 3,082 | $0.0377 | not measured | not measured |
| **Run total** | | | **$0.0679** | | **not measured** |

What will differ when G1·C is measured, and why:
- **Prompts are shorter.** G1·C's system prompts drop the verbatim `claim_rule`, `brand_voice` and `run_logging` blocks (D-24) for one-line pointers: measured on the prompts themselves, 35 fewer words for the Researcher and the Summarizer (272 → 237, 267 → 232) and 111 fewer for the Editor and the Writer (439 → 328, 941 → 830), so input tokens should fall a little; the Editor's per-call cost (80% of the run) is dominated by the item payload, not the rules.
- **Cache tokens are counted at the input price.** The SDK reports `cache_read_input_tokens` and `cache_creation_input_tokens`; G1·C bills them as input (upper bound) and keeps the SDK's own `total_cost_usd` in the note for comparison. G1·B saw no cache usage (one HTTP request per agent).
- **The shared-layer checks cost nothing.** `claims_registry`, `brand_policy`, `observability`, `measurement` and the deterministic `evaluation` judge make no model call. `--judge claude` would add judged evaluations as logged, capped calls under the same `run_id`.

Running total of live G1·C calls: **$0.00** of the $10 cap.
