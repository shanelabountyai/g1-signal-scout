# G1 Weekly Signal Scout — PRD v0.1

Nov 4, 2026 · @Shane LaBounty

## Summary

Agentic AI track, build-log G1, and the first build in the track. A schedule fires it with no prompt. Three agents hand off in order (Researcher → Summarizer → Editor) and produce a weekly digest of items worth posting about. A seen-items table makes sure a re-run never repeats an item.

Built twice: **G1·B in n8n first**, then **G1·C in Python with the Claude Agent SDK** as a hand rebuild of the same scout.

**Already decided (by you, Nov 3):** G1·B before G1·C; the scout watches AI adoption in marketing ops plus agent readiness; the digest lands in Google Drive for now (vault later); G1·B is built live with you because credentials live in your self-hosted n8n.

**From the build-log card:** schedule trigger; sequential pipeline; dedupe state; graphic row "Activation"; built **without** the shared layer on purpose, so G0 has something to pull out of it.

**Everything else here is a proposal.**

## Why it's in the portfolio

It's the first agent that starts itself. It also feeds your real content pipeline, and G1·C measures cost per run against the n8n version, which is a concrete number to post about.

## Agents

| Agent | Job | Output |
| --- | --- | --- |
| Researcher | Pull new items from the sources since the last run; drop anything already in the seen-items table | Item list: title, URL, source, date, short excerpt |
| Summarizer | Two-sentence summary of each item and a topic tag (marketing-ops AI adoption / agent readiness / other) | Summarized items |
| Editor | Keep the 5–8 best items, cut off-topic ones, and add a one-line "post angle" for each | Final digest |

The digest is a Google Doc (or Markdown file) in a Drive folder named for the week. Every item keeps its source link.

## Rules the agents carry (deliberately duplicated)

Because G1 runs without the shared layer, each agent carries its own copy of: the topic brief, claim rules (no claim without a source link), brand voice for post angles, and run logging. **List every duplicated rule in `docs/duplication-log.md`** as you build. That list is G0's input.

## Sources (proposed)

Start with RSS feeds: cheap, predictable and free. About 10–15 feeds across marketing-ops and martech publications, AI vendor blogs, and agent-commerce protocol news. Add a search API (e.g., Tavily or Brave) only if RSS proves too thin. That adds cost per query.

## G1·B (n8n) build notes

- Schedule Trigger → RSS Read nodes (one per feed) → merge → dedupe against a seen-items table (n8n Data Table, or a Google Sheet if Data Tables aren't available in your version)
- Researcher, Summarizer and Editor as three AI Agent / LLM nodes in sequence
- Google Drive node writes the digest; seen items are recorded only after the write succeeds
- An error path that logs the failure and stops without marking items seen
- Runs on your self-hosted n8n (npx, data in `~/.n8n`); you connect the Anthropic and Google Drive credentials

## G1·C (code) build notes

- Python 3.12 + Claude Agent SDK, run by cron (or launchd on your Mac)
- Typed hand-offs between agents (Pydantic models)
- SQLite seen-items table
- Same sources and same models as G1·B; log tokens and cost per run and compare side by side

## Acceptance criteria (proposed)

1. A scheduled run produces a digest in Drive with 5–8 items, each with a source link and a post angle.
2. Running it twice in a row produces no repeated items.
3. A failed Drive write leaves items unmarked, so the next run picks them up.
4. `docs/duplication-log.md` lists every rule copied into more than one agent.
5. **C only:** cost per run reported next to G1·B's for the same week of sources.

## Decisions needed (one at a time)

**1. Models** Options: (a) Haiku 5.5 for Researcher and Summarizer, Sonnet 5.5 for Editor; (b) one model for all three; (c) whatever is already credentialed in n8n. *Recommendation: (a).* The Editor does the judgment work; the other two are high-volume. It also gives G1·C a real cost comparison.

**2. Fire time** *Recommendation: Monday 6 AM CT,* so the digest is ready for that week's posts.

**3. Sources** *Recommendation: RSS only for v1.* Add a search API only if a few weeks of digests come up thin.

## Questions for you

1. Are the Anthropic and Google Drive credentials already set up in your n8n?
2. Any must-include sources (newsletters, blogs, people) for the feed list?
3. Which Drive folder should the digest go in?
