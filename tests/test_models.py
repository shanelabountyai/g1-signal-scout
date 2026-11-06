"""C2: a fixture item round-trips Item → SummarizedItem → DigestItem → Digest, and the digest JSON round-trips."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from scout.models import AgentUsage, Check, Digest, DigestItem, Item, PostDraft, RunCost, SummarizedItem


def test_fixture_item_round_trips_through_all_models(items):
    it = items[0]
    assert isinstance(it, Item) and it.id == 0 and it.url.startswith("https://")

    s = SummarizedItem(**it.model_dump(), summary="One. Two.", tag="marketing-ops-ai")
    assert s.url == it.url and s.title == it.title

    d = DigestItem(**s.model_dump(), post_angle="One sentence under 25 words.", why="because")
    assert d.summary == s.summary and d.tag == "marketing-ops-ai"

    digest = Digest(week="2026-11-02", run_id="g1c-2026-11-02-000000", run_at="2026-11-06T00:00:00+00:00", mode="recorded",
                    items=[d], drafts=[PostDraft(id=d.id, pillar="Scale", anchor="x", post="y")],
                    cost=RunCost(run_id="g1c-2026-11-02-000000", measured=False, usages=[AgentUsage(agent="Editor", model="claude-sonnet-5-5")]))
    text = json.dumps(digest.to_json_dict())
    back = Digest.model_validate(json.loads(text))
    assert back == digest
    assert back.items[0].url == it.url  # the URL survives every hand-off untouched
    assert back.title == "Signal Scout — week of 2026-11-02"
    assert back.drafted_ids() == {d.id}


def test_tag_and_pillar_are_closed_enums(items):
    it = items[0]
    with pytest.raises(ValidationError):
        SummarizedItem(**it.model_dump(), summary="s", tag="news")
    with pytest.raises(ValidationError):
        PostDraft(id=0, pillar="Growth", anchor="a", post="p")


def test_models_forbid_extra_fields(items):
    with pytest.raises(ValidationError):
        Item(**items[0].model_dump(), extra_field=1)
    with pytest.raises(ValidationError):
        Check(tool="brand_policy", target="post", passed=True, severity="fail")


def test_check_defaults_to_kept():
    c = Check(tool="claims_registry", target="summary", passed=True)
    assert c.action == "kept" and c.detail == ""
