# Kickoff — Weekly Signal Scout (Build Log G1, Agentic AI track)

G1·B is built **live with the owner** (decided 2026-11-03): the Anthropic and Google Drive credentials live in his self-hosted n8n (npx, data in `~/.n8n`), so a session can't finish it alone. Paste the block below into Claude Code started in `~/Projects/agentic-track/g1-signal-scout`, on Fable (`/model`), when you're at the keyboard.

```
You are starting a new build: Weekly Signal Scout (Build Log G1, Agentic AI track,
graphic row "Activation"). The spec is docs/prd.md. Read it fully, and ../README.md,
before doing anything. G1 is the first build in the track.

Owner decisions already made (2026-11-03). Record each as a D- entry in
docs/DECISIONS.md before writing anything else:
- G1·B (n8n) first, G1·C (code) only after G1·B passes its acceptance criteria.
- The scout watches AI adoption in marketing ops plus agent readiness.
- The digest lands in Google Drive for now (vault later).
- G1·B is built live with the owner: he imports the workflow and connects credentials.
- Built WITHOUT the shared layer on purpose. Every rule an agent carries that another
  agent also carries goes in docs/duplication-log.md. That log is G0's input.

Open decisions: models (PRD recommends Haiku 5.5 for Researcher and Summarizer,
Sonnet 5.5 for Editor), fire time (PRD recommends Monday 6 AM CT), sources (PRD
recommends RSS only for v1). Ask me these one at a time, each with options and a
recommendation, before building.

G1·B deliverables:
- n8n/g1-signal-scout.json: importable workflow per the PRD's G1·B notes. Seen items
  are recorded only after the Drive write succeeds; an error path logs and stops.
- n8n/README.md: exact import and credential steps for the owner's n8n.
- config/feeds.md: the proposed RSS list (10-15 feeds), each with why it's there.
  Check every feed URL resolves before listing it.
- fixtures/: a saved sample of feed items so the workflow can be tested offline.

Working rules:
- Confirm current Claude model IDs and prices from Anthropic's docs, and current n8n
  node names (RSS Read, AI Agent, Data Table, Google Drive) for the owner's n8n
  version. Ask him for the version; record what you found, not what the PRD guessed.
- Log tokens and cost per run from the first live call. Hard cap: $10 of live model
  calls for the whole build unless I raise it.
- Keep NEXT.md current: what is done, what is next, exact hand steps for the owner.
- git init here if there is no repo; work on a branch named `kickoff`. Commit at the
  end of every task. Never commit secrets.
- No schedule turned on, no merges to main, no deploys and no account changes
  without my explicit go.

Step 1, plan first: write docs/BACKLOG.md breaking G1·B then G1·C into tasks you can
finish and test in one sitting, each with acceptance criteria from the PRD, with my
hand steps listed separately. Then stop and show me the backlog and DECISIONS.md.
```
