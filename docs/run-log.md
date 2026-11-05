# Run log — G1·B live model calls

Prices per MTok (D-8): Haiku 5.5 $0.10 in / $0.50 out; Sonnet 5.5 $2 / $10. Hard cap for the build: **$10** (D-9).
Source of truth is the `run_log` Data Table in the owner's n8n (one row per agent call, plus `status=error` rows from the error path); this file is the human copy, updated after each build session.

| Date (UTC) | Exec | Agent | Model | In | Out | Cost | Result |
|---|---|---|---|---|---|---|---|
| 2026-11-05 00:0x | 3 | Researcher | claude-haiku-5-5 | 16,619 | 8,000 | $0.0057 | **error**: hit max_tokens echoing 106 URLs; fixed by answering with ids |
| 2026-11-05 00:12 | 4 | Researcher | claude-haiku-5-5 | 17,275 | 3,414 | $0.0034 | ok, 106 → 29 kept |
| 2026-11-05 00:12 | 4 | Summarizer | claude-haiku-5-5 | 5,865 | 3,707 | $0.0024 | ok, 29 summarized |
| 2026-11-05 00:12 | 4 | Editor | claude-sonnet-5-5 | 8,525 | 765 | $0.0247 | ok, 8 picked; digest in Drive `1tewKrCX-4yEu97KbAoe81fwZ9iDsugXF` |

**Cost per successful run: $0.031.** Running total of the build: **$0.036** of $10.

Shape of a run (2026-11-05): 15 feeds → 2,072 RSS items → 106 from the last 7 days → 29 on-topic → 8 picked. The Editor is 80% of the cost; the two Haiku passes together are under a cent.
