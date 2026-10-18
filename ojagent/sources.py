"""The job sites the app can search: key -> (label, client class, max postings per run)."""

from __future__ import annotations

from itertools import zip_longest

from .jobstreet import JobStreetClient
from .models import JobPosting, JobSummary
from .scraper import JobSource, OnlineJobsClient


class AllSites:
    """Searches every site at once. Cards are interleaved site by site, so the first N cards
    (what a run scans) split about evenly; when one site runs out, the others fill in."""

    def __init__(self, clients: list[JobSource] | None = None):
        self.clients = clients if clients is not None else [OnlineJobsClient(), JobStreetClient()]
        self._exhausted: set[int] = set()
        self._owner: dict[str, JobSource] = {}  # job id -> client that listed it

    def search(self, keyword: str | None = None, page: int = 0) -> list[JobSummary]:
        groups: list[list[JobSummary]] = []
        for i, client in enumerate(self.clients):
            found = [] if i in self._exhausted else client.search(keyword, page)
            if not found:
                self._exhausted.add(i)
            for card in found:
                self._owner[card.job_id] = client
            groups.append(found)
        return [card for row in zip_longest(*groups) for card in row if card is not None]

    def get_job(self, job_id: str) -> JobPosting:
        client = self._owner.get(job_id)
        if client is None:
            raise KeyError(f"Job {job_id} was not in any search results.")
        return client.get_job(job_id)


SOURCES: dict[str, tuple[str, type, int]] = {
    "onlinejobs": ("onlinejobs.ph", OnlineJobsClient, 90),
    "jobstreet": ("JobStreet", JobStreetClient, 90),
    "all": ("onlinejobs.ph + JobStreet", AllSites, 90),  # 90 in total, split between the sites
}


def make_source(key: str) -> JobSource:
    """A fresh client for the site `key` (one of SOURCES)."""
    _, client_class, _ = SOURCES[key]
    return client_class()
