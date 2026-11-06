"""n8n/prompts.py is the source of every agent instruction (D-23). This test fails if G1·C's copies drift,
and proves the three shared rules G0 now supplies are gone from G1·C's prompts (D-24)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from scout import prompts as c

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def n8n_prompts():
    spec = importlib.util.spec_from_file_location("n8n_prompts", REPO / "n8n" / "prompts.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["n8n_prompts"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("name", ["RESEARCHER", "SUMMARIZER", "EDITOR", "WRITER"])
def test_instructions_schema_model_match_g1b(n8n_prompts, name):
    b = getattr(n8n_prompts, name)
    spec = getattr(c, name)
    assert spec.instructions == b["system"]
    assert spec.schema == b["schema"]
    assert spec.model == b["model"] and spec.effort == b["effort"] and spec.max_tokens == b["max_tokens"]
    assert tuple(b["rules"]) == spec.rules  # same rules were carried in G1·B


def test_topic_brief_and_writer_blocks_are_verbatim(n8n_prompts):
    assert c.TOPIC_BRIEF == n8n_prompts.SHARED["topic_brief"]
    assert c.SHANE_RECORD == n8n_prompts.SHANE_RECORD
    assert c.POST_RULES == n8n_prompts.POST_RULES


@pytest.mark.parametrize("spec", c.AGENTS, ids=lambda s: s.name)
def test_shared_rules_moved_to_g0_are_not_in_the_prompt(n8n_prompts, spec):
    prompt = spec.system_prompt()
    for rule in c.SHARED_RULES_MOVED_TO_G0:
        assert n8n_prompts.SHARED[rule] not in prompt, f"{spec.name} still carries {rule} verbatim"
    assert c.TOPIC_BRIEF in prompt  # the one rule G1 keeps
    assert spec.instructions in prompt
    for rule in spec.rules:
        if rule in c.POINTERS:
            assert c.POINTERS[rule] in prompt  # the pointer line replaces the rule


def test_duplicated_rule_counts_before_after():
    counts = c.duplicated_rule_counts()
    assert counts["before"] == {"topic_brief": 4, "claim_rule": 4, "brand_voice": 2, "run_logging": 4}
    assert counts["after"] == {"topic_brief": 1, "claim_rule": 0, "brand_voice": 0, "run_logging": 0}
    assert sum(counts["before"].values()) == 14 and sum(counts["after"].values()) == 1


def test_writer_prompt_never_names_the_2024_26_employer():
    assert "global professional association" in c.WRITER.system_prompt()
