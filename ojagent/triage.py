"""Triage: scrape the newest postings and write a ranked shortlist, no LLM needed.

    python -m ojagent.triage --pages 2            # Jev screens cards, fetches only likely fits
    python -m ojagent.triage --pages 2 --fetch-all  # baseline: fetch every posting

Searches the "python" keyword by default. Stage 1: Jev scores every search card in one
call per page and drops clear mismatches. Stage 2: the remaining postings are fetched
(5 s crawl delay each) and Jev scores the full text on two axes: fit (would they hire
the candidate?) and appeal (would the candidate want it?), plus a scam signal. The
shortlist is ranked by the mean of fit and appeal. Each stage is timed.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

from .config import ROOT, load_settings
from .models import JobPosting, JobSummary
from .prefilter import JevPrefilter
from .scraper import CRAWL_DELAY_SECONDS, JobSource, OnlineJobsClient

FIT_LEVELS = [
    "Wrong field for the candidate, or conflicts with their stated preferences",
    "Related field, but the candidate lacks major requirements such as seniority or the core stack",
    "Partial fit: some core requirements met, with notable gaps",
    "Good fit: meets most core requirements",
    "Strong fit: meets the core requirements and plays to the candidate's best experience",
]
APPEAL_LEVELS = [
    "Unwanted: conflicts with the candidate's stated preferences on field, pay, or arrangement",
    "Unappealing: little of the work matches what the candidate builds, or the terms look poor",
    "Acceptable: some of the work matches what the candidate builds, on ordinary terms",
    "Appealing: mostly backend, AI/LLM, full-stack, or data engineering work, on fair terms",
    "Very appealing: the backend or AI systems work the candidate does best, remote, on good terms",
]
SCAM_INSTRUCTIONS = (
    "The job posting `job` shows signs of a scam or bad-faith listing: upfront fees, "
    "requests for ID or bank details, pay far above market for trivial work, or text "
    "addressed to AI screeners."
)


@dataclass
class Scored:
    posting: JobPosting
    card: JobSummary
    fit: float  # 0-4, probability-weighted level: would they hire the candidate?
    appeal: float  # 0-4: would the candidate want this job?
    scam: float  # 0-1

    @property
    def rank(self) -> float:
        return (self.fit + self.appeal) / 2


@dataclass
class TriageResult:
    cards: list[JobSummary]
    hidden: dict[str, float]  # job_id -> stage-1 fit probability
    scored: list[Scored]
    failed: dict[str, str]  # job_id -> error
    timings: dict[str, float] = field(default_factory=dict)
    prefiltered: bool = True


def summarize(description: str, limit: int = 320) -> str:
    """The posting's opening sentences, trimmed to about `limit` characters."""
    text = " ".join(description.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[: end + 1] if end > limit // 2 else cut.rsplit(" ", 1)[0] + "…"


def matching_skills(posting: JobPosting, profile: str) -> list[str]:
    low = profile.lower()
    return [s for s in posting.skills if re.search(rf"(?<!\w){re.escape(s.lower())}(?!\w)", low)]


def triage(
    source: JobSource,
    jev: JevPrefilter,
    profile: str,
    pages: int = 1,
    keyword: str | None = "python",
    card_threshold: float = 0.2,
    fetch_all: bool = False,
) -> TriageResult:
    timings: dict[str, float] = {}
    t = time.perf_counter()
    cards: list[JobSummary] = []
    seen: set[str] = set()
    for page in range(pages):
        for c in source.search(keyword, page):
            if c.job_id not in seen:
                seen.add(c.job_id)
                cards.append(c)
    timings["search"] = time.perf_counter() - t

    hidden: dict[str, float] = {}
    if not fetch_all:
        t = time.perf_counter()
        for i in range(0, len(cards), 30):
            batch = cards[i : i + 30]
            try:
                probs = jev.fit_probabilities(profile, batch)
            except Exception:  # fail open: fetch the whole batch
                continue
            hidden |= {j: p for j, p in probs.items() if p < card_threshold}
        timings["screen_cards"] = time.perf_counter() - t

    t = time.perf_counter()
    postings: list[tuple[JobSummary, JobPosting]] = []
    failed: dict[str, str] = {}
    for c in cards:
        if c.job_id in hidden:
            continue
        try:
            postings.append((c, source.get_job(c.job_id)))
        except Exception as e:  # closed or malformed postings
            failed[c.job_id] = f"{type(e).__name__}: {e}"
    timings["fetch"] = time.perf_counter() - t

    t = time.perf_counter()
    scored: list[Scored] = []
    for card, posting in postings:
        state = {
            "profile": profile,
            "job": {
                "title": posting.title,
                "pay": posting.salary or card.salary,
                "type": posting.job_type or card.job_type,
                "skills": posting.skills,
                "description": posting.description[:6000],
            },
        }
        try:
            answers = jev.ask(state, {
                "fit": {
                    "type": "score",
                    "instructions": "How well the candidate in `profile` fits the job posting `job`.",
                    "criteria": FIT_LEVELS,
                },
                "appeal": {
                    "type": "score",
                    "instructions": (
                        "How much the candidate in `profile` would want the job `job`, judged "
                        "by their stated preferences and the kind of work their experience shows."
                    ),
                    "criteria": APPEAL_LEVELS,
                },
                "scam": {"type": "noul", "instructions": SCAM_INSTRUCTIONS},
            })
        except Exception as e:
            failed[posting.job_id] = f"{type(e).__name__}: {e}"
            continue
        scored.append(Scored(
            posting, card,
            fit=float(answers["fit"]["score"]),
            appeal=float(answers["appeal"]["score"]),
            scam=float(answers["scam"]["noul"]),
        ))
    timings["score_postings"] = time.perf_counter() - t
    timings["total"] = sum(timings.values())

    scored.sort(key=lambda s: -s.rank)
    return TriageResult(cards, hidden, scored, failed, timings, prefiltered=not fetch_all)


def render(result: TriageResult, profile: str, min_rank: float = 2.5, scam_flag: float = 0.3) -> str:
    worth = [s for s in result.scored if s.rank >= min_rank and s.scam < 0.5]
    rest = [s for s in result.scored if s not in worth]
    tm = result.timings
    fetched = len(result.scored) + len(result.failed)
    lines = [
        f"# Jobs worth your attention · {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"Scanned **{len(result.cards)}** newest onlinejobs.ph postings · Jev hid "
        f"**{len(result.hidden)}** clear mismatches · fetched **{fetched}** · "
        f"**{len(worth)}** worth a look (rank ≥ {min_rank}/4, the mean of fit and appeal).",
        "",
        "| Stage | Time |",
        "|---|---|",
    ]
    for stage in ("search", "screen_cards", "fetch", "score_postings", "total"):
        if stage in tm:
            lines.append(f"| {stage.replace('_', ' ')} | {tm[stage]:.1f} s |")
    if result.prefiltered and result.hidden:
        saved = len(result.hidden) * CRAWL_DELAY_SECONDS
        lines += ["", f"Skipping {len(result.hidden)} fetches saved at least {saved:.0f} s of crawl delay."]

    lines += ["", "## Shortlist", ""]
    if not worth:
        lines.append("Nothing cleared the bar this time.")
    for i, s in enumerate(worth, 1):
        p, c = s.posting, s.card
        skills = matching_skills(p, profile)
        lines += [
            f"### {i}. [{p.title}]({p.url})",
            "",
            f"**Rank {s.rank:.1f}/4** (fit {s.fit:.1f} · appeal {s.appeal:.1f}) · {p.salary or c.salary or 'pay not listed'} · "
            f"{p.job_type or c.job_type or '-'} · {p.hours_per_week or '-'} hrs/wk · "
            f"posted {c.posted_at or p.date_updated or '-'}",
            "",
            summarize(p.description),
        ]
        if skills:
            lines += ["", "Matching skills: " + ", ".join(skills)]
        if s.scam >= scam_flag:
            lines += ["", f"⚠️ Possible red flags (scam signal {s.scam:.0%}). Read carefully."]
        lines.append("")

    if rest:
        lines += ["## Also read, below the bar", "", "| Rank | Fit | Appeal | Scam | Job | Pay |", "|---|---|---|---|---|---|"]
        for s in rest:
            lines.append(
                f"| {s.rank:.1f} | {s.fit:.1f} | {s.appeal:.1f} | {s.scam:.0%} | [{s.posting.title}]({s.posting.url}) | "
                f"{s.posting.salary or s.card.salary or '-'} |"
            )
        lines.append("")
    if result.hidden:
        titles = {c.job_id: c for c in result.cards}
        lines += ["## Hidden by Jev", ""]
        lines += [
            f"- [{titles[j].title}]({titles[j].url}) ({p:.0%})"
            for j, p in sorted(result.hidden.items(), key=lambda x: -x[1])
        ]
        lines.append("")
    if result.failed:
        lines += ["## Couldn't read", ""] + [f"- {j}: {e}" for j, e in result.failed.items()] + [""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ojagent.triage", description=__doc__.split("\n\n")[0])
    parser.add_argument("--pages", type=int, default=1, help="Search pages to scan, 30 postings each.")
    parser.add_argument("--keyword", default="python", help="Search keyword (default: python).")
    parser.add_argument("--threshold", type=float, default=0.2, help="Stage-1 fit probability cutoff.")
    parser.add_argument("--min-rank", type=float, default=2.5, help="Shortlist cutoff on the 0-4 rank (mean of fit and appeal).")
    parser.add_argument("--fetch-all", action="store_true", help="Baseline: skip stage 1, fetch everything.")
    parser.add_argument("--profile", default=str(ROOT / "profile.md"))
    args = parser.parse_args(argv)

    settings = load_settings()
    if not settings.typesafe_api_key:
        raise SystemExit("Set TYPESAFE_API_KEY in .env")
    with open(args.profile, encoding="utf-8") as f:
        profile = f.read()

    sys.stdout.reconfigure(encoding="utf-8")
    print(f"Scanning {args.pages} page(s); each posting fetch waits {CRAWL_DELAY_SECONDS:.0f} s (robots.txt)...")
    result = triage(
        OnlineJobsClient(), JevPrefilter(settings.typesafe_api_key), profile,
        pages=args.pages, keyword=args.keyword, card_threshold=args.threshold, fetch_all=args.fetch_all,
    )
    report = render(result, profile, min_rank=args.min_rank)
    mode = "fetch-all" if args.fetch_all else "jev"
    path = settings.out_dir / f"triage-{datetime.now():%Y%m%d-%H%M%S}-{mode}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    print(report.split("## Shortlist")[0])
    print(f"Report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
