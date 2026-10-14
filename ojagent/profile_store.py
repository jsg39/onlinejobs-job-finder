"""The candidate profile the app ranks against: editable preferences, resume text, and
what the user's applied / not-interested marks reveal about what they want.

Stored as JSON in data/. On first use it is seeded from profile.md (and a previously
uploaded data/resume.txt), so the CLI and the app start from the same facts.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .pay import usd_per_month

Period = Literal["hour", "month", "year"]
PERIOD_WORD = {"hour": "hour", "month": "month", "year": "year"}
LEARN_LIMIT = 10  # most recent marks quoted in the profile


class Preferences(BaseModel):
    roles: str = Field(default="backend, AI/LLM, full-stack, or data engineering", max_length=500)
    remote_only: bool = True
    min_pay_amount: float = Field(default=0, ge=0)
    min_pay_currency: Literal["USD", "PHP"] = "USD"
    min_pay_period: Period = "month"
    not_interested: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=1000)


class Profile(BaseModel):
    preferences: Preferences = Field(default_factory=Preferences)
    resume_text: str = Field(default="", max_length=30_000)
    resume_meta: dict | None = None  # filename and upload time of the last uploaded file
    use_learned: bool = True


class JobSnapshot(BaseModel):
    """What the app keeps about a job the user marked, enough to learn from."""

    id: str
    title: str
    type: str | None = None
    skills: list[str] = Field(default_factory=list)
    pay_usd_month: dict | None = None
    role: str | None = None  # the brief's one-line role, if there was one


class Mark(BaseModel):
    status: Literal["applied", "dismissed"]
    job: JobSnapshot
    at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


def _section(markdown: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", markdown, re.M | re.S)
    return match.group(1).strip() if match else ""


def seed_from_markdown(profile_md: str, resume_txt: str | None = None) -> Profile:
    """Read the preferences out of profile.md; everything else there becomes the resume text."""
    prefs_text = _section(profile_md, "Preferences")
    prefs = Preferences()
    if m := re.search(r"Looking for:\s*(.+)", prefs_text):
        line = m.group(1)
        prefs.remote_only = "remote" in line.lower()
        if roles := re.search(r"roles in ([^.]+)", line):
            prefs.roles = roles.group(1).strip()
    if m := re.search(r"Minimum pay:\s*(.+)", prefs_text):
        line = m.group(1).split("(")[0]  # "PHP 50,000/month (about USD 5/hour)": the floor, not the note
        if amount := re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(k)?", line, re.I):
            value = float(amount.group(1).replace(",", ""))
            prefs.min_pay_amount = value * 1000 if amount.group(2) else value
        prefs.min_pay_currency = "PHP" if re.search(r"php|₱|peso", line, re.I) else "USD"
        prefs.min_pay_period = "hour" if re.search(r"hour|/hr", line, re.I) else (
            "year" if re.search(r"year|annual", line, re.I) else "month"
        )
    if m := re.search(r"Not interested in:\s*(.+)", prefs_text):
        prefs.not_interested = m.group(1).strip().rstrip(".")

    if resume_txt:
        resume = resume_txt
    else:  # profile.md minus its title, intro and preferences
        body = re.sub(r"^## Preferences\n.*?(?=^## |\Z)", "", profile_md, flags=re.M | re.S)
        resume = body[body.find("## "):].strip() if "## " in body else body.strip()
    return Profile(preferences=prefs, resume_text=resume)


def learned_summary(marks: dict[str, Mark]) -> dict:
    ordered = sorted(marks.values(), key=lambda m: m.at, reverse=True)
    applied = [m.job for m in ordered if m.status == "applied"]
    dismissed = [m.job for m in ordered if m.status == "dismissed"]
    skills = Counter(s for j in applied for s in j.skills if s.lower() not in {"software", "other"})
    pays = sorted(j.pay_usd_month["max"] for j in applied if j.pay_usd_month)
    return {
        "applied": [j.title for j in applied],
        "dismissed": [j.title for j in dismissed],
        "top_skills": [s for s, n in skills.most_common(8) if n >= 2 or len(applied) < 3],
        "types": [t for t, _ in Counter(j.type for j in applied if j.type).most_common(2)],
        "median_pay_usd_month": pays[len(pays) // 2] if pays else None,
    }


def compose(profile: Profile, marks: dict[str, Mark]) -> str:
    """The profile text Jev and the LLM rank against."""
    p = profile.preferences
    lines = ["# Candidate profile", "", "## Preferences"]
    looking = f"- Looking for: roles in {p.roles}" if p.roles else "- Looking for: any role that fits the resume"
    if p.remote_only:
        looking += ". Fully remote only; no on-site or hybrid work"
    lines.append(looking + ".")
    if p.min_pay_amount:
        amount = f"{p.min_pay_currency} {p.min_pay_amount:,.0f}/{PERIOD_WORD[p.min_pay_period]}"
        usd = usd_per_month(amount)
        lines.append(f"- Minimum pay: {amount}" + (f" (about USD {usd['min']:,}/month)." if usd else "."))
    if p.not_interested:
        lines.append(f"- Not interested in: {p.not_interested}.")
    if p.notes:
        lines.append(f"- Also: {p.notes}")

    learned = learned_summary(marks)
    if profile.use_learned and (learned["applied"] or learned["dismissed"]):
        lines += ["", "## Learned from the candidate's choices"]
        if learned["applied"]:
            lines.append("- Applied to: " + "; ".join(learned["applied"][:LEARN_LIMIT]) + ".")
        if learned["top_skills"]:
            lines.append("- Skills common in jobs they applied to: " + ", ".join(learned["top_skills"]) + ".")
        if learned["types"]:
            lines.append("- Job types they applied to: " + ", ".join(learned["types"]) + ".")
        if learned["median_pay_usd_month"]:
            lines.append(f"- Typical pay of jobs they applied to: about USD {learned['median_pay_usd_month']:,}/month.")
        if learned["dismissed"]:
            lines.append("- Marked not interested: " + "; ".join(learned["dismissed"][:LEARN_LIMIT]) + ".")

    lines += ["", "## Resume", profile.resume_text.strip() or "(no resume yet)"]
    return "\n".join(lines) + "\n"


class ProfileStore:
    def __init__(self, data_dir: Path, seed_markdown: Path):
        self.profile_path = data_dir / "profile.json"
        self.marks_path = data_dir / "marks.json"
        self.legacy_resume = data_dir / "resume.txt"
        self.seed_markdown = seed_markdown
        self.data_dir = data_dir

    def load(self) -> Profile:
        if self.profile_path.exists():
            return Profile.model_validate_json(self.profile_path.read_text(encoding="utf-8"))
        resume = self.legacy_resume.read_text(encoding="utf-8") if self.legacy_resume.exists() else None
        md = self.seed_markdown.read_text(encoding="utf-8") if self.seed_markdown.exists() else ""
        return seed_from_markdown(md, resume)

    def save(self, profile: Profile) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.profile_path.write_text(profile.model_dump_json(indent=1), encoding="utf-8")

    def marks(self) -> dict[str, Mark]:
        if not self.marks_path.exists():
            return {}
        raw = json.loads(self.marks_path.read_text(encoding="utf-8"))
        return {k: Mark.model_validate(v) for k, v in raw.items()}

    def set_mark(self, job_id: str, mark: Mark | None) -> dict[str, Mark]:
        marks = self.marks()
        if mark is None:
            marks.pop(job_id, None)
        else:
            marks[job_id] = mark
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.marks_path.write_text(
            json.dumps({k: v.model_dump() for k, v in marks.items()}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        return marks

    def clear_marks(self) -> None:
        self.marks_path.unlink(missing_ok=True)

    def composed(self) -> str:
        return compose(self.load(), self.marks())
