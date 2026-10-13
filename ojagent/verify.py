"""Deterministic checks that keep the agent honest.

Every claim the model makes must be traceable to text it was actually given:
requirement quotes to the job posting, evidence quotes to the candidate profile.
The tools run these checks and hand failures back to the model so it can fix them.
"""

from __future__ import annotations

import re
import unicodedata

from .models import ApplicationDraft, FitAssessment, JobPosting

SUBJECT_MAX_CHARS = 120
MESSAGE_MIN_WORDS = 60
MESSAGE_MAX_WORDS = 350

# Technologies a draft might name. If the message names one that is in neither the
# profile nor the assessment's acknowledged gaps, it is claiming a skill we can't back.
TECH_TERMS = [
    "python", "javascript", "typescript", "java", "c#", "c++", "golang", "rust", "php",
    "ruby", "swiftui", "kotlin", "react", "next.js", "vue", "angular", "svelte", "node.js",
    "express.js", "django", "flask", "fastapi", "laravel", "rails", "spring boot", "graphql",
    "postgresql", "mysql", "mongodb", "redis", "dynamodb", "sqlite", "sql server",
    "elasticsearch", "kafka", "rabbitmq", "aws", "azure", "gcp", "docker", "kubernetes",
    "terraform", "pytorch", "tensorflow", "scikit-learn", "pandas", "spark", "airflow",
    "langchain", "langgraph", "llamaindex", "autogen", "crewai", "openai", "anthropic",
    "qdrant", "pinecone", "weaviate", "chroma", "mcp", "wordpress", "shopify", "webflow",
    "figma", "power bi", "tableau", "salesforce", "hubspot", "zapier", "n8n", "make.com",
    "selenium", "playwright", "cypress", "jest", "pytest", "websocket", "tailwind",
]

_PUNCT = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_PUNCT).lower()
    text = re.sub(r"[*_`#>]", " ", text)  # markdown noise
    return " ".join(text.split())


def contains_quote(source: str, quote: str) -> bool:
    quote_n = normalize(quote).strip(" .,;:-'\"")
    return bool(quote_n) and quote_n in normalize(source)


def mentions_term(text: str, term: str) -> bool:
    return re.search(rf"(?<![\w.]){re.escape(term)}(?![\w])", normalize(text)) is not None


def check_assessment(a: FitAssessment, posting: JobPosting, profile: str) -> list[str]:
    errors: list[str] = []
    posting_text = "\n".join([posting.title, posting.description, *posting.skills])
    for m in a.matched:
        if not contains_quote(posting_text, m.requirement_quote):
            errors.append(f"requirement_quote not found in the posting: {m.requirement_quote!r}")
        if not contains_quote(profile, m.profile_evidence_quote):
            errors.append(
                f"profile_evidence_quote not found in the profile: {m.profile_evidence_quote!r}"
            )
    for phrase in a.required_phrases:
        if not contains_quote(posting_text, phrase):
            errors.append(f"required_phrase not found in the posting: {phrase!r}")
    if a.verdict in ("strong", "possible") and not a.matched:
        errors.append(f"verdict {a.verdict!r} needs at least one matched requirement")
    bands = {"strong": (70, 100), "possible": (45, 85), "weak": (15, 60), "no": (0, 30)}
    lo, hi = bands[a.verdict]
    if not lo <= a.score <= hi:
        errors.append(f"score {a.score} is inconsistent with verdict {a.verdict!r} ({lo}-{hi})")
    return errors


def check_draft(
    d: ApplicationDraft, a: FitAssessment, posting: JobPosting, profile: str
) -> list[str]:
    errors: list[str] = []
    if a.verdict not in ("strong", "possible"):
        errors.append(f"do not draft for a {a.verdict!r} fit")
    if not d.subject.strip():
        errors.append("subject is empty")
    if len(d.subject) > SUBJECT_MAX_CHARS:
        errors.append(f"subject is {len(d.subject)} chars; max {SUBJECT_MAX_CHARS}")
    words = len(d.message.split())
    if not MESSAGE_MIN_WORDS <= words <= MESSAGE_MAX_WORDS:
        errors.append(f"message is {words} words; keep it {MESSAGE_MIN_WORDS}-{MESSAGE_MAX_WORDS}")
    if not d.profile_facts_used:
        errors.append("profile_facts_used is empty; cite the profile facts the message relies on")
    for fact in d.profile_facts_used:
        if not contains_quote(profile, fact):
            errors.append(f"profile_facts_used entry not found in the profile: {fact!r}")
    full = f"{d.subject}\n{d.message}"
    for phrase in a.required_phrases:
        if not contains_quote(full, phrase):
            errors.append(f"employer asked applicants to include {phrase!r}; it is missing")
    acknowledged = normalize(" ".join(a.gaps))
    for term in TECH_TERMS:
        if (
            mentions_term(d.message, term)
            and not mentions_term(profile, term)
            and term not in acknowledged
        ):
            errors.append(
                f"message mentions {term!r}, which is not in the profile. Remove it, or if "
                "the message honestly acknowledges it as a gap, list it in the assessment gaps"
            )
    return errors
