"""One run of the scout (C1–C5). The order is G1·B's (D-26):

  health → feeds → normalize → drop seen → Researcher → Summarizer → Editor → Writer
  → (every model call already logged to observability) → sink.write
  → on failure: observability error row, RunFailed, NOTHING marked seen (AC 3)
  → measurement digest.published → mark seen → measurement run.completed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scout import feeds as feedmod
from scout.agents import AgentFailed, OverCap, Runner
from scout.config import FIXTURES_JSON, Feed
from scout.layer import Layer
from scout.llm import ModelCaller
from scout.models import Counts, Digest, Item, LayerInfo, RunCost
from scout.seen import SeenStore
from scout.sinks import DigestSink, SinkError, WriteResult


class RunFailed(RuntimeError):
    """The run stopped before items were marked seen. `stage` says where."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(f"{stage}: {message}")
        self.stage = stage


@dataclass
class RunReport:
    run_id: str
    week: str
    digest: Digest | None
    write: WriteResult | None
    marked_seen: int
    counts: Counts
    unseen: list[Item] = field(default_factory=list)
    dry_run: bool = False
    layer_calls: dict[str, int] = field(default_factory=dict)
    health: dict[str, Any] = field(default_factory=dict)


def week_monday(now: datetime) -> str:
    monday = now - timedelta(days=(now.weekday()) % 7)
    return monday.date().isoformat()


def make_run_id(now: datetime) -> str:
    return f"g1c-{week_monday(now)}-{now.strftime('%H%M%S')}"


def gather_items(feed_list: list[Feed], fixtures: Path | None, as_of: datetime | None, on_feed_error=None) -> tuple[list[Item], int, datetime | None]:
    """Raw items from fixtures or the live feeds, normalized. Returns (items, raw_count, as_of used)."""
    if fixtures is not None:
        raws = feedmod.load_fixtures(fixtures)
        as_of = as_of or feedmod.newest_date(raws)  # D-32: saved fixtures do not go stale
    else:
        raws = feedmod.fetch_all(feed_list, on_error=on_feed_error)
    return feedmod.normalize(raws, feed_list, as_of=as_of), len(raws), as_of


async def run_scout(
    *,
    layer: Layer,
    caller: ModelCaller,
    seen: SeenStore,
    sink: DigestSink,
    feed_list: list[Feed],
    fixtures: Path | None = FIXTURES_JSON,
    as_of: datetime | None = None,
    now: datetime | None = None,
    dry_run: bool = False,
    judge: str = "deterministic",
    log=print,
) -> RunReport:
    now = now or datetime.now(UTC)
    run_id = make_run_id(now)
    week = week_monday(now)
    counts = Counts(feeds=len(feed_list))

    # 1. the layer must be up (attach.md step 3)
    h = layer.require_healthy()
    health_info = {"status": h.status, "db_path": h.db_path, "server_version": h.server_version, "seeds": h.seeds, "contracts": h.contracts}
    log(f"[{run_id}] shared layer {h.status}: g0-shared-layer {h.server_version}, db {h.db_path}, seeds {h.seeds}")

    # 2. items
    def on_feed_error(f: Feed, e: Exception) -> None:
        log(f"[{run_id}] feed failed, skipped: {f.source} ({e})")
        layer.log_call(run_id=run_id, agent="feeds", step="fetch", model=None, input_tokens=0, output_tokens=0, cost_usd=0.0, status="error", note=f"{f.source}: {e}"[:400])

    fresh, raw_count, used_as_of = gather_items(feed_list, fixtures, as_of, on_feed_error)
    counts.raw, counts.fresh = raw_count, len(fresh)
    unseen = feedmod.renumber(seen.drop_seen(fresh))
    counts.unseen = len(unseen)
    log(f"[{run_id}] {raw_count} raw → {len(fresh)} fresh (as of {used_as_of.date() if used_as_of else 'now'}) → {len(unseen)} unseen")

    if dry_run:
        layer.record("run.dry_run", {"week": week, "fresh": counts.fresh, "unseen": counts.unseen, "feeds": counts.feeds}, run_id)
        return RunReport(run_id=run_id, week=week, digest=None, write=None, marked_seen=0, counts=counts, unseen=unseen, dry_run=True,
                         layer_calls=dict(layer.calls), health=health_info)

    layer.record("run.started", {"week": week, "fresh": counts.fresh, "unseen": counts.unseen, "mode": "live" if caller.measured else "recorded"}, run_id)
    if not unseen:
        log(f"[{run_id}] nothing new this week; no model call, nothing written")
        layer.record("run.empty", {"week": week}, run_id)
        return RunReport(run_id=run_id, week=week, digest=None, write=None, marked_seen=0, counts=counts, layer_calls=dict(layer.calls), health=health_info)

    # 3. the four agents, each logged to observability as it happens
    runner = Runner(layer=layer, caller=caller, run_id=run_id, judge=judge)
    try:
        kept = await runner.research(unseen)
        counts.kept = len(kept)
        log(f"[{run_id}] Researcher kept {len(kept)} of {len(unseen)}")
        summarized, dropped = await runner.summarize(kept)
        counts.summarized, counts.dropped_by_claim_rule = len(summarized), dropped
        log(f"[{run_id}] Summarizer: {len(summarized)} summarized, {dropped} dropped by the claim rule")
        intro, picks = await runner.edit(summarized)
        counts.picked = len(picks)
        log(f"[{run_id}] Editor picked {len(picks)}")
        drafts = await runner.write(picks)
        counts.drafted = len(drafts)
        log(f"[{run_id}] Writer drafted {len(drafts)}")
    except (OverCap, AgentFailed) as e:
        layer.record("run.failed", {"week": week, "stage": "agents", "error": str(e)[:300]}, run_id)
        raise RunFailed("agents", str(e)) from e
    except Exception as e:  # model/SDK error already logged by Runner.ask
        layer.record("run.failed", {"week": week, "stage": "agents", "error": str(e)[:300]}, run_id)
        raise RunFailed("agents", str(e)) from e

    digest = Digest(
        week=week, run_id=run_id, run_at=now.isoformat(timespec="seconds"), mode="live" if caller.measured else "recorded",
        intro=intro, counts=counts, items=picks, drafts=drafts,
        cost=RunCost(run_id=run_id, measured=caller.measured, usages=runner.usages, total_cost_usd=runner.total_cost_usd,
                     cap_usd=runner.cap_usd, over_cap=runner.over_cap),
        layer=LayerInfo(db_path=h.db_path, server_version=h.server_version, status=h.status, contracts=h.contracts, calls=dict(layer.calls)),
    )

    # 4. write, then (and only then) mark seen — AC 3
    try:
        write = sink.write(digest)
    except SinkError as e:
        layer.log_call(run_id=run_id, agent="sink", step=f"write:{sink.name}", model=None, input_tokens=0, output_tokens=0,
                       cost_usd=0.0, status="error", note=str(e)[:400])
        layer.record("run.failed", {"week": week, "stage": "sink", "sink": sink.name, "error": str(e)[:300]}, run_id)
        log(f"[{run_id}] sink {sink.name} FAILED: {e}; nothing marked seen")
        raise RunFailed("sink", str(e)) from e
    log(f"[{run_id}] digest written by {write.sink}: {write.location}")

    layer.record("digest.published", {"week": week, "items": len(picks), "drafts": len(drafts), "sink": write.sink,
                                      "cost_usd": digest.cost.total_cost_usd if digest.cost.measured else None}, run_id)
    marked = seen.mark_seen(picks, run_id, at=now)
    log(f"[{run_id}] marked {marked} items seen (seen_items now {seen.count()})")
    layer.record("run.completed", {"week": week, "picked": len(picks), "drafted": len(drafts), "marked_seen": marked,
                                   "cost_usd": digest.cost.total_cost_usd if digest.cost.measured else None,
                                   "layer_calls": dict(layer.calls)}, run_id)
    return RunReport(run_id=run_id, week=week, digest=digest, write=write, marked_seen=marked, counts=counts, unseen=unseen,
                     layer_calls=dict(layer.calls), health=health_info)
