"""The shared layer (G0·C), called in-process (D-23, D-30).

One thin adapter so every capability call in the scout goes through one place
and is counted. Every method returns the capability's typed `Output`; a
`Refusal` becomes `Output(ok=False, error=…)` exactly as G0's MCP server does,
so `ok: false` is a result the caller reads, never an exception
(docs/attach.md, "Rules for every consumer").
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from typing import Any

from pydantic import ValidationError
from shared_layer.capabilities import brand_policy, claims_registry, evaluation, health, measurement, observability
from shared_layer.contracts import contract_versions
from shared_layer.errors import Refusal, ToolError
from shared_layer.storage import Database, open_database


class LayerDegraded(RuntimeError):
    """health reported `degraded`; the run must not start (attach.md step 3)."""


class Layer:
    def __init__(self, db_path: str | None = None, db: Database | None = None) -> None:
        self.db = db or open_database(db_path)
        self.calls: Counter[str] = Counter()

    def close(self) -> None:
        self.db.close()

    # -- the one way a call is made ------------------------------------------

    def _run(self, module: Any, **kwargs: Any) -> Any:
        self.calls[module.TOOL] += 1
        Output = module.Output
        try:
            inp = module.Input(**kwargs)
        except ValidationError as e:
            return Output(ok=False, error=ToolError(code="INVALID_ARGUMENT", message=str(e).splitlines()[0]))
        try:
            return module.run(self.db, inp)
        except Refusal as r:
            return Output(ok=False, error=r.envelope)
        except sqlite3.Error as e:
            return Output(ok=False, error=ToolError(code="STORAGE_ERROR", message=f"SQLite refused the operation: {e}"))

    # -- capabilities ------------------------------------------------------------

    def health(self) -> health.Output:
        self.calls[health.TOOL] += 1
        return health.run(self.db, health.Input(), contracts=contract_versions())

    def require_healthy(self) -> health.Output:
        h = self.health()
        if h.status != "ok":
            raise LayerDegraded(f"shared layer degraded: writable={h.db_writable} seeds={h.seeds} at {h.db_path}")
        return h

    def check_claims(self, text: str | None = None, claims: list[str] | None = None) -> claims_registry.Output:
        return self._run(claims_registry, text=text, claims=claims)

    def check_brand(self, text: str, channel: str) -> brand_policy.Output:
        return self._run(brand_policy, text=text, channel=channel)

    def evaluate(self, rubric_id: str, item: str | dict[str, Any], context: str | None, run_id: str, judge: str = "deterministic") -> evaluation.Output:
        return self._run(evaluation, rubric_id=rubric_id, item=item, context=context, judge=judge, run_id=run_id)

    def log_call(self, *, run_id: str, agent: str, step: str, model: str | None, input_tokens: int, output_tokens: int,
                 cost_usd: float, status: str = "ok", duration_ms: int | None = None, note: str | None = None) -> observability.Output:
        return self._run(observability, run_id=run_id, agent=agent, step=step, model=model, input_tokens=input_tokens,
                         output_tokens=output_tokens, cost_usd=cost_usd, status=status, duration_ms=duration_ms, note=note)

    def record(self, event: str, fields: dict[str, Any], run_id: str, agent: str = "scout") -> measurement.Output:
        return self._run(measurement, event=event, fields=fields, run_id=run_id, agent=agent)

    # -- cost helpers (G0's price table; G1·C has none of its own, D-27) ----------

    @staticmethod
    def prices_per_mtok() -> dict[str, tuple[float, float]]:
        return dict(evaluation.PRICES_PER_MTOK)

    @classmethod
    def cost_usd(cls, model: str, input_tokens: int, output_tokens: int) -> float:
        p_in, p_out = cls.prices_per_mtok().get(model, (0.0, 0.0))
        return round(input_tokens * p_in / 1e6 + output_tokens * p_out / 1e6, 6)
