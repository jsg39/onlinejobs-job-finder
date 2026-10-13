"""Render a run's saved results as Markdown."""

from __future__ import annotations

from .agent import RunResult

_ORDER = {"strong": 0, "possible": 1, "weak": 2, "no": 3}


def render(result: RunResult, rows: list[dict], model: str) -> str:
    rows = sorted(rows, key=lambda r: (_ORDER[r["assessment"].verdict], -r["assessment"].score))
    lines = [
        f"# onlinejobs.ph run {result.run_id}",
        "",
        f"Model `{model}` · {result.steps} steps · {result.tool_calls} tool calls · "
        f"{result.rejections} rejected by validators · "
        f"{result.input_tokens:,} in / {result.output_tokens:,} out tokens · stop: {result.stop_reason}",
        "",
        "| Verdict | Score | Job | Pay | Draft |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        p, a = r["posting"], r["assessment"]
        lines.append(
            f"| {a.verdict} | {a.score} | [{p.title}]({p.url}) | {p.salary or '-'} | "
            f"{'yes' if r['draft'] else '-'} |"
        )
    if result.summary:
        lines += ["", f"> Agent note: {result.summary}"]
    if result.prefiltered:
        lines += ["", f"**Skipped by prefilter ({len(result.prefiltered)}):** " + "; ".join(
            f"{title} ({p:.0%})" for title, p in sorted(result.prefiltered.values(), key=lambda x: -x[1])
        )]
    if result.prefilter_errors:
        lines += ["", f"> Prefilter failed, so nothing was skipped: {result.prefilter_errors[0]}"]

    for r in rows:
        p, a, d = r["posting"], r["assessment"], r["draft"]
        lines += [
            "",
            "---",
            "",
            f"## {p.title}",
            f"[{p.url}]({p.url}) · {p.job_type or '-'} · {p.salary or '-'} · "
            f"{p.hours_per_week or '-'} hrs/wk",
            "",
            f"**{a.verdict.upper()} ({a.score}/100).** {a.reasoning}",
        ]
        if a.matched:
            lines += ["", "**Matches**"]
            lines += [
                f"- “{m.requirement_quote}” ← “{m.profile_evidence_quote}”" for m in a.matched
            ]
        if a.gaps:
            lines += ["", "**Gaps**"] + [f"- {g}" for g in a.gaps]
        if a.red_flags:
            lines += ["", "**Red flags**"] + [f"- {f}" for f in a.red_flags]
        if a.application_requirements:
            lines += ["", "**Employer asks for**"] + [f"- [ ] {x}" for x in a.application_requirements]
        if a.required_phrases:
            lines += ["", "**Employer requires:** " + ", ".join(f"`{x}`" for x in a.required_phrases)]
        if d:
            lines += ["", "**Subject**", "", f"    {d.subject}", "", "**Message**", ""]
            lines += [f"    {line}" for line in d.message.splitlines()]
    return "\n".join(lines) + "\n"
