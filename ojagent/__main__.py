"""CLI: python -m ojagent [--max-jobs N] [--task "..."]"""

from __future__ import annotations

import argparse
import sys

from .agent import Agent
from .config import ROOT, load_settings
from .llm import OpenAICompatibleLLM
from .prefilter import JevPrefilter
from .report import render
from .scraper import OnlineJobsClient
from .store import Store

DEFAULT_TASK = (
    "Find the newest onlinejobs.ph postings that fit me, assess each one you read, and "
    "draft applications for the good fits."
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ojagent", description=__doc__)
    parser.add_argument("--task", default=DEFAULT_TASK, help="Instruction for the agent.")
    parser.add_argument("--max-jobs", type=int, default=8, help="Max postings to read.")
    parser.add_argument("--max-steps", type=int, default=60)
    parser.add_argument("--model", help="Override LLM_MODEL.")
    parser.add_argument("--profile", default=str(ROOT / "profile.md"))
    parser.add_argument(
        "--prefilter-threshold", type=float, default=0.2,
        help="Hide postings Jev rates below this fit probability (needs TYPESAFE_API_KEY).",
    )
    parser.add_argument("--no-prefilter", action="store_true", help="Show the agent every posting.")
    args = parser.parse_args(argv)

    settings = load_settings()
    model = args.model or settings.model
    with open(args.profile, encoding="utf-8") as f:
        profile = f.read()

    store = Store(settings.db_path)
    prefilter = None
    if settings.typesafe_api_key and not args.no_prefilter:
        prefilter = JevPrefilter(settings.typesafe_api_key)
    agent = Agent(
        llm=OpenAICompatibleLLM(model, settings.api_key, settings.base_url),
        source=OnlineJobsClient(),
        store=store,
        profile=profile,
        max_steps=args.max_steps,
        trace_dir=settings.out_dir / "traces",
        prefilter=prefilter,
        prefilter_threshold=args.prefilter_threshold,
    )
    if prefilter:
        print(f"Prefilter: {prefilter.model}, hiding postings below {args.prefilter_threshold:.0%} fit")
    print(f"Running with {model} (robots.txt crawl-delay is 5s, so fetching takes a while)...")
    result = agent.run(args.task, max_jobs=args.max_jobs)

    report = render(result, store.run_results(result.run_id), model)
    report_path = settings.out_dir / f"{result.run_id}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    sys.stdout.reconfigure(encoding="utf-8")
    print(report.split("\n---\n")[0])
    print(f"\nFull report: {report_path}\nTrace: {result.trace_path}")
    return 0 if result.finished else 1


if __name__ == "__main__":
    raise SystemExit(main())
