import httpx
import pytest

from ojagent.jobstreet import JobStreetClient, parse_jobstreet_job, parse_jobstreet_search, search_slug
from tests.conftest import FIXTURES

SEARCH_HTML = (FIXTURES / "jobstreet_search.html").read_text(encoding="utf-8")
DETAIL_HTML = (FIXTURES / "jobstreet_detail.html").read_text(encoding="utf-8")


def test_parse_search_reads_all_cards():
    jobs = parse_jobstreet_search(SEARCH_HTML)
    assert len(jobs) == 30
    assert len({j.job_id for j in jobs}) == 30
    first = jobs[0]
    assert first.job_id == "95312624"
    assert first.title == "Full Stack Python Developer"
    assert first.url == "https://ph.jobstreet.com/job/95312624"
    assert first.job_type == "Full time"
    assert first.posted_at == "2026-10-16T05:28:19.000Z"


def test_salary_is_none_when_hidden_and_set_when_shown():
    by_id = {j.job_id: j for j in parse_jobstreet_search(SEARCH_HTML)}
    assert by_id["95312624"].salary is None  # salaryLabel ""
    assert by_id["95289179"].salary == "₱40,000 – ₱60,000 per month"


def test_work_arrangement_appears_in_snippet():
    by_id = {j.job_id: j for j in parse_jobstreet_search(SEARCH_HTML)}
    assert by_id["95312624"].snippet.startswith(
        "Citco · Makati City, Metro Manila · Hybrid. Develop new applications"
    )
    assert "· On-site." in by_id["95312761"].snippet
    # No companyName on this card: falls back to advertiser.description.
    assert "· Remote." in by_id["95289179"].snippet
    assert by_id["95289179"].snippet.startswith("Centro ASSIST")


def test_parse_job_detail_extracts_facts_and_clean_description():
    job = parse_jobstreet_job(DETAIL_HTML)
    assert job.job_id == "95312624"
    assert job.title == "Full Stack Python Developer"
    assert job.url == "https://ph.jobstreet.com/job/95312624"
    assert job.job_type == "Full time"
    assert job.salary is None
    assert job.date_updated == "2026-10-16T05:28:19.963Z"
    assert job.skills == []
    assert job.description.startswith(
        "Company: CITCO INTERNATIONAL SUPPORT SERVICES LIMITED-PHILIPPINE ROHQ\n"
        "Location: Makati City, Metro Manila\n"
        "Work arrangement: Hybrid\n\n"
    )
    body = job.description.split("\n\n", 1)[1]
    assert "About the role" in body
    assert "- Develop new applications that serve existing software systems" in body
    assert "<" not in job.description and ">" not in job.description


def test_pages_without_state_script_raise():
    with pytest.raises(ValueError):
        parse_jobstreet_job("<html><body>no state here</body></html>")
    with pytest.raises(ValueError):
        parse_jobstreet_search("<html><body>no state here</body></html>")


def test_expired_posting_raises():
    expired = DETAIL_HTML.replace('"isExpired":false', '"isExpired":true')
    assert expired != DETAIL_HTML
    with pytest.raises(ValueError):
        parse_jobstreet_job(expired)


@pytest.mark.parametrize(
    ("keyword", "slug"),
    [
        ("python", "python"),
        ("AI engineer", "ai-engineer"),
        ("  Data   Analyst ", "data-analyst"),
        ("C++/C#", "cpp-csharp"),
    ],
)
def test_search_slug(keyword, slug):
    assert search_slug(keyword) == slug


def _client(seen: list[httpx.URL], delay: float = 0) -> JobStreetClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        body = DETAIL_HTML if request.url.path.startswith("/job/") else SEARCH_HTML
        return httpx.Response(200, content=body.encode("utf-8"))

    return JobStreetClient(http=httpx.Client(transport=httpx.MockTransport(handler)), delay=delay)


def test_page_zero_sends_sortmode_and_no_page_param():
    seen: list[httpx.URL] = []
    client = _client(seen)
    assert len(client.search("AI engineer")) == 30
    url = seen[0]
    assert url.path == "/ai-engineer-jobs"
    assert url.params == httpx.QueryParams({"sortmode": "ListedDate"})


def test_later_page_sends_one_based_page_number():
    seen: list[httpx.URL] = []
    client = _client(seen)
    client.search("python", page=2)
    assert seen[0].path == "/python-jobs"
    assert seen[0].params == httpx.QueryParams({"sortmode": "ListedDate", "page": "3"})


def test_client_never_requests_api_or_graphql():
    seen: list[httpx.URL] = []
    client = _client(seen)
    # Searching for "graphql" or "api" is fine: those are /graphql-jobs and /api-jobs.
    client.search("graphql")
    client.search("api", page=1)
    client.get_job("95312624")
    assert len(seen) == 3
    assert not any(u.path == "/graphql" or u.path.startswith(("/api/", "/graphql/")) for u in seen)
    with pytest.raises(ValueError):
        client._get("/api/jobsearch/x")
    with pytest.raises(ValueError):
        client._get("/graphql")
    assert len(seen) == 3


def test_client_respects_crawl_delay(monkeypatch):
    sleeps = []
    monkeypatch.setattr("ojagent.jobstreet.time.sleep", lambda s: sleeps.append(s))
    seen: list[httpx.URL] = []
    client = _client(seen, delay=5)
    client.search("python")
    client.search("python", page=2)
    client.get_job("95312624")
    assert len(seen) == 3
    assert len(sleeps) == 2 and all(4 < s <= 5 for s in sleeps)
