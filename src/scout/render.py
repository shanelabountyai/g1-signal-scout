"""Digest → Markdown / HTML. Deterministic: links and facts come from the item records, the models added only
intro, angles and drafts (same stance as G1·B's Compose digest node). Every shared-layer check is shown."""

from __future__ import annotations

import html
import json

from scout.agents import flagged
from scout.models import Check, Digest


def _checks_md(checks: list[Check]) -> str:
    bad = flagged(checks)
    if not bad:
        return f"  - checks: {len(checks)} passed (claims registry, brand policy, evaluation)"
    lines = [f"  - checks: {len(checks) - len(bad)} passed, **{len(bad)} flagged**:"]
    lines += [f"    - `{c.tool}` on {c.target}: {c.detail}" for c in bad]
    return "\n".join(lines)


def to_markdown(d: Digest) -> str:
    c = d.counts
    cost = d.cost
    cost_line = f"cost ${cost.total_cost_usd:.4f} (cap ${cost.cap_usd:.0f})" if cost.measured else "cost not measured (recorded responses, no live call)"
    out = [f"# {d.title}", "",
           f"*{c.fresh} new items from {c.feeds} feeds · {c.unseen} unseen · {c.kept} on topic · {c.summarized} summarized"
           f"{f' · {c.dropped_by_claim_rule} dropped by the claim rule' if c.dropped_by_claim_rule else ''} · {c.picked} picked · {c.drafted} drafted · {cost_line}*",
           "", d.intro.strip(), "", "## Post drafts", ""]
    if not d.drafts:
        out += ["No pick this week could be anchored honestly to your record, so no drafts. The picks are below.", ""]
    by_id = {i.id: i for i in d.items}
    for n, dr in enumerate(d.drafts, 1):
        rec = by_id.get(dr.id)
        out += [f"### Draft {n} · {dr.pillar}", ""]
        if rec:
            out += [f"**From:** [{rec.title}]({rec.url}) ({rec.source})  "]
        out += [f"**Anchored to:** {dr.anchor}", "", dr.post.strip(), "", "*Read it out loud before it ships.*", "", _checks_md(dr.checks), "", "---", ""]
    out += ["## All picks this week", ""]
    drafted = d.drafted_ids()
    for n, it in enumerate(d.items, 1):
        out += [f"### {n}. [{it.title}]({it.url}){' (drafted)' if it.id in drafted else ''}", "",
                f"**{it.source}** · {it.date[:10]} · `{it.tag}`", "", it.summary.strip(), "",
                f"**Angle:** {it.post_angle}  ", f"*Why: {it.why}*", "", _checks_md(it.checks), ""]
    out += ["---", "", "## Run", ""]
    out += [f"- run `{d.run_id}` at {d.run_at} · mode **{d.mode}**",
            f"- shared layer {d.layer.status} · {d.layer.db_path} · g0-shared-layer {d.layer.server_version} · calls: "
            + ", ".join(f"{k} ×{v}" for k, v in sorted(d.layer.calls.items()))]
    out += ["", "| Agent | Model | In | Out | Cost | Note |", "|---|---|---|---|---|---|"]
    for u in cost.usages:
        cost_s = f"${u.cost_usd:.4f}" if cost.measured else "—"
        out.append(f"| {u.agent} | {u.model} | {u.input_tokens:,} | {u.output_tokens:,} | {cost_s} | {u.status}; {u.note[:80]} |")
    out.append(f"| **total** | | | | {'$' + format(cost.total_cost_usd, '.4f') if cost.measured else 'not measured'} | {'OVER CAP' if cost.over_cap else ''} |")
    return "\n".join(out) + "\n"


def to_json(d: Digest) -> str:
    return json.dumps(d.to_json_dict(), indent=2, ensure_ascii=False) + "\n"


def _esc(s: object) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def _paras(t: str) -> str:
    return "".join(f"<p>{_esc(p.strip()).replace(chr(10), '<br>')}</p>" for p in t.split("\n\n") if p.strip())


def to_html(d: Digest) -> str:
    """The HTML the Drive sink uploads for conversion to a Google Doc (same layout as G1·B's Doc)."""
    c = d.counts
    by_id = {i.id: i for i in d.items}
    drafted = d.drafted_ids()
    h = [f'<html><head><meta charset="utf-8"></head><body><h1>{_esc(d.title)}</h1>',
         f"<p><i>{c.fresh} new items from {c.feeds} feeds · {c.kept} on topic · {c.picked} picked · {c.drafted} drafted · "
         f"{'cost $' + format(d.cost.total_cost_usd, '.3f') if d.cost.measured else 'cost not measured'}</i></p>", _paras(d.intro), "<h2>Post drafts</h2>"]
    if not d.drafts:
        h.append("<p>No pick this week could be anchored honestly to your record, so no drafts. The picks are below.</p>")
    for n, dr in enumerate(d.drafts, 1):
        rec = by_id.get(dr.id)
        h.append(f"<h3>Draft {n} · {_esc(dr.pillar)}</h3>")
        if rec:
            h.append(f'<p><b>From:</b> <a href="{_esc(rec.url)}">{_esc(rec.title)}</a> ({_esc(rec.source)})<br><b>Anchored to:</b> {_esc(dr.anchor)}</p>')
        h.append(_paras(dr.post) + "<p><i>Read it out loud before it ships.</i></p>")
        bad = flagged(dr.checks)
        if bad:
            h.append("<p><b>Flagged:</b> " + "; ".join(f"{_esc(x.tool)}: {_esc(x.detail)}" for x in bad) + "</p>")
        h.append("<hr>")
    h.append("<h2>All picks this week</h2>")
    for n, it in enumerate(d.items, 1):
        h.append(f'<h3>{n}. <a href="{_esc(it.url)}">{_esc(it.title)}</a>{" (drafted)" if it.id in drafted else ""}</h3>')
        h.append(f"<p><b>{_esc(it.source)}</b> · {_esc(it.date[:10])} · {_esc(it.tag)}</p><p>{_esc(it.summary)}</p>")
        h.append(f"<p><b>Angle:</b> {_esc(it.post_angle)}<br><i>Why: {_esc(it.why)}</i></p>")
        bad = flagged(it.checks)
        if bad:
            h.append("<p><b>Flagged:</b> " + "; ".join(f"{_esc(x.tool)}: {_esc(x.detail)}" for x in bad) + "</p>")
    usage = " · ".join(f"{u.agent} {u.model} {u.input_tokens}→{u.output_tokens} tok" + (f" ${u.cost_usd:.4f}" if d.cost.measured else "") for u in d.cost.usages)
    h.append(f"<hr><p><small>Run {_esc(d.run_at)} · {_esc(d.mode)} · {usage}</small></p></body></html>")
    return "".join(h)
