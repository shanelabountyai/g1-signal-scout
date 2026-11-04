# Feeds — G1 Weekly Signal Scout (v1, RSS only per D-12)

15 feeds. Every URL below was fetched and parsed on 2026-11-04 with `python3 config/check-feeds.py` (stdlib; re-run it any time a feed looks dead). Topic brief (D-2): AI adoption in marketing ops, and agent readiness. The Editor cuts the rest.

High-volume feeds (OpenAI, Shopify Engineering, HubSpot) return their whole archive; the workflow keeps only items from the last 7 days before the seen-items check, so the first run doesn't flood the Researcher.

## Marketing ops and martech

| Source | Feed URL | Why it's here |
|---|---|---|
| MarTech | https://martech.org/feed/ | Daily martech news; the stack-and-process view of AI adoption in marketing ops. |
| Marketing AI Institute | https://www.marketingaiinstitute.com/blog/rss.xml | Exactly the topic brief: AI adoption in marketing, with surveys and case studies. |
| Marketing Brew | https://www.marketingbrew.com/feed.xml | Mainstream marketing press; shows which AI stories reach the non-technical marketer. |
| HubSpot Marketing Blog | https://blog.hubspot.com/marketing/rss.xml | Largest marketing-ops vendor; what they publish is what mid-market teams adopt. High volume, mostly how-to; the Editor cuts. |
| Salesforce Blog | https://www.salesforce.com/blog/feed/ | Agentforce and Marketing Cloud; enterprise agent-readiness framing straight from the vendor. |
| Microsoft 365 Blog | https://www.microsoft.com/en-us/microsoft-365/blog/feed/ | Copilot adoption inside business ops; the "agents at work" narrative for enterprise buyers. |

## AI platforms and automation vendors

| Source | Feed URL | Why it's here |
|---|---|---|
| OpenAI News | https://openai.com/news/rss.xml | Model and agent product launches that marketing teams react to within the week. |
| Google AI (The Keyword) | https://blog.google/technology/ai/rss/ | Gemini, Workspace AI and ads-side AI; Google's adoption story for business users. |
| n8n Blog | https://blog.n8n.io/rss/ | Agent and automation patterns ops teams actually ship; also the tool G1·B runs on. |
| Zapier Blog | https://zapier.com/blog/feeds/latest/ | AI automation aimed at ops teams; a proxy for what no-code marketing ops is adopting. |

## Agent readiness, protocols and agentic commerce

| Source | Feed URL | Why it's here |
|---|---|---|
| Model Context Protocol Blog | https://blog.modelcontextprotocol.io/index.xml | The protocol layer agents connect through; readiness means being reachable by it. |
| Stripe Blog | https://stripe.com/blog/feed.rss | Agentic commerce and agent payments; where "agent-ready" meets money. |
| Shopify Engineering | https://shopify.engineering/blog.atom | Agentic commerce from the merchant platform side; catalog and checkout readiness. |
| Simon Willison's Weblog | https://simonwillison.net/atom/everything/ | Highest-signal running commentary on agent releases, including Anthropic's, which has no RSS feed of its own. |
| Latent Space | https://www.latent.space/feed | AI-engineering newsletter and podcast; agent architecture trends a month before they reach the trade press. |

## Checked and left out

- **Anthropic news** — no RSS feed at any of the usual paths (404). Covered indirectly by Simon Willison and Latent Space. Revisit if a feed appears.
- **chiefmartec.com** — resolves, but the newest post was May 2026; too quiet for a weekly scout.
- **Hugging Face blog**, **Cloudflare blog**, **Sequoia**, **Google Developers blog** — resolve, but mostly research or infrastructure; off the topic brief.
- **CMSWire**, **LangChain blog**, **Shopify.com blog**, **PayPal newsroom** — URL returns something, but not parseable RSS/Atom (HTML page or malformed XML).
- **The Batch (deeplearning.ai)**, **a16z**, **Adobe blog**, **Braze**, **Klaviyo**, **Gartner newsroom** — 404, 403 or timeout.
