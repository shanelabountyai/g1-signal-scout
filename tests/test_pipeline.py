"""C4: AC 1–3 against SQLite, in G1·B's order (D-26). Sinks: local tested, failing used for AC 3, Drive constructor only."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from scout import config
from scout.pipeline import RunFailed, make_run_id, run_scout, week_monday
from scout.sinks import DriveSink, FailingSink, LocalSink, SinkError, load_digest, sink_from_name
from tests.conftest import ScriptedCaller

NOW = datetime(2026, 11, 6, 12, 0, 0, tzinfo=UTC)


async def run(layer, seen, sink, caller, **kw):
    return await run_scout(layer=layer, caller=caller, seen=seen, sink=sink, feed_list=config.feeds(), fixtures=config.FIXTURES_JSON,
                           now=kw.pop("now", NOW), log=lambda m: None, **kw)


def test_week_and_run_id():
    assert week_monday(NOW) == "2026-11-02"
    assert make_run_id(NOW) == "g1c-2026-11-02-120000"
    assert week_monday(datetime(2026, 11, 9, 6, tzinfo=UTC)) == "2026-11-09"


async def test_dry_run_makes_no_model_call_and_writes_nothing(layer, seen, tmp_path, scripted_from_recorded):
    rep = await run(layer, seen, LocalSink(tmp_path), scripted_from_recorded, dry_run=True)
    assert rep.dry_run and rep.digest is None and rep.counts.unseen == 29 and rep.counts.fresh == 29
    assert scripted_from_recorded.calls == [] and seen.count() == 0 and list(tmp_path.iterdir()) == []
    assert layer.calls["health"] == 1 and layer.calls["measurement"] == 1  # run.dry_run recorded


async def test_ac1_digest_written_with_5_to_8_items_each_with_link_and_angle(layer, seen, tmp_path, scripted_from_recorded):
    rep = await run(layer, seen, LocalSink(tmp_path), scripted_from_recorded)
    d = rep.digest
    assert d is not None and 5 <= len(d.items) <= 8
    assert all(i.url.startswith("https://") and i.post_angle for i in d.items)
    assert len(d.drafts) == 3
    md = (tmp_path / "2026-11-02" / "signal-scout-2026-11-02.md").read_text()
    js = tmp_path / "2026-11-02" / "signal-scout-2026-11-02.json"
    assert md.startswith("# Signal Scout — week of 2026-11-02") and "## Post drafts" in md and "## All picks this week" in md
    for i in d.items:
        assert f"]({i.url})" in md
    assert load_digest(js) == d  # the JSON round-trips to the same digest
    assert (tmp_path / "2026-11-02" / "signal-scout-2026-11-02.html").read_text().startswith("<html>")
    # order: observability rows for 4 agents, then digest.published, then seen, then run.completed
    events = [r[0] for r in layer.db.conn.execute("SELECT event FROM events ORDER BY stored_at, rowid")]
    assert events == ["run.started", "digest.published", "run.completed"]
    assert rep.marked_seen == len(d.items) == seen.count()
    assert d.mode == "live" and d.cost.measured is True  # the scripted caller is "measured"; see the recorded test below


async def test_ac2_second_run_shares_no_url(layer, seen, tmp_path, scripted_from_recorded):
    first = await run(layer, seen, LocalSink(tmp_path), scripted_from_recorded)
    urls1 = {i.url for i in first.digest.items}
    later = NOW.replace(hour=13)
    second = await run(layer, seen, LocalSink(tmp_path / "second"), scripted_from_recorded, now=later)
    assert second.counts.unseen == 29 - len(urls1)
    urls2 = {i.url for i in second.digest.items}
    assert urls1.isdisjoint(urls2)
    assert seen.count() == len(urls1) + len(urls2)
    assert second.run_id != first.run_id


async def test_ac3_failed_write_leaves_items_unmarked_and_logs_an_error_row(layer, seen, scripted_from_recorded):
    with pytest.raises(RunFailed) as ei:
        await run(layer, seen, FailingSink("bogus folder"), scripted_from_recorded)
    assert ei.value.stage == "sink"
    assert seen.count() == 0  # nothing marked seen
    rows = layer.db.conn.execute("SELECT agent, step, status, note FROM run_log ORDER BY logged_at, rowid").fetchall()
    assert [(r[0], r[2]) for r in rows] == [("Researcher", "ok"), ("Summarizer", "ok"), ("Editor", "ok"), ("Writer", "ok"), ("sink", "error")]
    assert rows[-1][1] == "write:failing" and "bogus folder" in rows[-1][3]
    events = [r[0] for r in layer.db.conn.execute("SELECT event FROM events ORDER BY stored_at, rowid")]
    assert events == ["run.started", "run.failed"]  # no digest.published, no run.completed
    # and the next run picks the same items up again
    rep = await run(layer, seen, LocalSink(__import__("tempfile").mkdtemp()), scripted_from_recorded, now=NOW.replace(hour=14))
    assert rep.counts.unseen == 29 and rep.marked_seen == 7


async def test_agent_failure_marks_nothing_and_records_run_failed(layer, seen, tmp_path, scripted_from_recorded):
    scripted_from_recorded.fail = "Editor"
    with pytest.raises(RunFailed) as ei:
        await run(layer, seen, LocalSink(tmp_path), scripted_from_recorded)
    assert ei.value.stage == "agents" and seen.count() == 0 and list(tmp_path.iterdir()) == []


async def test_empty_week_makes_no_model_call(layer, seen, tmp_path, scripted_from_recorded, items):
    seen.mark_seen(items, "pre")
    rep = await run(layer, seen, LocalSink(tmp_path), scripted_from_recorded)
    assert rep.digest is None and scripted_from_recorded.calls == [] and list(tmp_path.iterdir()) == []


async def test_recorded_mode_is_not_measured(layer, seen, tmp_path, scripted_from_recorded):
    scripted_from_recorded.measured = False
    scripted_from_recorded.name = "recorded"
    rep = await run(layer, seen, LocalSink(tmp_path), scripted_from_recorded)
    assert rep.digest.mode == "recorded" and rep.digest.cost.measured is False
    md = (tmp_path / "2026-11-02" / "signal-scout-2026-11-02.md").read_text()
    assert "cost not measured" in md


async def test_degraded_layer_refuses_to_run(layer, seen, tmp_path, scripted_from_recorded, monkeypatch):
    from scout.layer import LayerDegraded

    monkeypatch.setattr(layer.db, "writable", lambda: False)
    with pytest.raises(LayerDegraded):
        await run(layer, seen, LocalSink(tmp_path), scripted_from_recorded)
    assert scripted_from_recorded.calls == []


def test_sink_factory_and_drive_preconditions(tmp_path, monkeypatch):
    assert isinstance(sink_from_name("local", tmp_path), LocalSink)
    assert isinstance(sink_from_name("failing"), FailingSink)
    with pytest.raises(SinkError):
        sink_from_name("email")
    monkeypatch.delenv(config.ENV_DRIVE_SA, raising=False)
    monkeypatch.delenv(config.ENV_DRIVE_FOLDER, raising=False)
    with pytest.raises(SinkError, match="SCOUT_DRIVE_SERVICE_ACCOUNT_JSON"):
        DriveSink()
    with pytest.raises(SinkError, match="no key file"):
        DriveSink(key_path=str(tmp_path / "missing.json"), folder_id="f")
    key = tmp_path / "sa.json"
    key.write_text("{}")
    s = DriveSink(key_path=str(key), folder_id="folder")
    assert s.folder_id == "folder" and s.name == "drive"


async def test_local_sink_unwritable_path_is_a_sink_error(layer, seen, tmp_path, scripted_from_recorded):
    blocker = tmp_path / "file"
    blocker.write_text("not a dir")
    with pytest.raises(RunFailed) as ei:
        await run(layer, seen, LocalSink(blocker), scripted_from_recorded)
    assert ei.value.stage == "sink" and seen.count() == 0


def test_cli_dry_run_and_fixture_run(tmp_path, monkeypatch, capsys):
    from scout.cli import main

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    g0 = str(tmp_path / "g0.sqlite")
    db = str(tmp_path / "seen.sqlite")
    assert main(["--dry-run", "--db", db, "--g0-db", g0, "--out", str(tmp_path / "out")]) == 0
    out = capsys.readouterr().out
    assert "# dry run" in out and "29 unseen of 29 fresh from 15 feeds" in out
    assert main(["--fixtures", "--db", db, "--g0-db", g0, "--out", str(tmp_path / "out")]) == 0
    out = capsys.readouterr().out
    assert "7 picks, 3 drafts" in out and "not measured" in out
    cost = json.loads((tmp_path / "out" / "2026-11-02" / "cost.json").read_text())
    assert cost["measured"] is False and cost["total_cost_usd"] is None and len(cost["agents"]) == 4
    assert cost["prices_per_mtok"]["claude-sonnet-5-5"] == {"in": 2.0, "out": 10.0}
    # second CLI run: dedupe holds across processes through the SQLite file
    assert main(["--fixtures", "--db", db, "--g0-db", g0, "--out", str(tmp_path / "out2")]) == 0
    d1 = load_digest(tmp_path / "out" / "2026-11-02" / "signal-scout-2026-11-02.json")
    d2 = load_digest(tmp_path / "out2" / "2026-11-02" / "signal-scout-2026-11-02.json")
    assert {i.url for i in d1.items}.isdisjoint({i.url for i in d2.items})
    # broken sink → exit 2, nothing new marked seen
    import sqlite3
    before = sqlite3.connect(db).execute("SELECT COUNT(*) FROM seen_items").fetchone()[0]
    assert main(["--fixtures", "--db", db, "--g0-db", g0, "--sink", "failing"]) == 2
    assert sqlite3.connect(db).execute("SELECT COUNT(*) FROM seen_items").fetchone()[0] == before
    # --live without a key → exit 4
    assert main(["--live", "--db", db, "--g0-db", g0]) == 4
