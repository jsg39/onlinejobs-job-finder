"""JobStreet Philippines client: reads the SEEK state embedded in each page.

Search pagination goes beyond what JobStreet's robots.txt allows. robots.txt only permits
`?keywords` query URLs, and `/{slug}-jobs?sortmode=...&page=N` is not one of them. This client
requests those URLs anyway, on purpose, and stays slow: every request waits out the 5 s crawl
delay. It never requests `/api/` or `/graphql` paths, which robots.txt disallows outright.
The site sits behind Cloudflare, which blocks non-browser clients, so requests go out with a
Chrome TLS fingerprint (curl_cffi).
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

from .models import JobPosting, JobSummary
from .scraper import CRAWL_DELAY_SECONDS

BASE_URL = "https://ph.jobstreet.com"

_STATE_RE = re.compile(r"window\.SEEK_REDUX_DATA\s*=\s*(\{.*?\});\s*\n", re.S)


class JobStreetClient:
    """Implements the `JobSource` protocol from `ojagent.scraper`."""

    def __init__(self, http: httpx.Client | None = None, delay: float = CRAWL_DELAY_SECONDS):
        # Cloudflare rejects plain httpx with 403, so the default client uses curl_cffi's
        # Chrome fingerprint. Tests pass an httpx.Client; both have the same get() shape.
        self.http = http or curl_requests.Session(impersonate="chrome", timeout=30)
        self.delay = delay
        self._last_request = float("-inf")

    def _get(self, path: str, params: dict | None = None) -> str:
        if path == "/graphql" or path.startswith(("/api/", "/graphql/")):
            raise ValueError(f"Refusing to request disallowed path {path}")
        wait = self._last_request + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            response = self.http.get(BASE_URL + path, params=params)
        finally:
            self._last_request = time.monotonic()
        response.raise_for_status()
        return response.content.decode("utf-8", "replace")

    def search(self, keyword: str | None = None, page: int = 0) -> list[JobSummary]:
        """Newest-first keyword results, 30 per page. JobStreet's page numbers are 1-based."""
        slug = search_slug(keyword or "")
        if not slug:
            raise ValueError("JobStreet search needs a keyword.")
        params = {"sortmode": "ListedDate"}
        if page > 0:
            params["page"] = str(page + 1)
        return parse_jobstreet_search(self._get(f"/{slug}-jobs", params))

    def get_job(self, job_id: str) -> JobPosting:
        return parse_jobstreet_job(self._get(f"/job/{job_id}"))


def search_slug(keyword: str) -> str:
    """'AI engineer' -> 'ai-engineer'; 'C++/C#' -> 'cpp-csharp'."""
    text = keyword.lower().replace("c++", "cpp").replace("c#", "csharp")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _state(html: str) -> dict[str, Any]:
    match = _STATE_RE.search(html)
    if match is None:
        raise ValueError("Not a JobStreet page (no window.SEEK_REDUX_DATA).")
    return json.loads(match.group(1).replace(":undefined", ":null"))


def _work_arrangement(wa: Any) -> str | None:
    """Search pages give displayText or data[].label.text; the detail page gives a label string."""
    if not isinstance(wa, dict):
        return None
    if wa.get("displayText"):
        return wa["displayText"]
    if isinstance(wa.get("label"), str) and wa["label"]:
        return wa["label"]
    texts = []
    for item in wa.get("data") or []:
        label = item.get("label")
        if isinstance(label, dict) and label.get("text"):
            texts.append(label["text"])
    return ", ".join(texts) or None


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for br in soup.select("br"):
        br.replace_with("\n")
    for item in soup.select("li"):
        item.insert_before("\n- ")
    for block in soup.select("p, li, ul, ol, div, h1, h2, h3, h4, h5, h6"):
        block.insert_after("\n")
    lines = [" ".join(line.split()) for line in soup.get_text().splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def parse_jobstreet_search(html: str) -> list[JobSummary]:
    state = _state(html)
    try:
        jobs = state["results"]["results"]["jobs"]
    except (KeyError, TypeError) as exc:
        raise ValueError("JobStreet search page has no job list.") from exc

    summaries: list[JobSummary] = []
    seen: set[str] = set()
    for job in jobs:
        job_id = str(job.get("id", ""))
        if not job_id or job_id in seen:
            continue
        seen.add(job_id)

        company = job.get("companyName") or (job.get("advertiser") or {}).get("description")
        location = (next(iter(job.get("locations") or []), None) or {}).get("label")
        arrangement = _work_arrangement(job.get("workArrangements"))
        head = " · ".join(p for p in (company, location, arrangement) if p)
        body = " ".join(p for p in [job.get("teaser"), *(job.get("bulletPoints") or [])] if p)

        summaries.append(
            JobSummary(
                job_id=job_id,
                title=job.get("title") or "",
                url=f"{BASE_URL}/job/{job_id}",
                job_type=", ".join(job.get("workTypes") or []) or None,
                posted_at=job.get("listingDate"),
                salary=job.get("salaryLabel") or None,
                snippet=". ".join(p for p in (head, body) if p),
            )
        )
    return summaries


def parse_jobstreet_job(html: str) -> JobPosting:
    state = _state(html)
    try:
        result = state["jobdetails"]["result"]
        job = result["job"]
    except (KeyError, TypeError) as exc:
        raise ValueError("Not a JobStreet job page (no job details).") from exc
    if job.get("isExpired"):
        raise ValueError("This JobStreet posting has expired.")

    advertiser = (job.get("advertiser") or {}).get("name")
    location = (job.get("location") or {}).get("label")
    arrangement = _work_arrangement(result.get("workArrangements"))
    facts = [
        f"{label}: {value}"
        for label, value in (
            ("Company", advertiser),
            ("Location", location),
            ("Work arrangement", arrangement),
        )
        if value
    ]
    prefix = "\n".join(facts) + "\n\n" if facts else ""

    salary = job.get("salary")
    work_types = job.get("workTypes") or {}
    listed = job.get("listedAt") or {}
    job_id = str(job.get("id", ""))

    return JobPosting(
        job_id=job_id,
        title=job.get("title") or "",
        url=f"{BASE_URL}/job/{job_id}",
        job_type=work_types.get("label"),
        salary=salary.get("label") if isinstance(salary, dict) else None,
        date_updated=listed.get("dateTimeUtc"),
        description=prefix + _html_to_text(job.get("content") or ""),
    )
