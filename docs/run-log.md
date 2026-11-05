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
