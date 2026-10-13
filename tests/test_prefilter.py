"""Jev prefilter: request shape, filtering in search_jobs, and failing open (no network)."""

import json

import httpx

from ojagent.agent import Agent
from ojagent.models import FitAssessment, JobSummary
from ojagent.prefilter import JEV_URL, JevPrefilter
from ojagent.report import render
from ojagent.store import Store
from ojagent.tools import SearchJobsArgs, Toolbox
from tests.conftest import PROFILE, ScriptedLLM
from tests.test_agent import GOOD_ASSESSMENT


class FixedPrefilter:
    def __init__(self, probs=None, error=None):
        self.probs = probs or {}
        self.error = error
        self.calls: list[list[str]] = []

    def fit_probabilities(self, profile, jobs):
        self.calls.append([j.job_id for j in jobs])
        if self.error:
            raise self.error
        return {j.job_id: self.probs[j.job_id] for j in jobs}


def jev_client(handler):
    return JevPrefilter("test-key", client=httpx.Client(transport=httpx.MockTransport(handler)), retries=1)


def test_jev_request_asks_one_noul_per_job():
    sent = {}

    def handler(request):
        sent["url"] = str(request.url)
        sent["auth"] = request.headers["authorization"]
        sent["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "model": "jev-1.13.0",
            "answers": {"1": {"type": "noul", "noul": 0.9}, "2": {"type": "noul", "noul": 0.05}},
            "usage": {"input_tokens": 300, "output_tokens": 0},
        })

    jev = jev_client(handler)
    jobs = [JobSummary(job_id="1", title="Python Dev", url="u"), JobSummary(job_id="2", title="Designer", url="u")]
    assert jev.fit_probabilities(PROFILE, jobs) == {"1": 0.9, "2": 0.05}
    assert sent["url"] == JEV_URL and sent["auth"] == "Bearer test-key"
    assert sent["body"]["state"]["profile"] == PROFILE
    assert set(sent["body"]["questions"]) == {"1", "2"}
    assert all(q["type"] == "noul" for q in sent["body"]["questions"].values())
    assert "`jobs.2`" in sent["body"]["questions"]["2"]["instructions"]
    assert jev.input_tokens == 300 and len(jev.latencies_ms) == 1


def test_jev_retries_when_rate_limited(monkeypatch):
    monkeypatch.setattr("ojagent.prefilter.time.sleep", lambda s: None)
    statuses = iter([429, 200])

    def handler(request):
        status = next(statuses)
        body = {"answers": {"1": {"type": "noul", "noul": 0.7}}} if status == 200 else {}
        return httpx.Response(status, json=body)

    jev = jev_client(handler)
    assert jev.fit_probabilities(PROFILE, [JobSummary(job_id="1", title="t", url="u")]) == {"1": 0.7}


def test_search_hides_clear_mismatches(source):
    pre = FixedPrefilter({"100": 0.85, "200": 0.03})
    box = Toolbox(source, Store(), PROFILE, "run", prefilter=pre)
    result = box.search_jobs(SearchJobsArgs())
    assert [j["job_id"] for j in result["jobs"]] == ["100"]
    assert result["hidden_as_clear_mismatches"] == 1
    assert box.prefiltered == {"200": ("Graphic Designer", 0.03)}


def test_prefilter_skips_already_assessed_jobs(source):
    store = Store()
    store.save_posting(source.postings["100"])
    store.save_assessment(FitAssessment.model_validate(GOOD_ASSESSMENT), "old-run")
    pre = FixedPrefilter({"200": 0.9})
    box = Toolbox(source, store, PROFILE, "run", prefilter=pre)
    box.search_jobs(SearchJobsArgs())
    assert pre.calls == [["200"]]


def test_prefilter_failure_shows_every_job(source):
    pre = FixedPrefilter(error=httpx.ConnectError("down"))
    box = Toolbox(source, Store(), PROFILE, "run", prefilter=pre)
    result = box.search_jobs(SearchJobsArgs())
    assert result["count"] == 2 and result["hidden_as_clear_mismatches"] == 0
    assert box.prefilter_errors == ["ConnectError: down"]


def test_run_result_reports_prefiltered_jobs(source):
    llm = ScriptedLLM([[("search_jobs", {})], [("finish", {"summary": "none"})]])
    agent = Agent(llm=llm, source=source, store=Store(), profile=PROFILE, max_steps=5,
                  prefilter=FixedPrefilter({"100": 0.1, "200": 0.02}))
    result = agent.run("go")
    assert set(result.prefiltered) == {"100", "200"}


def test_report_lists_skipped_jobs(source):
    llm = ScriptedLLM([[("search_jobs", {})], [("finish", {"summary": "none"})]])
    agent = Agent(llm=llm, source=source, store=Store(), profile=PROFILE, max_steps=5,
                  prefilter=FixedPrefilter({"100": 0.9, "200": 0.02}))
    report = render(agent.run("go"), [], "scripted")
    assert "Skipped by prefilter (1):** Graphic Designer (2%)" in report
