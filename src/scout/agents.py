"""The four agents and their hand-offs (C3, D-24, D-25, D-32).

Each agent is one model call. The join back to the original records is by
integer id, unknown ids are dropped (D-14), and the shared layer is called by
this module — not by the model — after every agent:

  Researcher  → observability
  Summarizer  → observability; per item: evaluation(claim_rule_v1) vs the source item (fail = DROPPED),
                claims_registry on the summary (flag)
  Editor      → observability; per pick: brand_policy(post_angle), evaluation(post_angle_v1),
                evaluation(claim_rule_v1) vs the source item, claims_registry (all flag)
  Writer      → observability; per draft: brand_policy(linkedin), evaluation(claim_rule_v1) vs pick+record,
                claims_registry (all flag)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from scout.layer import Layer
from scout.llm import CallResult, ModelCaller
from scout.models import AgentUsage, Check, DigestItem, Item, PostDraft, SummarizedItem, Verdict
from scout.prompts import EDITOR, RESEARCHER, SHANE_RECORD, SUMMARIZER, WRITER, AgentSpec


class OverCap(RuntimeError):
    """observability reported over_cap; no further model call is made (D-28)."""


class AgentFailed(RuntimeError):
    """An agent returned nothing usable (same stops as G1·B's After-* nodes)."""


@dataclass
class Runner:
    layer: Layer
    caller: ModelCaller
    run_id: str
    judge: str = "deterministic"
    usages: list[AgentUsage] = field(default_factory=list)
    over_cap: bool = False
    cap_usd: float = 10.0
    total_cost_usd: float = 0.0

    # -- one model call, logged -----------------------------------------------------

    async def ask(self, spec: AgentSpec, user_text: str, step: str) -> CallResult:
        if self.over_cap:
            raise OverCap(f"run {self.run_id} is over the ${self.cap_usd:.2f} cap; {spec.name} not called")
        try:
            r = await self.caller.call(spec, user_text)
        except Exception as e:
            self.layer.log_call(run_id=self.run_id, agent=spec.name, step=step, model=spec.model, input_tokens=0, output_tokens=0,
                                cost_usd=0.0, status="error", note=str(e)[:400])
            self.usages.append(AgentUsage(agent=spec.name, model=spec.model, status="error", note=str(e)[:400]))
            raise
        cost = self.layer.cost_usd(r.model, r.billed_input_tokens, r.output_tokens) if self.caller.measured else 0.0
        note = f"stop={r.stop_reason}; sdk_cost={r.sdk_cost_usd}; cache_read={r.cache_read_tokens}; cache_write={r.cache_creation_tokens}; via={self.caller.name}"
        logged = self.layer.log_call(run_id=self.run_id, agent=spec.name, step=step, model=r.model, input_tokens=r.billed_input_tokens,
                                     output_tokens=r.output_tokens, cost_usd=cost, status="ok", duration_ms=r.duration_ms, note=note)
        if logged.ok and logged.run_total is not None:
            self.total_cost_usd = logged.run_total.cost_usd
            self.cap_usd = logged.cap_usd
            self.over_cap = logged.over_cap
        self.usages.append(AgentUsage(agent=spec.name, model=r.model, input_tokens=r.billed_input_tokens, output_tokens=r.output_tokens,
                                      cost_usd=cost, sdk_cost_usd=r.sdk_cost_usd, stop_reason=r.stop_reason, duration_ms=r.duration_ms,
                                      status="ok", log_id=logged.log_id if logged.ok else "", note=note))
        return r

    # -- checks ---------------------------------------------------------------------

    def _claim_check(self, text: str, context: str, target: str) -> tuple[Check, Check]:
        ev = self.layer.evaluate("claim_rule_v1", text, context, self.run_id, judge=self.judge)
        if ev.ok:
            failed = [s.criterion for s in ev.scores if s.score < 1.0]
            ev_check = Check(tool="evaluation", target=target, passed=ev.passed, detail="claim_rule_v1" + (": " + ", ".join(failed) if failed else " ok"))
        else:
            ev_check = Check(tool="evaluation", target=target, passed=False, detail=f"claim_rule_v1 refused: {ev.error.code if ev.error else '?'}", action="flagged")
        cr = self.layer.check_claims(text=text)
        if cr.ok:
            bad = [f"{r.status}: {r.claim[:60]}" for r in cr.results if r.status != "supported"]
            cr_check = Check(tool="claims_registry", target=target, passed=not any(r.status == "unsupported" for r in cr.results),
                             detail="; ".join(bad) if bad else (f"{len(cr.results)} claim(s) supported" if cr.results else "no quantitative claim"),
                             action="flagged" if any(r.status == "unsupported" for r in cr.results) else "kept")
        else:
            cr_check = Check(tool="claims_registry", target=target, passed=True, detail=f"refused: {cr.error.code if cr.error else '?'}")
        return ev_check, cr_check

    def _brand_check(self, text: str, channel: str, target: str) -> Check:
        bp = self.layer.check_brand(text, channel)
        if not bp.ok:
            return Check(tool="brand_policy", target=target, passed=False, detail=f"refused: {bp.error.code if bp.error else '?'}", action="flagged")
        if bp.passed:
            return Check(tool="brand_policy", target=target, passed=True, detail=f"{bp.rules_checked} rules ok")
        return Check(tool="brand_policy", target=target, passed=False, action="flagged",
                     detail="; ".join(f"{v.rule_id} ({v.excerpt.strip()}) → {v.fix}" for v in bp.violations if v.severity == "fail"))

    def _angle_eval(self, angle: str, target: str = "post_angle") -> Check:
        ev = self.layer.evaluate("post_angle_v1", angle, None, self.run_id, judge=self.judge)
        if not ev.ok:
            return Check(tool="evaluation", target=target, passed=False, detail=f"post_angle_v1 refused: {ev.error.code if ev.error else '?'}", action="flagged")
        weak = [f"{s.criterion}={s.score:g}" for s in ev.scores if s.score < 1.0]
        return Check(tool="evaluation", target=target, passed=ev.passed, action="kept" if ev.passed else "flagged",
                     detail=f"post_angle_v1 {ev.total:g}" + (": " + ", ".join(weak) if weak else " ok"))

    # -- the agents -------------------------------------------------------------------

    @staticmethod
    def _context(item: Item) -> str:
        return f"{item.title}\n{item.url}\n{item.source} {item.date}\n{item.excerpt}"

    async def research(self, items: list[Item]) -> list[Item]:
        if not items:
            return []
        user = "Week items as JSON:\n" + json.dumps([i.model_dump() for i in items], ensure_ascii=False)
        r = await self.ask(RESEARCHER, user, step="screen")
        by_id = {i.id: i for i in items}
        kept: list[Item] = []
        for raw in r.parsed.get("items", []):
            try:
                v = Verdict(**raw)
            except (ValidationError, TypeError):
                continue
            if v.keep and v.id in by_id and by_id[v.id] not in kept:
                kept.append(by_id[v.id])
        if not kept:
            raise AgentFailed(f"Researcher kept 0 of {len(items)} items")
        return kept

    async def summarize(self, kept: list[Item]) -> tuple[list[SummarizedItem], int]:
        """Returns the summarized items that passed the claim rule and how many were dropped by it."""
        user = "Items as JSON:\n" + json.dumps([i.model_dump() for i in kept], ensure_ascii=False)
        r = await self.ask(SUMMARIZER, user, step="summarize")
        by_id = {i.id: i for i in kept}
        out: list[SummarizedItem] = []
        dropped = 0
        seen_ids: set[int] = set()
        for raw in r.parsed.get("items", []):
            rec = by_id.get(raw.get("id")) if isinstance(raw, dict) else None
            if rec is None or rec.id in seen_ids:
                continue  # claim rule: unknown id, dropped
            try:
                s = SummarizedItem(**rec.model_dump(), summary=str(raw.get("summary", "")), tag=raw.get("tag"))
            except ValidationError:
                continue
            seen_ids.add(rec.id)
            ev_check, cr_check = self._claim_check(s.summary, self._context(rec), "summary")
            if not ev_check.passed:
                ev_check.action = "dropped"
                dropped += 1
                continue
            s.checks = [ev_check, cr_check]
            out.append(s)
        if not out:
            raise AgentFailed("Summarizer returned 0 known items" + (f" ({dropped} dropped by the claim rule)" if dropped else ""))
        return out, dropped

    async def edit(self, summarized: list[SummarizedItem]) -> tuple[str, list[DigestItem]]:
        user = "Summarized items as JSON:\n" + json.dumps([s.model_dump(exclude={"checks"}) for s in summarized], ensure_ascii=False)
        r = await self.ask(EDITOR, user, step="pick")
        by_id = {s.id: s for s in summarized}
        picks: list[DigestItem] = []
        for raw in r.parsed.get("picks", []):
            rec = by_id.get(raw.get("id")) if isinstance(raw, dict) else None
            if rec is None or any(p.id == rec.id for p in picks):
                continue
            angle = str(raw.get("post_angle", "")).strip()
            d = DigestItem(**rec.model_dump(), post_angle=angle, why=str(raw.get("why", "")))
            ev_check, cr_check = self._claim_check(angle, self._context(rec) + "\n" + rec.summary, "post_angle")
            if not ev_check.passed:
                ev_check.action = "flagged"
            d.checks = list(rec.checks) + [self._brand_check(angle, "post_angle", "post_angle"), self._angle_eval(angle), ev_check, cr_check]
            picks.append(d)
        if not picks:
            raise AgentFailed("Editor picked 0 known items")
        return str(r.parsed.get("intro", "")), picks

    async def write(self, picks: list[DigestItem]) -> list[PostDraft]:
        for_writer = [{"id": p.id, "title": p.title, "source": p.source, "summary": p.summary, "tag": p.tag, "post_angle": p.post_angle} for p in picks]
        user = "This week's picks as JSON:\n" + json.dumps(for_writer, ensure_ascii=False)
        r = await self.ask(WRITER, user, step="draft")
        by_id = {p.id: p for p in picks}
        drafts: list[PostDraft] = []
        for raw in r.parsed.get("drafts", []):
            rec = by_id.get(raw.get("id")) if isinstance(raw, dict) else None
            if rec is None or not raw.get("post"):
                continue
            try:
                d = PostDraft(id=rec.id, pillar=raw.get("pillar"), anchor=str(raw.get("anchor", "")), post=str(raw["post"]))
            except ValidationError:
                continue
            context = self._context(rec) + "\n" + rec.summary + "\n" + rec.post_angle + "\n" + SHANE_RECORD
            ev_check, cr_check = self._claim_check(d.post, context, "post")
            if not ev_check.passed:
                ev_check.action = "flagged"
            d.checks = [self._brand_check(d.post, "linkedin", "post"), ev_check, cr_check]
            drafts.append(d)
        return drafts


def flagged(checks: list[Check]) -> list[Check]:
    return [c for c in checks if c.action == "flagged"]


def summarize_checks(checks: list[Check]) -> dict[str, Any]:
    return {"total": len(checks), "flagged": len(flagged(checks)), "by_tool": {t: sum(1 for c in checks if c.tool == t) for t in ("claims_registry", "brand_policy", "evaluation")}}
