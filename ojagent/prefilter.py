"""Fast first-pass fit filter, run on search results before the agent reads them.

Jev (TypeSafe AI) is a decision-only model: it answers typed questions with
probabilities instead of text. One call scores every card on a results page, so
clearly irrelevant postings never cost a 5 s crawl or an LLM assessment.
"""

from __future__ import annotations

import time
from typing import Protocol

import httpx

from .models import JobSummary

JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-1.13.0"
RETRY_STATUSES = {429, 529}


class Prefilter(Protocol):
    def fit_probabilities(self, profile: str, jobs: list[JobSummary]) -> dict[str, float]:
        """Probability (0-1) that the candidate is a realistic fit, keyed by job_id."""
        ...


class JevPrefilter:
    def __init__(
        self,
        api_key: str,
        model: str = JEV_MODEL,
        client: httpx.Client | None = None,
        retries: int = 3,
    ):
        self.model = model
        self.retries = retries
        self.client = client or httpx.Client(timeout=15)
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self.latencies_ms: list[float] = []
        self.input_tokens = 0

    def fit_probabilities(self, profile: str, jobs: list[JobSummary]) -> dict[str, float]:
        if not jobs:
            return {}
        body = {
            "state": {
                "profile": profile,
                "jobs": {j.job_id: {"title": j.title, "snippet": j.snippet} for j in jobs},
            },
            "questions": {
                j.job_id: {
                    "type": "noul",
                    "instructions": (
                        f"The candidate in `profile` is a realistic applicant for the job "
                        f"posting `jobs.{j.job_id}`: it is in their field and matches their "
                        f"stated preferences."
                    ),
                }
                for j in jobs
            },
        }
        answers = self.ask(body["state"], body["questions"])
        return {job_id: float(a["noul"]) for job_id, a in answers.items()}

    def ask(self, state: str | dict, questions: dict) -> dict:
        """One System One call; returns the raw answers keyed by question id."""
        data = self._post({"model": self.model, "state": state, "questions": questions})
        self.input_tokens += data.get("usage", {}).get("input_tokens", 0)
        return data["answers"]

    def _post(self, body: dict) -> dict:
        for attempt in range(self.retries + 1):
            start = time.perf_counter()
            resp = self.client.post(JEV_URL, json=body, headers=self.headers)
            self.latencies_ms.append((time.perf_counter() - start) * 1000)
            if resp.status_code not in RETRY_STATUSES or attempt == self.retries:
                resp.raise_for_status()
                return resp.json()
            time.sleep(2**attempt)
        raise AssertionError("unreachable")
