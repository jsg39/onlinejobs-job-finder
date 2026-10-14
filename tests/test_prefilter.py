"""Jev client against a mocked API: request shape and rate-limit retry (no network)."""

import json

import httpx

from ojagent.models import JobSummary
from ojagent.prefilter import JEV_URL, JevPrefilter
from tests.conftest import PROFILE


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
