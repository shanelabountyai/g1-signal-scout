"""Shared fixtures: an in-memory shared layer, an in-memory seen store, the fixture items, and a scriptable caller."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scout import config, feeds
from scout.layer import Layer
from scout.llm import CallResult
from scout.models import Item
from scout.prompts import AgentSpec
from scout.seen import SeenStore

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def layer() -> Layer:
    lay = Layer(":memory:")
    yield lay
    lay.close()


@pytest.fixture
def seen() -> SeenStore:
    s = SeenStore(":memory:")
    yield s
    s.close()


@pytest.fixture(scope="session")
def feed_list():
    return config.feeds()


@pytest.fixture(scope="session")
def raw_items() -> list[dict[str, Any]]:
    return feeds.load_fixtures(config.FIXTURES_JSON)


@pytest.fixture
def items(raw_items, feed_list) -> list[Item]:
    return feeds.normalize(raw_items, feed_list, as_of=feeds.newest_date(raw_items))


HANDMADE = Path(__file__).parent / "data" / "handmade-responses.json"  # frozen hand-made sample (D-30); fixtures/ holds the live recording


@pytest.fixture(scope="session")
def recorded() -> dict[str, Any]:
    return json.loads(HANDMADE.read_text(encoding="utf-8"))


class ScriptedCaller:
    """A caller whose answers are given per agent name; `measured` and usage are configurable so cost math can be tested."""

    name = "scripted"

    def __init__(self, answers: dict[str, dict[str, Any]], measured: bool = True, usage: dict[str, tuple[int, int]] | None = None,
                 fail: str | None = None) -> None:
        self.answers = answers
        self.measured = measured
        self.usage = usage or {}
        self.fail = fail
        self.calls: list[str] = []

    async def call(self, spec: AgentSpec, user_text: str) -> CallResult:
        self.calls.append(spec.name)
        if self.fail == spec.name:
            raise RuntimeError(f"{spec.name} exploded")
        i, o = self.usage.get(spec.name, (1000, 100))
        return CallResult(agent=spec.name, model=spec.model, parsed=self.answers[spec.name], input_tokens=i, output_tokens=o,
                          sdk_cost_usd=None, stop_reason="end_turn", duration_ms=5)


@pytest.fixture
def scripted_from_recorded(recorded) -> ScriptedCaller:
    return ScriptedCaller({k: v["response"] for k, v in recorded.items() if not k.startswith("_") and isinstance(v, dict)})
