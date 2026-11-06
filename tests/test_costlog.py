"""C5: cost per agent from usage at G0's prices; no second price table in G1·C (D-28)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from shared_layer.capabilities.evaluation import PRICES_PER_MTOK

from scout.costlog import cost_record, run_log_rows, write_cost
from scout.layer import Layer
from scout.models import AgentUsage, Counts, Digest, RunCost

SRC = Path(__file__).resolve().parents[1] / "src" / "scout"


def _digest(measured: bool) -> Digest:
    usages = [AgentUsage(agent="Researcher", model="claude-haiku-5-5", input_tokens=17_275, output_tokens=3_414, cost_usd=Layer.cost_usd("claude-haiku-5-5", 17_275, 3_414)),
              AgentUsage(agent="Editor", model="claude-sonnet-5-5", input_tokens=8_525, output_tokens=765, cost_usd=Layer.cost_usd("claude-sonnet-5-5", 8_525, 765))]
    return Digest(week="2026-11-02", run_id="g1c-2026-11-02-000000", run_at="2026-11-06T00:00:00+00:00", mode="live" if measured else "recorded",
                  counts=Counts(picked=7, drafted=3),
                  cost=RunCost(run_id="g1c-2026-11-02-000000", measured=measured, usages=usages, total_cost_usd=round(sum(u.cost_usd for u in usages), 6)))


def test_prices_come_from_g0_only():
    assert Layer.prices_per_mtok() == PRICES_PER_MTOK
    # G1·B's exec 4 numbers reproduce G1·B's logged costs at the same prices
    assert round(Layer.cost_usd("claude-haiku-5-5", 17_275, 3_414), 4) == 0.0034
    assert round(Layer.cost_usd("claude-sonnet-5-5", 8_525, 765), 4) == 0.0247
    assert Layer.cost_usd("unknown-model", 1000, 1000) == 0.0
    # no literal price table anywhere in G1·C's source (the D-8 numbers appear only in G0)
    for py in SRC.glob("*.py"):
        text = py.read_text()
        assert not re.search(r'"claude-(haiku|sonnet|opus)-5-5"\s*:\s*[\[(]\s*\d', text), f"{py.name} carries a price table"


def test_cost_record_and_run_log_rows_measured(tmp_path):
    d = _digest(measured=True)
    p = write_cost(d, tmp_path)
    rec = json.loads(p.read_text())
    assert p == tmp_path / "2026-11-02" / "cost.json"
    assert rec["measured"] is True and rec["total_cost_usd"] == d.cost.total_cost_usd and rec["cap_usd"] == 10.0
    assert rec["prices_per_mtok"]["claude-haiku-5-5"] == {"in": 0.10, "out": 0.50}
    rows = run_log_rows(d)
    assert "| Researcher | claude-haiku-5-5 | 17,275 | 3,414 | $0.0034 |" in rows
    assert "**G1·C total**" in rows and "$0.0281" in rows


def test_cost_record_unmeasured_says_so(tmp_path):
    d = _digest(measured=False)
    rec = cost_record(d)
    assert rec["total_cost_usd"] is None and rec["measured"] is False
    assert "not measured" in run_log_rows(d)
