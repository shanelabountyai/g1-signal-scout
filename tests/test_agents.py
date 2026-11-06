"""C3: the four agents attached to G0 (D-24, D-32). No model call anywhere in here."""

from __future__ import annotations

import pytest

from scout.agents import AgentFailed, OverCap, Runner, flagged
from scout.feeds import renumber
from scout.models import Item
from scout.prompts import EDITOR, RESEARCHER, SUMMARIZER, WRITER
from tests.conftest import ScriptedCaller

ITEMS = renumber([
    Item(id=0, title="Salesforce cut lead assignment from 20 minutes to 20 seconds", url="https://sf.example/data360", source="Salesforce Blog",
         date="2026-11-04T00:00:00+00:00", excerpt="Leads could follow outdated rules for up to six weeks. Lead assignment went from 20 minutes to 20 seconds."),
    Item(id=1, title="AEO measurement", url="https://hs.example/aeo", source="HubSpot Marketing Blog", date="2026-11-04T00:00:00+00:00",
         excerpt="Measuring success was the top challenge among B2B marketers at 23%."),
    Item(id=2, title="Website builders", url="https://sf.example/builders", source="Salesforce Blog", date="2026-11-04T00:00:00+00:00", excerpt="Seven builders."),
])


def answers(summary_1="HubSpot's report puts measurement as the top AEO challenge for B2B marketers at 23%. The article is about benchmarking.",
            angle_0="Salesforce cut lead assignment from 20 minutes to 20 seconds by fixing routing rules that lagged six weeks.",
            post_0="Twenty minutes to twenty seconds. Salesforce fixed the lag.\n\nAt Level 3 I owned the Eloqua-to-Salesforce lead funnel.\n\n#marketingops"):
    return {
        "Researcher": {"items": [{"id": 0, "keep": True, "reason": "ops result"}, {"id": 1, "keep": True, "reason": "survey"},
                                 {"id": 2, "keep": False, "reason": "listicle"}, {"id": 99, "keep": True, "reason": "unknown id"}]},
        "Summarizer": {"items": [{"id": 0, "summary": "Salesforce cut lead assignment from 20 minutes to 20 seconds. Rules lagged six weeks.", "tag": "marketing-ops-ai"},
                                 {"id": 1, "summary": summary_1, "tag": "marketing-ops-ai"},
                                 {"id": 42, "summary": "ghost", "tag": "other"}]},
        "Editor": {"intro": "Routing and measurement.", "picks": [{"id": 0, "post_angle": angle_0, "why": "number"},
                                                                  {"id": 1, "post_angle": "AEO measurement is the gap at 23%; the stack has to catch up.", "why": "survey"},
                                                                  {"id": 7, "post_angle": "ghost", "why": "unknown"}]},
        "Writer": {"drafts": [{"id": 0, "pillar": "Impact", "anchor": "owned the Eloqua-to-Salesforce lead funnel", "post": post_0}]},
    }


async def run_all(layer, caller, judge="deterministic"):
    r = Runner(layer=layer, caller=caller, run_id="g1c-test-000000", judge=judge)
    kept = await r.research(ITEMS)
    summarized, dropped = await r.summarize(kept)
    intro, picks = await r.edit(summarized)
    drafts = await r.write(picks)
    return r, kept, summarized, dropped, intro, picks, drafts


async def test_happy_path_joins_by_id_and_logs_every_call(layer):
    caller = ScriptedCaller(answers(), usage={"Researcher": (1000, 100), "Summarizer": (2000, 200), "Editor": (3000, 300), "Writer": (4000, 400)})
    r, kept, summarized, dropped, intro, picks, drafts = await run_all(layer, caller)
    assert [i.url for i in kept] == [ITEMS[0].url, ITEMS[1].url]  # unknown id 99 dropped, keep=false dropped
    assert dropped == 0 and [s.id for s in summarized] == [0, 1]  # ghost id 42 dropped
    assert [p.id for p in picks] == [0, 1] and intro == "Routing and measurement."
    assert picks[0].url == ITEMS[0].url  # URL from the record, never from the model
    assert len(drafts) == 1 and drafts[0].pillar == "Impact"
    # observability: one row per agent, cost from G0's prices, run total kept
    assert [u.agent for u in r.usages] == ["Researcher", "Summarizer", "Editor", "Writer"]
    assert r.usages[0].cost_usd == pytest.approx(1000 * 0.10 / 1e6 + 100 * 0.50 / 1e6)
    assert r.usages[2].cost_usd == pytest.approx(3000 * 2.0 / 1e6 + 300 * 10.0 / 1e6)
    assert r.total_cost_usd == pytest.approx(sum(u.cost_usd for u in r.usages))
    assert all(u.log_id.startswith("log_") for u in r.usages)
    assert layer.calls["observability"] == 4 and r.over_cap is False
    rows = layer.db.conn.execute("SELECT agent, step, model FROM run_log ORDER BY logged_at").fetchall()
    assert [(a, s) for a, s, _ in rows] == [("Researcher", "screen"), ("Summarizer", "summarize"), ("Editor", "pick"), ("Writer", "draft")]
    # every shared-layer check happened and passed on clean text
    assert layer.calls["brand_policy"] == 3 and layer.calls["claims_registry"] >= 5 and layer.calls["evaluation"] >= 7
    assert not flagged([c for p in picks for c in p.checks]) and not flagged(drafts[0].checks)


async def test_invented_number_in_summary_is_dropped_by_claim_rule(layer):
    caller = ScriptedCaller(answers(summary_1="Measurement is the top challenge for 61% of B2B marketers. Benchmarks follow."))
    r, kept, summarized, dropped, intro, picks, drafts = await run_all(layer, caller)
    assert dropped == 1 and [s.id for s in summarized] == [0]
    assert [p.id for p in picks] == [0]  # the Editor's pick of id 1 has nothing to join to


async def test_banned_phrase_in_angle_is_flagged_not_dropped(layer):
    caller = ScriptedCaller(answers(angle_0="Excited to share: Salesforce cut lead assignment from 20 minutes to 20 seconds, a game-changer."))
    r, kept, summarized, dropped, intro, picks, drafts = await run_all(layer, caller)
    assert [p.id for p in picks] == [0, 1]
    bad = flagged(picks[0].checks)
    tools = {c.tool for c in bad}
    assert "brand_policy" in tools
    detail = next(c.detail for c in bad if c.tool == "brand_policy")
    assert "never_use.excited_to_share" in detail and "never_use.game_changer" in detail


async def test_long_angle_fails_post_angle_rules(layer):
    long = "This angle keeps going and going well past the limit the brand policy sets for a one line post angle so it must be flagged by the engine today."
    caller = ScriptedCaller(answers(angle_0=long))
    r, *_, picks, drafts = await run_all(layer, caller)
    assert any("post_angle.max_25_words" in c.detail for c in flagged(picks[0].checks))


async def test_draft_with_number_not_in_record_or_item_is_flagged(layer):
    caller = ScriptedCaller(answers(post_0="I saved 3,400 hours last quarter with this.\n\nSalesforce showed the way.\n\n#ops"))
    r, *_, drafts = await run_all(layer, caller)
    ev = [c for c in drafts[0].checks if c.tool == "evaluation"]
    assert ev and ev[0].passed is False and ev[0].action == "flagged" and "numbers_in_source" in ev[0].detail


async def test_researcher_keeping_nothing_stops_the_run(layer):
    a = answers()
    a["Researcher"] = {"items": [{"id": i, "keep": False, "reason": "no"} for i in range(3)]}
    with pytest.raises(AgentFailed):
        await Runner(layer=layer, caller=ScriptedCaller(a), run_id="r").research(ITEMS)


async def test_model_error_is_logged_as_error_row_and_reraised(layer):
    caller = ScriptedCaller(answers(), fail="Summarizer")
    r = Runner(layer=layer, caller=caller, run_id="r-err")
    kept = await r.research(ITEMS)
    with pytest.raises(RuntimeError, match="exploded"):
        await r.summarize(kept)
    rows = layer.db.conn.execute("SELECT agent, status FROM run_log WHERE run_id='r-err' ORDER BY logged_at").fetchall()
    assert [tuple(x) for x in rows] == [("Researcher", "ok"), ("Summarizer", "error")]
    assert r.usages[-1].status == "error"


async def test_over_cap_stops_before_the_next_call(layer, monkeypatch):
    monkeypatch.setenv("G0_RUN_CAP_USD", "0.001")
    caller = ScriptedCaller(answers(), usage={"Researcher": (10_000, 1_000)})  # $0.0015 > cap
    r = Runner(layer=layer, caller=caller, run_id="r-cap")
    kept = await r.research(ITEMS)
    assert r.over_cap is True
    with pytest.raises(OverCap):
        await r.summarize(kept)
    assert caller.calls == ["Researcher"]  # the Summarizer was never called


async def test_recorded_responses_are_unmeasured(layer, scripted_from_recorded):
    scripted_from_recorded.measured = False
    r = Runner(layer=layer, caller=scripted_from_recorded, run_id="r-rec")
    from scout import config, feeds
    raws = feeds.load_fixtures(config.FIXTURES_JSON)
    items = feeds.normalize(raws, config.feeds(), as_of=feeds.newest_date(raws))
    kept = await r.research(items)
    assert len(kept) == 16 and r.usages[0].cost_usd == 0.0


def test_agent_specs_are_the_four(layer):
    assert [s.name for s in (RESEARCHER, SUMMARIZER, EDITOR, WRITER)] == ["Researcher", "Summarizer", "Editor", "Writer"]
