"""Typed data passed between the scraper, the tools, and the agent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Verdict = Literal["strong", "possible", "weak", "no"]


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


class MatchedRequirement(BaseModel):
    requirement_quote: str = Field(
        description="Exact quote from the job posting naming a requirement."
    )
    profile_evidence_quote: str = Field(
        description="Exact quote from the candidate profile that satisfies it."
    )


class FitAssessment(BaseModel):
    job_id: str
    verdict: Verdict
    score: int = Field(ge=0, le=100, description="0-100 fit score.")
    reasoning: str = Field(description="2-4 sentences explaining the verdict.")
    matched: list[MatchedRequirement] = Field(default_factory=list)
    gaps: list[str] = Field(
        default_factory=list,
        description="Requirements from the posting the candidate does not meet.",
    )
    red_flags: list[str] = Field(
        default_factory=list,
        description=(
            "Real concerns about the posting itself: unpaid trials, fees, vague scope, "
            "pay far below market, suspicious requests. Not application requirements."
        ),
    )
    application_requirements: list[str] = Field(
        default_factory=list,
        description=(
            "What the employer asks applicants to submit or answer (resume, portfolio, "
            "expected pay, specific questions). A checklist for the candidate."
        ),
    )
    required_phrases: list[str] = Field(
        default_factory=list,
        description=(
            "Exact words the employer requires in the application, e.g. a code word "
            "they ask applicants to put in the subject. Empty if none."
        ),
    )


class ApplicationDraft(BaseModel):
    job_id: str
    subject: str = Field(description="Application subject line, under 120 characters.")
    message: str = Field(description="Application message body, 80-300 words.")
    profile_facts_used: list[str] = Field(
        description="Exact quotes from the candidate profile that the message relies on."
    )
