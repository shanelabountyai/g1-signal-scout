"""`scout` — run the Weekly Signal Scout, code version (G1·C).

  uv run scout --dry-run              health, fixtures, unseen items; no model call
  uv run scout --fixtures             full run on the fixtures (recorded responses without a key)
  uv run scout --fixtures --record    full run on the fixtures with live calls, saving the responses
  uv run scout --live                 live feeds, live model calls (needs ANTHROPIC_API_KEY)
  uv run scout --live --sink drive    …and the Google Drive sink (needs the service-account env)

Exit code 0 on success or an empty week, 2 when the run failed before marking items seen,
3 when the shared layer is degraded, 4 when live calls were asked for without a key.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from scout import config
from scout.costlog import run_log_rows, write_cost
from scout.layer import Layer, LayerDegraded
from scout.llm import AgentSdkCaller, ModelCaller, RecordedCaller, RecordingCaller
from scout.pipeline import RunFailed, run_scout
from scout.seen import SeenStore
from scout.sinks import SinkError, sink_from_name


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="scout", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="health + fixtures + unseen list; no model call, nothing written")
    mode.add_argument("--fixtures", action="store_true", help="full run on fixtures/feed-items.json (default when no --live)")
    mode.add_argument("--live", action="store_true", help="fetch the real feeds and call the models (needs ANTHROPIC_API_KEY)")
    p.add_argument("--record", action="store_true", help="with a key: call the models and save fixtures/recorded-responses.json")
    p.add_argument("--sink", default="local", choices=["local", "drive", "failing"], help="where the digest lands (default local)")
    p.add_argument("--out", default=str(config.OUT_DIR), help="root for the local sink and cost.json")
    p.add_argument("--db", default=None, help=f"seen_items SQLite path (default ${config.ENV_DB_PATH} or ~/.g1-signal-scout/scout.sqlite)")
    p.add_argument("--g0-db", default=None, help="shared layer SQLite path (default $G0_DB_PATH or G0's default)")
    p.add_argument("--fixtures-file", default=str(config.FIXTURES_JSON))
    p.add_argument("--recorded-file", default=str(config.RECORDED_JSON))
    p.add_argument("--as-of", default=None, help="ISO date for the freshness window (fixtures default to their newest item)")
    p.add_argument("--judge", default="deterministic", choices=["deterministic", "claude", "fixture"], help="evaluation judge (D-32)")
    p.add_argument("--cap", type=float, default=None, help="override the $10 run cap (sets G0_RUN_CAP_USD)")
    return p


def choose_caller(args: argparse.Namespace, log) -> ModelCaller:
    key = config.api_key_present()
    if args.live and not key:
        raise SystemExit(f"--live needs {config.ENV_API_KEY} in the environment (exit 4)")
    if key and (args.live or args.record):
        caller: ModelCaller = AgentSdkCaller(max_budget_usd=float(os.environ.get("G0_RUN_CAP_USD", 10.0)))
        if args.record:
            caller = RecordingCaller(caller, Path(args.recorded_file))
            log(f"recording live responses to {args.recorded_file}")
        return caller
    if args.record and not key:
        raise SystemExit(f"--record needs {config.ENV_API_KEY}; without it the run replays the recorded file (exit 4)")
    rec = RecordedCaller(Path(args.recorded_file))
    log(f"no {config.ENV_API_KEY}: agents answer from {args.recorded_file} ({'live recording' if rec.recorded_live else 'hand-made sample, D-30'}); cost not measured")
    return rec


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log = lambda m: print(m, file=sys.stderr)  # noqa: E731
    if args.cap is not None:
        os.environ["G0_RUN_CAP_USD"] = str(args.cap)
    as_of = datetime.fromisoformat(args.as_of).replace(tzinfo=UTC) if args.as_of else None
    fixtures = None if args.live else Path(args.fixtures_file)

    try:
        layer = Layer(args.g0_db)
    except Exception as e:  # noqa: BLE001
        log(f"shared layer could not be opened: {e}")
        return 3
    seen = SeenStore(args.db or config.db_path())
    try:
        sink = sink_from_name(args.sink, Path(args.out))
    except SinkError as e:
        log(str(e))
        return 2
    try:
        caller = choose_caller(args, log) if not args.dry_run else RecordedCaller(Path(args.recorded_file))
    except SystemExit as e:
        log(str(e))
        return 4

    try:
        report = asyncio.run(run_scout(layer=layer, caller=caller, seen=seen, sink=sink, feed_list=config.feeds(), fixtures=fixtures,
                                       as_of=as_of, dry_run=args.dry_run, judge=args.judge, log=log))
    except LayerDegraded as e:
        log(str(e))
        return 3
    except RunFailed as e:
        log(f"run failed at {e.stage}: {e}")
        return 2
    finally:
        seen.close()
        layer.close()

    if report.dry_run:
        print(f"# dry run {report.run_id}: {report.counts.unseen} unseen of {report.counts.fresh} fresh from {report.counts.feeds} feeds; "
              f"shared layer {report.health.get('status')} (g0-shared-layer {report.health.get('server_version')}); layer calls {report.layer_calls}")
        for it in report.unseen:
            print(f"- [{it.id}] {it.source} · {it.date[:10]} · {it.title}\n      {it.url}")
        return 0
    if report.digest is None:
        print(f"# {report.run_id}: nothing new this week")
        return 0
    cost_path = write_cost(report.digest, Path(args.out))
    print(f"# {report.digest.title} — {report.counts.picked} picks, {report.counts.drafted} drafts; written by {report.write.sink if report.write else '?'}: "
          f"{report.write.location if report.write else ''}; {report.marked_seen} marked seen; cost.json: {cost_path}")
    print(run_log_rows(report.digest))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
