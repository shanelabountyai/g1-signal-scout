"""Model calls (C3, D-25, D-30).

`AgentSdkCaller` makes one structured-output call per agent through the Claude
Agent SDK (`claude_agent_sdk.query`): no tools, one turn, the agent's JSON
schema as `output_format`, so the answer arrives parsed in
`ResultMessage.structured_output` and the token usage in `ResultMessage.usage`.

`RecordedCaller` answers from `fixtures/recorded-responses.json` and makes no
network call. `RecordingCaller` wraps a real caller and saves what it got, so
the first live run (`scout --fixtures --record`) replaces the hand-made file
with real responses.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from scout.prompts import AgentSpec


class ModelCallError(RuntimeError):
    """The model did not return usable JSON for the agent's schema."""


@dataclass
class CallResult:
    agent: str
    model: str
    parsed: dict[str, Any]
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    sdk_cost_usd: float | None = None
    stop_reason: str | None = None
    duration_ms: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def billed_input_tokens(self) -> int:
        """What the cost is computed on: fresh input plus cache writes and reads. Cache reads are cheaper than
        this counts them; the number is an upper bound on purpose (a cap breach must not hide in a discount)."""
        return self.input_tokens + self.cache_creation_tokens + self.cache_read_tokens


class ModelCaller(Protocol):
    name: str
    measured: bool  # True when the usage numbers are real

    async def call(self, spec: AgentSpec, user_text: str) -> CallResult: ...


# ---------------------------------------------------------------- the real thing


class AgentSdkCaller:
    name = "claude-agent-sdk"
    measured = True

    def __init__(self, max_budget_usd: float = 10.0) -> None:
        self.max_budget_usd = max_budget_usd

    async def call(self, spec: AgentSpec, user_text: str) -> CallResult:
        from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

        options = ClaudeAgentOptions(
            model=spec.model,
            system_prompt=spec.system_prompt(),
            tools=[],
            allowed_tools=[],
            max_turns=1,
            permission_mode="dontAsk",
            setting_sources=[],
            effort=spec.effort,  # type: ignore[arg-type]
            output_format={"type": "json_schema", "schema": spec.schema},
            max_budget_usd=self.max_budget_usd,
        )
        started = time.monotonic()
        result: ResultMessage | None = None
        text_parts: list[str] = []
        model_seen = spec.model
        async for message in query(prompt=user_text, options=options):
            if isinstance(message, AssistantMessage):
                model_seen = message.model or model_seen
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
            elif isinstance(message, ResultMessage):
                result = message
        duration_ms = int((time.monotonic() - started) * 1000)
        if result is None:
            raise ModelCallError(f"{spec.name}: the SDK returned no result message")
        if result.is_error:
            raise ModelCallError(f"{spec.name}: SDK error {result.subtype} status={result.api_error_status} {result.errors or ''}")
        parsed = result.structured_output
        if not isinstance(parsed, dict):
            parsed = _parse_json("".join(text_parts) or (result.result or ""), spec.name)
        usage = result.usage or {}
        return CallResult(
            agent=spec.name, model=model_seen, parsed=parsed,
            input_tokens=int(usage.get("input_tokens", 0)), output_tokens=int(usage.get("output_tokens", 0)),
            cache_read_tokens=int(usage.get("cache_read_input_tokens", 0)), cache_creation_tokens=int(usage.get("cache_creation_input_tokens", 0)),
            sdk_cost_usd=result.total_cost_usd, stop_reason=result.stop_reason, duration_ms=duration_ms,
            raw={"usage": usage, "model_usage": result.model_usage, "num_turns": result.num_turns, "session_id": result.session_id},
        )


def _parse_json(text: str, agent: str) -> dict[str, Any]:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):]
    try:
        out = json.loads(t)
    except json.JSONDecodeError as e:
        raise ModelCallError(f"{agent}: response is not JSON ({e}): {t[:200]!r}") from e
    if not isinstance(out, dict):
        raise ModelCallError(f"{agent}: response JSON is not an object")
    return out


# ---------------------------------------------------------------- recorded responses (no key)


class RecordedCaller:
    """Answers each agent from a file keyed by agent name. `measured` is False: the usage numbers in the file
    are whatever was recorded (zeros for the hand-made file, D-30) and never go into the cost comparison."""

    name = "recorded"
    measured = False

    def __init__(self, path: Path) -> None:
        self.path = path
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.about: str = str(doc.get("_about", ""))
        self.recorded_live: bool = bool(doc.get("recorded_live", False))
        self.responses: dict[str, dict[str, Any]] = {k: v for k, v in doc.items() if not k.startswith("_") and isinstance(v, dict)}
        self.measured = self.recorded_live

    async def call(self, spec: AgentSpec, user_text: str) -> CallResult:
        rec = self.responses.get(spec.name)
        if rec is None:
            raise ModelCallError(f"{spec.name}: no recorded response in {self.path}")
        usage = rec.get("usage") or {}
        return CallResult(
            agent=spec.name, model=str(rec.get("model") or spec.model), parsed=dict(rec["response"]),
            input_tokens=int(usage.get("input_tokens", 0)), output_tokens=int(usage.get("output_tokens", 0)),
            cache_read_tokens=int(usage.get("cache_read_input_tokens", 0)), cache_creation_tokens=int(usage.get("cache_creation_input_tokens", 0)),
            sdk_cost_usd=rec.get("sdk_cost_usd"), stop_reason=rec.get("stop_reason", "recorded"), duration_ms=0,
            raw={"recorded_from": self.path.name},
        )


class RecordingCaller:
    """Wraps a real caller and writes every response to `path` in RecordedCaller's format."""

    name = "recording"
    measured = True

    def __init__(self, inner: ModelCaller, path: Path) -> None:
        self.inner = inner
        self.path = path
        self.doc: dict[str, Any] = {
            "_about": "Recorded live responses of the four G1·C agents on fixtures/feed-items.json, saved by "
                      "`scout --fixtures --record`. Replayed by RecordedCaller when no ANTHROPIC_API_KEY is present.",
            "recorded_live": True,
            "recorded_at": None,
        }

    async def call(self, spec: AgentSpec, user_text: str) -> CallResult:
        r = await self.inner.call(spec, user_text)
        from datetime import UTC, datetime

        self.doc["recorded_at"] = datetime.now(UTC).isoformat(timespec="seconds")
        self.doc[spec.name] = {
            "model": r.model, "response": r.parsed, "stop_reason": r.stop_reason, "sdk_cost_usd": r.sdk_cost_usd,
            "usage": {"input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
                      "cache_read_input_tokens": r.cache_read_tokens, "cache_creation_input_tokens": r.cache_creation_tokens},
            "user_text_chars": len(user_text),
        }
        self.path.write_text(json.dumps(self.doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return r
