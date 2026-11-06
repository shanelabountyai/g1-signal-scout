"""Cost log per run (C5, D-28): what each agent cost, from the response usage at G0's prices.

Written to out/<week>/cost.json and printed as the Markdown row block that goes into docs/run-log.md.
G1·C has no price table of its own; `Layer.cost_usd` reads G0's `evaluation.PRICES_PER_MTOK`.
"""

from __future__ import annotations

import json
from pathlib import Path

from scout.layer import Layer
from scout.models import Digest


def cost_record(d: Digest) -> dict:
    return {
        "run_id": d.run_id, "week": d.week, "run_at": d.run_at, "mode": d.mode, "measured": d.cost.measured,
        "prices_per_mtok": {m: {"in": p[0], "out": p[1]} for m, p in Layer.prices_per_mtok().items()},
        "agents": [u.model_dump() for u in d.cost.usages],
        "total_cost_usd": d.cost.total_cost_usd if d.cost.measured else None,
        "cap_usd": d.cost.cap_usd, "over_cap": d.cost.over_cap,
        "counts": d.counts.model_dump(),
    }


def write_cost(d: Digest, out_dir: Path) -> Path:
    folder = Path(out_dir) / d.week
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / "cost.json"
    p.write_text(json.dumps(cost_record(d), indent=2) + "\n", encoding="utf-8")
    return p


def run_log_rows(d: Digest) -> str:
    """Rows in docs/run-log.md's table shape: Date (UTC) | Exec | Agent | Model | In | Out | Cost | Result."""
    rows = []
    for u in d.cost.usages:
        cost = f"${u.cost_usd:.4f}" if d.cost.measured else "not measured"
        rows.append(f"| {d.run_at[:16].replace('T', ' ')} | {d.run_id} | {u.agent} | {u.model} | {u.input_tokens:,} | {u.output_tokens:,} | {cost} | {u.status}; {d.mode} |")
    total = f"${d.cost.total_cost_usd:.4f}" if d.cost.measured else "not measured"
    rows.append(f"| | | **G1·C total** | | | | **{total}** | {d.counts.picked} picked, {d.counts.drafted} drafted |")
    return "\n".join(rows)
