"""FastAPI backend with fake source, Jev and LLM (no network)."""

import time

import pytest
from fastapi.testclient import TestClient

from ojagent.api import build_profile, create_app, extract_resume_text
from tests.conftest import DESIGN_JOB, PROFILE, PYTHON_JOB, FakeSource
from tests.test_triage import FITS, FakeJev, FakeLLM

BASE_PROFILE = """# Me
## Preferences
- Minimum pay: PHP 50,000/month. Fully remote only.

## Experience
- Old experience line.
"""
RESUME = "Jane Dev. Python, FastAPI, PostgreSQL. " * 10


@pytest.fixture
def client(tmp_path):
    (tmp_path / "profile.md").write_text(BASE_PROFILE, encoding="utf-8")
    seen_profiles: list[str] = []

    class RecordingJev(FakeJev):
        def fit_probabilities(self, profile, jobs):
            seen_profiles.append(profile)
            return super().fit_probabilities(profile, jobs)

    app = create_app(
        make_source=lambda: FakeSource([PYTHON_JOB, DESIGN_JOB]),
        make_jev=lambda: RecordingJev({"100": 0.9, "200": 0.05}, FITS),
        make_llm=lambda: FakeLLM({PYTHON_JOB.title: {"summary": "FastAPI backend work."}}),
        profile_path=tmp_path / "profile.md",
        data_dir=tmp_path / "data",
        out_dir=tmp_path / "out",
    )
    c = TestClient(app)
    c.seen_profiles = seen_profiles
    c.tmp = tmp_path
    return c


def wait(client, run_id):
    for _ in range(100):
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise AssertionError("run did not finish")


def test_run_returns_ranked_jobs_and_saves_latest(client):
    start = client.post("/api/runs", json={"keyword": "fastapi"})
    assert start.status_code == 202
    run = wait(client, start.json()["id"])
    assert run["status"] == "done", run["error"]
    jobs = run["result"]["jobs"]
    assert [j["id"] for j in jobs] == ["100"] and jobs[0]["summary"] == "FastAPI backend work."
    assert run["result"]["keyword"] == "fastapi"
    assert client.get("/api/latest").json()["jobs"][0]["id"] == "100"


def test_uploaded_resume_replaces_experience_but_keeps_preferences(client):
    up = client.post("/api/resume", files={"file": ("resume.txt", RESUME.encode(), "text/plain")})
    assert up.status_code == 200 and up.json()["resume"]["filename"] == "resume.txt"
    wait(client, client.post("/api/runs", json={}).json()["id"])
    profile = client.seen_profiles[-1]
    assert "Jane Dev." in profile and "PHP 50,000" in profile
    assert "Old experience line." not in profile


def test_rejects_unreadable_or_unsupported_resumes(client):
    assert client.post("/api/resume", files={"file": ("cv.png", b"x" * 500, "image/png")}).status_code == 422
    assert client.post("/api/resume", files={"file": ("cv.txt", b"too short", "text/plain")}).status_code == 422


def test_one_run_at_a_time(client, monkeypatch):
    import ojagent.api as api

    monkeypatch.setattr(api, "triage", lambda *a, **k: time.sleep(0.3))
    first = client.post("/api/runs", json={})
    assert client.post("/api/runs", json={}).status_code == 409
    wait(client, first.json()["id"])


def test_keyword_is_validated(client):
    assert client.post("/api/runs", json={"keyword": ""}).status_code == 422
    assert client.post("/api/runs", json={"pages": 9}).status_code == 422


def test_latest_is_404_before_any_run(client):
    assert client.get("/api/latest").status_code == 404


def test_build_profile_without_resume_is_unchanged():
    assert build_profile(PROFILE, None) == PROFILE


def test_extract_docx_resume(tmp_path):
    import docx

    doc = docx.Document()
    doc.add_paragraph(RESUME)
    path = tmp_path / "cv.docx"
    doc.save(path)
    assert "Jane Dev." in extract_resume_text("cv.docx", path.read_bytes())
