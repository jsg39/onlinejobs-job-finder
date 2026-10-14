"""Postings as parsed from onlinejobs.ph search and detail pages."""

from __future__ import annotations

from pydantic import BaseModel, Field

class JobSummary(BaseModel):
    """One card from the search results page."""

    job_id: str
    title: str
    url: str
    job_type: str | None = None
    posted_at: str | None = None
    salary: str | None = None
    snippet: str = ""


class JobPosting(BaseModel):
    """A full job detail page."""

    job_id: str
    title: str
    url: str
    job_type: str | None = None
    salary: str | None = None
    hours_per_week: str | None = None
    date_updated: str | None = None
    skills: list[str] = Field(default_factory=list)
    description: str
