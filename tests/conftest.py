from __future__ import annotations

import json
from pathlib import Path

import pytest

from ojagent.llm import ToolCall, Turn
from ojagent.models import JobPosting, JobSummary

FIXTURES = Path(__file__).parent / "fixtures"

PROFILE = """# Test Candidate
## Experience
- Built REST APIs with FastAPI and PostgreSQL for a logistics company.
- Lead three developers on a multi-tenant rental platform (FastAPI, React).
## Skills
- Languages: Python, SQL
- Web: FastAPI, React
"""

PYTHON_JOB = JobPosting(
    job_id="100",
    title="Python Backend Developer",
    url="https://www.onlinejobs.ph/jobseekers/job/100",
    job_type="Full Time",
    salary="$1,000/month",
    description=(
        "We need a backend developer.\n"
        "Requirements:\n- 2+ years of Python and FastAPI\n- Experience with PostgreSQL\n"
        "- Nice to have: Kubernetes\n"
        "Put 'PINEAPPLE' in your subject line so we know you read this."
    ),
    skills=["Python", "FastAPI"],
)

DESIGN_JOB = JobPosting(
    job_id="200",
    title="Graphic Designer",
    url="https://www.onlinejobs.ph/jobseekers/job/200",
    job_type="Part Time",
    description="Design social media graphics in Canva and Photoshop.",
)


class FakeSource:
    def __init__(self, postings: list[JobPosting]):
        self.postings = {p.job_id: p for p in postings}
        self.fetches: list[str] = []

    def search(self, keyword=None, page=0):
        return [
            JobSummary(job_id=p.job_id, title=p.title, url=p.url, snippet=p.description[:80])
            for p in self.postings.values()
            if page == 0
        ]

    def get_job(self, job_id):
        self.fetches.append(job_id)
        if job_id not in self.postings:
            raise ValueError("Not a job page")
        return self.postings[job_id]


class ScriptedLLM:
    """Replays a fixed list of turns; records what it was sent."""

    model = "scripted"

    def __init__(self, turns: list[list[tuple[str, dict]] | str]):
        self.turns = list(turns)
        self.seen: list[list[dict]] = []

    def complete(self, messages, tools):
        self.seen.append(list(messages))
        if not self.turns:
            return Turn(content="(out of script)")
        turn = self.turns.pop(0)
        if isinstance(turn, str):
            return Turn(content=turn)
        return Turn(
            content=None,
            tool_calls=[
                ToolCall(f"call_{len(self.seen)}_{i}", name, json.dumps(args))
                for i, (name, args) in enumerate(turn)
            ],
            input_tokens=100,
            output_tokens=20,
        )


@pytest.fixture
def source():
    return FakeSource([PYTHON_JOB, DESIGN_JOB])
