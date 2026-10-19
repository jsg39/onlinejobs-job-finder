"""The "At a glance" bullets at the top of the Profile page: who the candidate is, what
they fit, and what they tend to go for. Written by the LLM from the composed profile and
cached in data/summary.json until that text changes.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from .llm import LLM

SECTIONS = ("about", "fits", "likes")

PROMPT = """You summarize a job seeker's profile for their own dashboard.
Read the profile below and reply with JSON only, no prose, in this shape:
{"about": [...], "fits": [...], "likes": [...]}

- about: 2-4 bullets on who they are: level, core stack, standout experience.
- fits: 2-4 bullets on the kinds of jobs they are a strong fit for, and why.
- likes: 2-4 bullets on what they tend to want or avoid, using their preferences, the jobs
  they applied to, and the reasons they gave for passing on jobs. If there are no marks yet,
  base it on their stated preferences only.

Only say they avoid or dislike something if their preferences or a reason they wrote says so.
Never guess why they passed on a job, and don't infer things the profile doesn't say.

Each bullet is one short line (under 15 words), written to them ("You ..."), concrete, no fluff.

<profile>
{profile}
</profile>"""


def source_hash(composed: str) -> str:
    """Changes when the profile or these instructions do, so either one makes the summary stale."""
    return hashlib.sha256((PROMPT + composed).encode("utf-8")).hexdigest()[:16]


def _parse(text: str) -> dict[str, list[str]]:
    match = re.search(r"\{.*\}", text or "", re.S)  # tolerate code fences and stray prose
    if not match:
        raise ValueError("The LLM didn't return a summary. Try again.")
    raw = json.loads(match.group(0))
    out = {k: [str(b).strip() for b in raw.get(k, []) if str(b).strip()][:4] for k in SECTIONS}
    if not any(out.values()):
        raise ValueError("The LLM returned an empty summary. Try again.")
    return out


def _without_bare_dismissals(composed: str) -> str:
    """Drop the list of not-interested titles: given only a title, models guess the reason
    ("night shift" in the title becomes "you avoid night shifts"). Written reasons stay."""
    return "\n".join(l for l in composed.splitlines() if not l.startswith("- Marked not interested:"))


def summarize(llm: LLM, composed: str) -> dict:
    profile = _without_bare_dismissals(composed)
    turn = llm.complete([{"role": "user", "content": PROMPT.replace("{profile}", profile)}])
    return {
        **_parse(turn.content or ""),
        "source_hash": source_hash(composed),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),  # with offset: the container runs on UTC
    }


class SummaryStore:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "summary.json"

    def load(self) -> dict | None:
        if not self.path.exists():
            return None
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, summary: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
