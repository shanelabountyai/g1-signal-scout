# NEXT

State (2026-11-05): **G1·B passes all four acceptance criteria and the schedule is on** (D-18; first automatic run Mon 2026-11-09 06:00 CT). Repo: https://github.com/shanelabountyai/g1-signal-scout (private). Branch `kickoff` pushed; nothing merged to main.

| AC | Result | Evidence |
|---|---|---|
| 1. Scheduled run → digest in Drive with 5–8 items, each with source link and post angle | pass | exec 4: 8 picks, Drive file `1tewKrCX-4yEu97KbAoe81fwZ9iDsugXF`; exec 5: 5 picks (only 5 on topic remained; intro says so) |
| 2. Two runs in a row, no repeated items | pass | exec 4 vs 5: 0 shared URLs; `seen_items` 8 → 13 rows |
| 3. Failed Drive write leaves items unmarked | pass | exec 6 and 7 (bogus folder): `seen_items` stayed at 13; exec 7 also wrote a `run_log` error row and stopped red |
| 4. `docs/duplication-log.md` lists every rule in more than one agent | pass | generated from `n8n/prompts.py` on every build |

Cost: ~$0.03 per run; ~$0.13 spent of the $10 cap (`docs/run-log.md`).

## Owner's hand steps still open

- **Merge `kickoff` → `main`** when the owner says so.
- **Check the first automatic run** after Monday 06:00 CT: a new file in the Drive folder and 3 new `run_log` rows. If the Mac was asleep, run it by hand.

## Next item

**G1·C**: the Python + Claude Agent SDK rebuild (`docs/BACKLOG.md` C1–C6). Same feeds (`config/feeds.md`), same prompts (`n8n/prompts.py` is the source), same models, SQLite `seen_items`, cost per run reported next to G1·B's ~$0.03 for the same week.

Then **G0** (`../shared`) starts from `docs/duplication-log.md`.

## Things to know before continuing

- `n8n/push.py push` updates the live workflow; re-importing by hand makes a duplicate.
- The n8n API key lives in `.env` (gitignored). `N8N_API_KEY=` line; the owner pastes the value.
- Feed volume: ~2,000 RSS items/week across 15 feeds, ~100 in the 7-day window, ~30 on topic. If the digest comes up thin for a few weeks, revisit D-12 (add a search API).
- The Editor is ~80% of the cost. Switching it to Haiku would cut a run to under a cent but weaken the post angles.
