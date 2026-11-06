"""The model callers (D-24, D-29). The SDK is driven with a fake `query`; no network."""

from __future__ import annotations

import json

import pytest

from scout import config
from scout.llm import AgentSdkCaller, ModelCallError, RecordedCaller, RecordingCaller
from scout.prompts import EDITOR, RESEARCHER


async def test_recorded_caller_replays_the_fixture_file():
    rc = RecordedCaller(config.RECORDED_JSON)
    assert rc.measured is False and rc.recorded_live is False and "HAND-MADE" in rc.about
    r = await rc.call(RESEARCHER, "ignored")
    assert r.agent == "Researcher" and r.model == "claude-haiku-5-5"
    assert len(r.parsed["items"]) == 29 and r.input_tokens == 0
    with pytest.raises(ModelCallError):
        await rc.call(type("S", (), {"name": "Nobody", "model": "x"})(), "")  # type: ignore[arg-type]


async def test_recorded_fixture_matches_each_agent_schema_shape():
    doc = json.loads(config.RECORDED_JSON.read_text())
    for name, required in [("Researcher", "items"), ("Summarizer", "items"), ("Editor", "picks"), ("Writer", "drafts")]:
        assert required in doc[name]["response"]
    assert all(set(d) == {"id", "pillar", "anchor", "post"} for d in doc["Writer"]["response"]["drafts"])
    assert len({d["pillar"] for d in doc["Writer"]["response"]["drafts"]}) == 3  # three different pillars (D-20)


class _FakeSdk:
    """Stands in for claude_agent_sdk: records the options and yields one assistant and one result message."""

    def __init__(self, structured=None, text="", is_error=False):
        self.options = None
        self.prompt = None
        self.structured = structured
        self.text = text
        self.is_error = is_error

    def install(self, monkeypatch):
        import claude_agent_sdk as sdk

        fake = self

        async def query(*, prompt, options=None, transport=None):
            fake.prompt, fake.options = prompt, options
            yield sdk.AssistantMessage(content=[sdk.TextBlock(text=fake.text)], model=options.model)
            yield sdk.ResultMessage(subtype="success", duration_ms=12, duration_api_ms=10, is_error=fake.is_error, num_turns=1,
                                    session_id="s", stop_reason="end_turn", total_cost_usd=0.0123,
                                    usage={"input_tokens": 500, "output_tokens": 50, "cache_read_input_tokens": 200, "cache_creation_input_tokens": 100},
                                    result=fake.text, structured_output=fake.structured)

        monkeypatch.setattr(sdk, "query", query)


async def test_sdk_caller_builds_a_no_tool_structured_call(monkeypatch):
    fake = _FakeSdk(structured={"intro": "x", "picks": []})
    fake.install(monkeypatch)
    r = await AgentSdkCaller(max_budget_usd=10).call(EDITOR, "Summarized items as JSON:\n[]")
    o = fake.options
    assert o.model == "claude-sonnet-5-5" and o.tools == [] and o.max_turns == 1 and o.permission_mode == "dontAsk"
    assert o.output_format == {"type": "json_schema", "schema": EDITOR.schema} and o.max_budget_usd == 10 and o.effort == "medium"
    assert o.system_prompt == EDITOR.system_prompt() and fake.prompt.startswith("Summarized items")
    assert r.parsed == {"intro": "x", "picks": []}
    assert r.input_tokens == 500 and r.billed_input_tokens == 800 and r.output_tokens == 50 and r.sdk_cost_usd == 0.0123


async def test_sdk_caller_falls_back_to_text_json(monkeypatch):
    _FakeSdk(structured=None, text='```json\n{"items": []}\n```').install(monkeypatch)
    r = await AgentSdkCaller().call(RESEARCHER, "x")
    assert r.parsed == {"items": []}


async def test_sdk_caller_refuses_non_json_and_errors(monkeypatch):
    _FakeSdk(structured=None, text="not json").install(monkeypatch)
    with pytest.raises(ModelCallError):
        await AgentSdkCaller().call(RESEARCHER, "x")
    _FakeSdk(structured={"items": []}, is_error=True).install(monkeypatch)
    with pytest.raises(ModelCallError):
        await AgentSdkCaller().call(RESEARCHER, "x")


async def test_recording_caller_writes_a_replayable_file(monkeypatch, tmp_path):
    _FakeSdk(structured={"items": [{"id": 0, "keep": True, "reason": "r"}]}).install(monkeypatch)
    path = tmp_path / "rec.json"
    rec = RecordingCaller(AgentSdkCaller(), path)
    await rec.call(RESEARCHER, "items")
    replay = RecordedCaller(path)
    assert replay.recorded_live is True and replay.measured is True
    r = await replay.call(RESEARCHER, "items")
    assert r.parsed["items"][0]["keep"] is True and r.input_tokens == 500 and r.cache_read_tokens == 200
