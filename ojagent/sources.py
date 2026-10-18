"""The job sites the app can search: key -> (label, client class, max postings per run)."""

from __future__ import annotations

from .jobstreet import JobStreetClient
from .scraper import JobSource, OnlineJobsClient

SOURCES: dict[str, tuple[str, type, int]] = {
    "onlinejobs": ("onlinejobs.ph", OnlineJobsClient, 90),
    "jobstreet": ("JobStreet", JobStreetClient, 90),
}


def make_source(key: str) -> JobSource:
    """A fresh client for the site `key` (one of SOURCES)."""
    _, client_class, _ = SOURCES[key]
    return client_class()
