"""FastAPI backend with fake source, Jev and LLM (no network)."""

import time

import pytest
from fastapi.testclient import TestClient

from ojagent.api import create_app, extract_resume_text
from tests.conftest import DESIGN_JOB, PYTHON_JOB, FakeSource
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
        make_llm=lambda: FakeLLM({PYTHON_JOB.title: {"role": "FastAPI backend work", "fits": ["FastAPI"]}}),
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
    assert [j["id"] for j in jobs] == ["100"] and jobs[0]["brief"]["role"] == "FastAPI backend work"
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
    assert client.post("/api/runs", json={"postings": 200}).status_code == 422
    assert client.post("/api/runs", json={"postings": 2}).status_code == 422


def test_latest_is_404_before_any_run(client):
    assert client.get("/api/latest").status_code == 404


def test_extract_docx_resume(tmp_path):
    import docx

    doc = docx.Document()
    doc.add_paragraph(RESUME)
    path = tmp_path / "cv.docx"
    doc.save(path)
    assert "Jane Dev." in extract_resume_text("cv.docx", path.read_bytes())


def test_active_run_lets_the_ui_resume_polling(client, monkeypatch):
    import ojagent.api as api

    assert client.get("/api/runs/active").json() == {"run": None}
    monkeypatch.setattr(api, "triage", lambda *a, **k: time.sleep(0.3))
    first = client.post("/api/runs", json={}).json()
    assert client.get("/api/runs/active").json()["run"]["id"] == first["id"]
    wait(client, first["id"])


def test_profile_is_seeded_from_profile_md_and_editable(client):
    view = client.get("/api/profile").json()
    prefs = view["profile"]["preferences"]
    assert prefs["min_pay_amount"] == 50000 and prefs["min_pay_currency"] == "PHP"
    assert "Old experience line." in view["profile"]["resume_text"]

    edited = view["profile"]
    edited["preferences"]["roles"] = "LLM agents"
    edited["resume_text"] = "Edited resume: built RAG systems."
    saved = client.put("/api/profile", json=edited).json()
    assert "roles in LLM agents" in saved["composed"] and "built RAG systems" in saved["composed"]

    wait(client, client.post("/api/runs", json={}).json()["id"])
    assert "built RAG systems" in client.seen_profiles[-1]


def test_marks_feed_the_learned_section(client):
    job = {"id": "100", "title": "Python Backend Developer", "type": "Full Time",
           "skills": ["Python", "FastAPI"], "pay_usd_month": {"min": 1000, "max": 1200}}
    r = client.put("/api/marks/100", json={"status": "applied", "job": job})
    assert r.json()["marks"] == {"100": "applied"}
    client.put("/api/marks/200", json={"status": "dismissed", "job": {"id": "200", "title": "Graphic Designer"}})

    view = client.get("/api/profile").json()
    assert view["learned"]["applied"] == ["Python Backend Developer"]
    assert "Applied to: Python Backend Developer." in view["composed"]
    assert "Marked not interested: Graphic Designer." in view["composed"]

    profile = view["profile"]
    profile["use_learned"] = False
    assert "Applied to" not in client.put("/api/profile", json=profile).json()["composed"]

    client.put("/api/marks/100", json={"status": None})
    assert client.get("/api/marks").json()["marks"] == {"200": "dismissed"}
    client.delete("/api/marks")
    assert client.get("/api/marks").json()["marks"] == {}


def test_mark_needs_the_job(client):
    assert client.put("/api/marks/100", json={"status": "applied"}).status_code == 422


def test_removing_resume_restores_profile_md_text(client):
    client.post("/api/resume", files={"file": ("resume.txt", RESUME.encode(), "text/plain")})
    view = client.delete("/api/resume").json()
    assert view["resume"] is None and "Old experience line." in view["profile"]["resume_text"]
