# Fixtures

`feed-items.json` — 45 items (3 newest per feed in `config/feeds.md`, saved 2026-11-04) in the exact shape n8n's **RSS Read** node emits: `title`, `link`, `pubDate`, `isoDate`, `content` (truncated to 2000 chars), `contentSnippet`, `guid`, `creator`, `categories`. Regenerate with `python3 fixtures/make-fixtures.py [per_feed]`.

Used so the workflow runs end to end with no feed on the network (B2). The 7-day freshness filter in the workflow will drop old fixture items; when testing with these, regenerate them first or run the Normalize node with the freshness window widened.

How the workflow loads them is set in B3 and documented in `n8n/README.md`.

`recorded-responses.json` — what the four G1·C agents answer when no `ANTHROPIC_API_KEY` is present (D-30). **Hand-made in each agent's output schema from the 29 fresh items above, not a recording of a live model**; its `_about` and `recorded_live: false` say so, and usage is zero so the cost reads "not measured". `ANTHROPIC_API_KEY=… uv run scout --fixtures --record` replaces it with real responses.
