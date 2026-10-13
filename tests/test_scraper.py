import httpx

from ojagent.scraper import OnlineJobsClient, parse_job_page, parse_search_page
from tests.conftest import FIXTURES


def test_parse_search_page_reads_all_cards():
    jobs = parse_search_page((FIXTURES / "search.html").read_text(encoding="utf-8", errors="replace"))
    assert len(jobs) == 30
    first = jobs[0]
    assert first.job_id == "1744849"
    assert first.title == "Web Developer & AI Automation Engineer"
    assert first.job_type == "Full Time"  # badge split out of the title
    assert first.posted_at == "2026-10-13 06:56:30"
    assert first.url.startswith("https://www.onlinejobs.ph/jobseekers/job/")
    assert "See More" not in first.snippet
    assert len({j.job_id for j in jobs}) == 30


def test_parse_job_page_extracts_facts_and_clean_description():
    job = parse_job_page((FIXTURES / "detail.html").read_text(encoding="utf-8"))
    assert job.job_id == "1748652"
    assert job.job_type == "Gig"
    assert job.salary == "N/A"
    assert job.date_updated == "Oct 13, 2026"
    assert job.skills == ["Local SEO", "Link Building", "Web Design & Page Layout"]
    assert job.description.startswith("Website Revamp + Optimisation")
    assert "<br" not in job.description and "ojfilter" not in job.description
    assert "----------" not in job.description  # masked contact info removed


def test_client_respects_crawl_delay(monkeypatch):
    sleeps = []
    monkeypatch.setattr("ojagent.scraper.time.sleep", lambda s: sleeps.append(s))
    html = (FIXTURES / "search.html").read_bytes()
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, content=html)

    client = OnlineJobsClient(http=httpx.Client(transport=httpx.MockTransport(handler)), delay=5)
    client.search("python")
    client.search("python", page=2)
    assert seen[0].endswith("/jobseekers/jobsearch?jobkeyword=python")
    assert "/jobseekers/jobsearch/60?" in seen[1]
    assert len(sleeps) == 1 and 4 < sleeps[0] <= 5
