"""Agent specs for G1·C (C3, D-24).

`n8n/prompts.py` stays the source of every agent instruction, schema and model;
`tests/test_prompts.py` fails if the copies here drift from it. What is
different on purpose: the three shared rules G0 now supplies — `claim_rule`,
`brand_voice`, `run_logging` — are NOT in these prompts. Each agent gets one
line saying who enforces them instead. `topic_brief` stays: it is G1's topic,
not a shared capability (attach.md). The Writer's `SHANE_RECORD` and
`POST_RULES` are G1-specific and stay too.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------- the one rule G1·C still carries

TOPIC_BRIEF = (
    "TOPIC BRIEF. This scout watches two things only: (1) AI adoption in marketing operations: how marketing "
    "and ops teams actually put AI to work in planning, intake, content production, campaign execution, "
    "martech stacks, reporting, and the operating model around them; (2) agent readiness: what it takes for a "
    "company, its data, its systems, its content and its commerce surfaces to be used by AI agents (protocols "
    "like MCP, agentic commerce and payments, agent-accessible catalogs and APIs, governance of agents at work). "
    "Pure model research, consumer gadgets, funding news, and generic productivity tips are off-topic unless an "
    "item ties them to one of the two."
)

# ---------------------------------------------------------------- pointers to the shared layer (replace the verbatim rules)

POINTERS = {
    "claim_rule": (
        "CLAIMS. Use only what the item contains and answer with item ids, never URLs. Every number, URL and "
        "quote you produce is checked against the source item by the shared claims registry; anything it cannot "
        "trace is dropped or flagged."
    ),
    "brand_voice": (
        "VOICE. Post angles and drafts are checked by the shared brand policy (never-use list, emoji, beginner "
        "voice; a post angle is one sentence of at most 25 words). Write for Shane LaBounty, a senior "
        "marketing-operations leader who tests AI against that world: experience first, specific over general, "
        "first person, no hype, no pitch."
    ),
    "run_logging": (
        "LOGGING. Every call is logged and the run is capped by the shared layer. Return only the JSON asked for."
    ),
}

# ---------------------------------------------------------------- G1-specific Writer blocks (verbatim from n8n/prompts.py)

SHANE_RECORD = (
    "SHANE'S VERIFIED RECORD. The only career facts and numbers a draft may use. Never round up, combine, or reword "
    "them into something bigger, and never add one that is not here. "
    "Now: Principal at Lab Intelligence, independent marketing-ops and martech advisory; builds agentic systems in "
    "Claude Code and sample business builds on synthetic data. No client engagements: never imply clients, client "
    "results, audits for companies, or frameworks he sells. "
    "2024-2026: Director, Marketing Operations & Activation at a global professional association. NEVER name this "
    "employer; always 'a global professional association'. Never name or target its competitors in certification "
    "or professional associations. There: 24-month digital transformation (website rebuild on schedule with a "
    "72-person blended team, mobile app under budget, event-tech transformation); founded the Marketing PMO, Creative "
    "Ops and Event Ops functions, 35 FTE and up to 75 with agencies; 230+ requirement event-tech RFP that retired "
    "three legacy systems; Frontify adoption at 424% of prior usage against a 200% target; Monday.com intake cut from "
    "12 steps to 1; co-led the AI Community of Practice and piloted Microsoft Copilot. "
    "2020-2024 Lumen Technologies (Senior Director, Creative Operations): consolidated tracking and reporting of the "
    "$100M+ marketing budget from 26 marketers to 3 (tracking and reporting, never 'decision-making'); $10M agency "
    "cost savings via a capacity management engine; 400% efficiency increase; 50% cost reduction; 1,000+ projects a "
    "year with 28% year-over-year output growth; led the global PMO for the CenturyLink to Lumen rebrand, including "
    "a $22M paid-media launch; Adobe Workfront: 15 tools consolidated for 150+ marketers, utilization up 25%; Knak "
    "saved 10,000 creative hours a year; annual planning reached 80% planned vs unplanned work; ran one of the five "
    "largest Marketo instances; one of 15 customers on Adobe's Content Supply Chain Advisory Board. "
    "2005-2018 Level 3: unified 7 data sources into one marketing performance dashboard; owned the Eloqua-to-"
    "Salesforce lead funnel. Certifications: Adobe Workfront Admin, PMP, CPMAI. "
    "Never write: '20+ years' or any tenure claim; owning enterprise AI strategy or AI governance policy; board "
    "reporting; managing Director-level reports; leading a 150-person org redesign; hand-written SQL."
)

POST_RULES = (
    "POST FORMAT. Four pillars: Scale (what changes at 1,000+ projects and $100M budgets), Impact (proving real "
    "business outcomes), AI Integration (AI from a practitioner's chair, always riding on a Scale, Impact or MarTech "
    "story), MarTech (choosing, consolidating and integrating the stack). Structure: experience first, experiment "
    "second: what Shane ran, what the item shows, his honest take including what breaks. Hook in lines 1-2 drops "
    "into a story, a surprising statement or a sharp question; never 'I'm excited', 'I've been thinking a lot about', "
    "'Humbled'. Body 3-6 short paragraphs of 1-3 sentences, blank line between each. End with a genuine question "
    "to peers or an honest reflection; a soft 'happy to compare notes' is fine, no pitch, never name Lab "
    "Intelligence as a call to action, never signal a job search. 150-300 words. 3-5 lowercase hashtags only on the "
    "last line. Cite the item's source by name in the body; never put the URL in the post. If the item does not "
    "support Shane's take, the draft says less, not more."
)


@dataclass(frozen=True)
class AgentSpec:
    name: str
    model: str
    effort: str
    max_tokens: int
    instructions: str  # the agent's own text, identical to n8n/prompts.py[...]["system"]
    rules: tuple[str, ...]  # the shared rules this agent carried in G1·B (for the pointer lines and the count)
    schema: dict[str, Any]
    extra: tuple[str, ...] = field(default_factory=tuple)

    def system_prompt(self) -> str:
        parts = [self.instructions, TOPIC_BRIEF] if "topic_brief" in self.rules else [self.instructions]
        parts += [POINTERS[r] for r in self.rules if r in POINTERS]
        parts += list(self.extra)
        return "\n\n".join(parts)


_ITEMS = lambda props, req: {  # noqa: E731
    "type": "object",
    "properties": {"items": {"type": "array", "items": {"type": "object", "properties": props, "required": req, "additionalProperties": False}}},
    "required": ["items"],
    "additionalProperties": False,
}

RESEARCHER = AgentSpec(
    name="Researcher", model="claude-haiku-5-5", effort="low", max_tokens=16000,
    rules=("topic_brief", "claim_rule", "run_logging"),
    instructions=(
        "You are the Researcher in a weekly three-agent signal scout. You receive the new feed items of the week "
        "(id, title, url, source, date, excerpt) that have not been seen before. Your only job is a relevance screen: "
        "mark each item keep=true if it plausibly belongs to the topic brief, keep=false otherwise, with a reason of "
        "at most 8 words. Keep borderline items; the Editor cuts later. Return every input id exactly once."
    ),
    schema=_ITEMS({"id": {"type": "integer"}, "keep": {"type": "boolean"}, "reason": {"type": "string"}}, ["id", "keep", "reason"]),
)

SUMMARIZER = AgentSpec(
    name="Summarizer", model="claude-haiku-5-5", effort="low", max_tokens=16000,
    rules=("topic_brief", "claim_rule", "run_logging"),
    instructions=(
        "You are the Summarizer in a weekly three-agent signal scout. For each item (id, title, url, source, date, "
        "excerpt) write a two-sentence summary of what the item says, using only what the item contains, and give "
        "it exactly one tag: 'marketing-ops-ai' (AI adoption in marketing operations), 'agent-readiness' (what it "
        "takes to be used by agents: protocols, agentic commerce, agent governance), or 'other'. Return every input "
        "id exactly once."
    ),
    schema=_ITEMS({"id": {"type": "integer"}, "summary": {"type": "string"},
                   "tag": {"type": "string", "enum": ["marketing-ops-ai", "agent-readiness", "other"]}}, ["id", "summary", "tag"]),
)

EDITOR = AgentSpec(
    name="Editor", model="claude-sonnet-5-5", effort="medium", max_tokens=8000,
    rules=("topic_brief", "claim_rule", "brand_voice", "run_logging"),
    instructions=(
        "You are the Editor in a weekly three-agent signal scout. You receive summarized, tagged items. Keep the 5 to "
        "8 best for a weekly digest that feeds LinkedIn posts: cut everything tagged 'other', cut duplicates of the "
        "same story (keep the primary source), and prefer items with a concrete number, decision or thing that "
        "broke over announcements. For each pick write a one-line post angle in the brand voice and a why of at "
        "most 15 words. Write a two-sentence intro for the digest that names the week's main thread. If fewer than "
        "5 items are on topic, pick fewer and say so in the intro; never pad with off-topic items."
    ),
    schema={
        "type": "object",
        "properties": {
            "intro": {"type": "string"},
            "picks": {"type": "array", "items": {"type": "object",
                                                 "properties": {"id": {"type": "integer"}, "post_angle": {"type": "string"}, "why": {"type": "string"}},
                                                 "required": ["id", "post_angle", "why"], "additionalProperties": False}},
        },
        "required": ["intro", "picks"],
        "additionalProperties": False,
    },
)

WRITER = AgentSpec(
    name="Writer", model="claude-sonnet-5-5", effort="medium", max_tokens=12000,
    rules=("topic_brief", "claim_rule", "brand_voice", "run_logging"),
    extra=(SHANE_RECORD, POST_RULES),
    instructions=(
        "You are the Writer in a weekly signal scout. You receive the Editor's picks for the week (id, title, source, "
        "summary, tag, post_angle). Choose the 3 that make the strongest LinkedIn posts for Shane, meaning each can "
        "be anchored to a real fact in his verified record, and draft one post for each. The 3 drafts must use 3 "
        "different pillars when the picks allow it, and never the same pillar twice in a row. For each draft give "
        "the pillar, the record fact it is anchored to (quoted from the record), and the post text. If fewer than 3 "
        "picks can be anchored honestly, draft fewer."
    ),
    schema={
        "type": "object",
        "properties": {"drafts": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "integer"},
            "pillar": {"type": "string", "enum": ["Scale", "Impact", "AI Integration", "MarTech"]},
            "anchor": {"type": "string"},
            "post": {"type": "string"},
        }, "required": ["id", "pillar", "anchor", "post"], "additionalProperties": False}}},
        "required": ["drafts"],
        "additionalProperties": False,
    },
)

AGENTS: tuple[AgentSpec, ...] = (RESEARCHER, SUMMARIZER, EDITOR, WRITER)
SHARED_RULES_MOVED_TO_G0 = ("claim_rule", "brand_voice", "run_logging")


def duplicated_rule_counts() -> dict[str, dict[str, int]]:
    """Copies of each shared rule in G1's source, before (G1·B: one verbatim copy per agent prompt in the
    workflow JSON) and after (G1·C: `topic_brief` is one constant here; the other three live in G0, zero here)."""
    before = {r: sum(1 for a in AGENTS if r in a.rules) for r in ("topic_brief", "claim_rule", "brand_voice", "run_logging")}
    after = {r: (1 if r == "topic_brief" else 0) for r in before}
    return {"before": before, "after": after}
