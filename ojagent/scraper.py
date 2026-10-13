"""Polite onlinejobs.ph client: honours the robots.txt crawl-delay and parses HTML."""

from __future__ import annotations

import re
import time
from typing import Protocol

import httpx
from bs4 import BeautifulSoup, Tag

from .models import JobPosting, JobSummary

BASE_URL = "https://www.onlinejobs.ph"
USER_AGENT = "Mozilla/5.0 (compatible; ojagent/0.1; personal job search)"
CRAWL_DELAY_SECONDS = 5.0  # from https://www.onlinejobs.ph/robots.txt

_JOB_ID_RE = re.compile(r"-(\d+)$")


class JobSource(Protocol):
    """Anything that can list and fetch jobs. The eval harness swaps in a fake."""

    def search(self, keyword: str | None = None, page: int = 0) -> list[JobSummary]: ...

    def get_job(self, job_id: str) -> JobPosting: ...


class OnlineJobsClient:
    def __init__(self, http: httpx.Client | None = None, delay: float = CRAWL_DELAY_SECONDS):
        self.http = http or httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True
        )
        self.delay = delay
        self._last_request = float("-inf")

    def _get(self, path: str, params: dict | None = None) -> str:
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
        """Latest postings, newest first. 30 results per page."""
        path = "/jobseekers/jobsearch" + (f"/{page * 30}" if page else "")
        params = {"jobkeyword": keyword} if keyword else None
        return parse_search_page(self._get(path, params))

    def get_job(self, job_id: str) -> JobPosting:
        # The site redirects /jobseekers/job/<id> to the canonical slug URL.
        return parse_job_page(self._get(f"/jobseekers/job/{job_id}"))


def _text(node: Tag | None) -> str | None:
    if node is None:
        return None
    text = " ".join(node.get_text(" ", strip=True).split())
    return text or None


def parse_search_page(html: str) -> list[JobSummary]:
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[JobSummary] = []
    for box in soup.select("div.jobpost-cat-box"):
        link = box.find_parent("a", href=True)
        if link is None:
            continue
        href = link["href"].split("?")[0]
        match = _JOB_ID_RE.search(href)
        if not match:
            continue
        heading = box.select_one("h4")
        badge = heading.select_one("span.badge") if heading else None
        if badge:
            badge.extract()
        posted = box.select_one("p[data-temp]")
        desc = box.select_one("div.desc")
        if desc:
            for see_more in desc.select("a"):
                see_more.decompose()
        jobs.append(
            JobSummary(
                job_id=match.group(1),
                title=_text(heading) or "",
                url=BASE_URL + href,
                job_type=_text(badge),
                posted_at=posted["data-temp"] if posted else None,
                salary=_text(box.select_one("dd.col")),
                snippet=_text(desc) or "",
            )
        )
    return jobs


def parse_job_page(html: str) -> JobPosting:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one("h1.job__title")
    if title is None:
        raise ValueError("Not a job page (no h1.job__title); the posting may be closed.")

    facts: dict[str, str | None] = {}
    for label in soup.select("div.job-post h3"):
        facts[label.get_text(strip=True).upper()] = _text(label.find_next_sibling("p"))

    desc = soup.select_one("#job-description")
    if desc is None:
        raise ValueError("Job page has no #job-description.")
    for hidden in desc.select("ojfilter"):  # contact details the site masks
        hidden.decompose()
    for br in desc.select("br"):
        br.replace_with("\n")
    lines = [" ".join(line.split()) for line in desc.get_text().splitlines()]
    description = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()

    canonical = soup.select_one("link[rel=canonical]")
    job_id = title.get("data-jobid", "")
    url = canonical["href"] if canonical else f"{BASE_URL}/jobseekers/job/{job_id}"

    return JobPosting(
        job_id=job_id,
        title=_text(title) or "",
        url=url,
        job_type=facts.get("TYPE OF WORK"),
        salary=facts.get("WAGE / SALARY"),
        hours_per_week=facts.get("HOURS PER WEEK"),
        date_updated=facts.get("DATE UPDATED"),
        skills=[s for s in (_text(a) for a in soup.select("a.card-worker-topskill")) if s],
        description=description,
    )
