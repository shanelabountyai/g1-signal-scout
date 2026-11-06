"""Typed hand-offs between the four agents (C2, D-25).

Researcher → list[Item] (the kept ones)
Summarizer → list[SummarizedItem]
Editor     → intro + list[DigestItem]
Writer     → list[PostDraft]
Everything the sink writes is one `Digest`.

The models carry the record; the agents only ever answer with an item's integer
id (D-14), so a URL or a title can never be rewritten by a model.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Tag = Literal["marketing-ops-ai", "agent-readiness", "other"]
Pillar = Literal["Scale", "Impact", "AI Integration", "MarTech"]


class Item(BaseModel):
    """One normalized feed entry, the shape G1·B's Normalize node emits plus the id the agents answer with."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=0)
    title: str
    url: str
    source: str
    date: str = ""  # ISO 8601 or "" when the feed gave none
    excerpt: str = ""


class Verdict(BaseModel):
    """The Researcher's answer for one item."""

    model_config = ConfigDict(extra="forbid")

    id: int
    keep: bool
    reason: str = ""


class Check(BaseModel):
    """One shared-layer check on one piece of text, as the digest shows it."""

    model_config = ConfigDict(extra="forbid")

    tool: Literal["claims_registry", "brand_policy", "evaluation"]
    target: Literal["summary", "post_angle", "post"]
    passed: bool
    detail: str = ""  # rule ids / statuses, one line
    action: Literal["kept", "flagged", "dropped"] = "kept"


class SummarizedItem(Item):
    summary: str
    tag: Tag
    checks: list[Check] = Field(default_factory=list)


class DigestItem(SummarizedItem):
    post_angle: str
    why: str = ""


class PostDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    pillar: Pillar
    anchor: str
    post: str
    checks: list[Check] = Field(default_factory=list)


class AgentUsage(BaseModel):
    """One model call, as logged to observability (C5)."""

    model_config = ConfigDict(extra="forbid")

    agent: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0  # from usage × G0's PRICES_PER_MTOK (D-28)
    sdk_cost_usd: float | None = None  # what the SDK itself reported, for comparison
    stop_reason: str | None = None
    duration_ms: int | None = None
    status: Literal["ok", "error", "skipped"] = "ok"
    log_id: str = ""  # observability row
    note: str = ""


class RunCost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    measured: bool  # False when the agents answered from recorded responses (D-30)
    usages: list[AgentUsage] = Field(default_factory=list)
    total_cost_usd: float = 0.0
    cap_usd: float = 10.0
    over_cap: bool = False


class Counts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feeds: int = 0
    raw: int = 0
    fresh: int = 0
    unseen: int = 0
    kept: int = 0
    summarized: int = 0
    dropped_by_claim_rule: int = 0
    picked: int = 0
    drafted: int = 0


class LayerInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    db_path: str = ""
    server_version: str = ""
    status: str = ""
    contracts: dict[str, str] = Field(default_factory=dict)
    calls: dict[str, int] = Field(default_factory=dict)  # tool → how many times this run called it


class Digest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week: str  # Monday of the ISO week, YYYY-MM-DD
    run_id: str
    run_at: str  # ISO 8601 UTC
    mode: Literal["live", "recorded"]
    intro: str = ""
    counts: Counts = Field(default_factory=Counts)
    items: list[DigestItem] = Field(default_factory=list)
    drafts: list[PostDraft] = Field(default_factory=list)
    cost: RunCost
    layer: LayerInfo = Field(default_factory=LayerInfo)

    @property
    def title(self) -> str:
        return f"Signal Scout — week of {self.week}"

    def drafted_ids(self) -> set[int]:
        return {d.id for d in self.drafts}

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
