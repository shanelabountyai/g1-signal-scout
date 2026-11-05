#!/usr/bin/env python3
"""Push the built workflow into the owner's n8n, or summarize its latest execution.

Usage:
  python3 n8n/push.py push        # build + PUT /api/v1/workflows/<WORKFLOW_ID>
  python3 n8n/push.py exec [N]    # per-node item counts/errors for the Nth-latest run (default 1)
  python3 n8n/push.py exec 1 "Drop seen"   # ...plus a sample of that node's output

Reads N8N_API_KEY and N8N_URL from .env (gitignored). Never prints the key. Stdlib only.
Does not activate the workflow: the schedule stays off until the owner says go (D-6).
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

WORKFLOW_ID = build.WORKFLOW_ID


def env():
    out = {}
    for line in (build.ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    if not out.get("N8N_API_KEY"):
        sys.exit("N8N_API_KEY is empty in .env")
    return out


def call(method, path, body=None):
    e = env()
    req = urllib.request.Request(
        e.get("N8N_URL", "http://localhost:5678") + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"X-N8N-API-KEY": e["N8N_API_KEY"], "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as err:
        sys.exit(f"{method} {path} -> {err.code}: {err.read().decode()[:500]}")


def push():
    wf = build.workflow
    body = {"name": wf["name"], "nodes": wf["nodes"], "connections": wf["connections"], "settings": wf["settings"]}
    r = call("PUT", f"/api/v1/workflows/{WORKFLOW_ID}", body)
    build.main_write()
    print(f"pushed {len(r['nodes'])} nodes to '{r['name']}' ({WORKFLOW_ID}), active={r['active']}, updated {r['updatedAt']}")


def exec_summary(n=1, sample_node=None):
    runs = call("GET", f"/api/v1/executions?workflowId={WORKFLOW_ID}&includeData=true&limit={n}")["data"]
    if len(runs) < n:
        sys.exit(f"only {len(runs)} executions")
    run = runs[n - 1]
    print(f"execution {run['id']} status={run['status']} mode={run['mode']} started {run['startedAt']}")
    rd = run["data"]["resultData"]
    for name, rs in rd.get("runData", {}).items():
        r = rs[0]
        main = (r.get("data") or {}).get("main") or [[]]
        count = len(main[0] or [])
        err = r.get("error")
        print(f"  {name:28s} items={count:<5d} {r.get('executionStatus', '')}{'  ERROR: ' + str(err.get('message', err))[:300] if err else ''}")
    if rd.get("error"):
        print("  workflow error:", rd["error"].get("message"))
    if sample_node and sample_node in rd.get("runData", {}):
        items = rd["runData"][sample_node][0]["data"]["main"][0] or []
        print(f"\n{sample_node} sample:", json.dumps([i["json"] for i in items[:2]])[:800])
    return run


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "push"
    if cmd == "push":
        push()
    elif cmd == "exec":
        exec_summary(int(sys.argv[2]) if len(sys.argv) > 2 else 1, sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        sys.exit(__doc__)
