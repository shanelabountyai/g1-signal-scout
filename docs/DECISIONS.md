# Decisions — G1 Weekly Signal Scout

One entry per decision, newest last. Owner = Shane. Dates are when decided, not when recorded.

| # | Date | Decision | Why |
|---|---|---|---|
| D-1 | 2026-11-03 | G1·B (n8n) is built first. G1·C (Python + Claude Agent SDK) starts only after G1·B passes its acceptance criteria. | The n8n version is the baseline G1·C is measured against (cost per run, same sources, same models). Building C first would leave nothing to compare. |
| D-2 | 2026-11-03 | Topic brief: the scout watches **AI adoption in marketing ops** plus **agent readiness**. Everything else is "other" and gets cut by the Editor. | Matches the content pillars the digest feeds. Narrow on purpose so a 10–15 feed list stays on topic. |
| D-3 | 2026-11-03 | The digest lands in **Google Drive** for now. The vault comes later. | Drive is already credentialed in the owner's n8n. Vault integration is a separate build. |
| D-4 | 2026-11-03 | G1·B is built **live with the owner**: he imports the workflow JSON and connects the credentials. A session never holds the keys. | The Anthropic and Google Drive credentials live in his self-hosted n8n (`npx`, data in `~/.n8n`). |
| D-5 | 2026-11-03 | Built **without the shared layer** on purpose. Every rule carried by more than one agent is listed in `docs/duplication-log.md`. | That log is G0's input: it shows what the shared layer has to pull out. |
| D-6 | 2026-11-04 | Repo: git on `main`, work on branch `kickoff`, one commit per task. Nothing merges to main, no schedule is switched on, nothing deploys, no account changes without the owner's explicit go. | Kickoff working rules. |
| D-7 | 2026-11-04 | Owner's n8n is **2.46.6** (found in the npx cache; owner confirms in Settings → About). Node names verified in the installed package: Schedule Trigger, RSS Read (`RssFeedRead`), Merge, Data Table, AI Agent, Anthropic Chat Model (`LMChatAnthropic`), Google Drive, Error Trigger, Stop and Error. Data Table exists, so no Google Sheet fallback. | Kickoff rule: record what was found, not what the PRD guessed. |
| D-8 | 2026-11-04 | Model IDs and prices (Anthropic first-party, from the claude-api skill cache dated 2026-10-06; re-check on the first live call): `claude-haiku-5-5` $0.10 in / $0.50 out per MTok (prompts ≤100K); `claude-sonnet-5-5` $2 / $10; `claude-opus-5-5` $4 / $20. | Needed for the per-run cost log and the models decision. |
| D-9 | 2026-11-04 | Hard cap: **$10** of live model calls for the whole G1 build unless the owner raises it. Tokens and cost are logged from the first live call. | Kickoff working rule. |
| D-10 | 2026-11-04 | Models: `claude-haiku-5-5` for Researcher and Summarizer, `claude-sonnet-5-5` for the Editor. | The Editor does the judgment work; the other two are high volume. Gives G1·C a real cost comparison. |
| D-11 | 2026-11-04 | Fire time: **Monday 6:00 AM America/Chicago**, weekly. Schedule Trigger stays off until the owner says go (D-6). | Digest is ready before the week's first post. Owner's Mac must be awake; if not, the run slips. |
| D-12 | 2026-11-04 | Sources: **RSS only** for v1. A search API is added only if a few weeks of digests come up thin. | Free, predictable, no extra credential. Cost per run is the model calls alone. |

No open decisions. Pending owner inputs (H0): n8n version confirmation, Drive folder, must-include sources.
