from ojagent.models import ApplicationDraft, FitAssessment, MatchedRequirement
from ojagent.verify import check_assessment, check_draft, contains_quote
from tests.conftest import PROFILE, PYTHON_JOB

GOOD_MATCH = MatchedRequirement(
    requirement_quote="2+ years of Python and FastAPI",
    profile_evidence_quote="Built REST APIs with FastAPI and PostgreSQL",
)


def assessment(**kw) -> FitAssessment:
    base = dict(
        job_id="100",
        verdict="strong",
        score=82,
        reasoning="Good fit.",
        matched=[GOOD_MATCH],
        gaps=["Kubernetes"],
        required_phrases=["PINEAPPLE"],
    )
    return FitAssessment(**{**base, **kw})


def draft(**kw) -> ApplicationDraft:
    message = " ".join(["I have built REST APIs with FastAPI and PostgreSQL."] * 12)
    base = dict(
        job_id="100",
        subject="PINEAPPLE - Python Backend Developer",
        message=message,
        profile_facts_used=["Built REST APIs with FastAPI and PostgreSQL"],
    )
    return ApplicationDraft(**{**base, **kw})


def test_contains_quote_tolerates_case_whitespace_and_smart_quotes():
    assert contains_quote("We don’t  need\nhelp", "we don't need help")
    assert not contains_quote("abc", "")


def test_valid_assessment_passes():
    assert check_assessment(assessment(), PYTHON_JOB, PROFILE) == []


def test_fabricated_profile_evidence_is_rejected():
    fake = MatchedRequirement(
        requirement_quote="Experience with PostgreSQL",
        profile_evidence_quote="5 years as a PostgreSQL DBA",
    )
    errors = check_assessment(assessment(matched=[fake]), PYTHON_JOB, PROFILE)
    assert any("not found in the profile" in e for e in errors)


def test_requirement_not_in_posting_is_rejected():
    fake = GOOD_MATCH.model_copy(update={"requirement_quote": "Django expert"})
    errors = check_assessment(assessment(matched=[fake]), PYTHON_JOB, PROFILE)
    assert any("not found in the posting" in e for e in errors)


def test_score_must_agree_with_verdict():
    errors = check_assessment(assessment(verdict="no", score=90, matched=[]), PYTHON_JOB, PROFILE)
    assert any("inconsistent" in e for e in errors)


def test_positive_verdict_needs_evidence():
    errors = check_assessment(assessment(matched=[]), PYTHON_JOB, PROFILE)
    assert any("needs at least one matched" in e for e in errors)


def test_valid_draft_passes():
    assert check_draft(draft(), assessment(), PYTHON_JOB, PROFILE) == []


def test_draft_must_include_employer_code_word():
    errors = check_draft(draft(subject="Python Backend Developer"), assessment(), PYTHON_JOB, PROFILE)
    assert any("PINEAPPLE" in e for e in errors)


def test_draft_cannot_claim_unlisted_skill():
    msg = draft().message + " I also run production Kubernetes and Django."
    errors = check_draft(draft(message=msg), assessment(gaps=[]), PYTHON_JOB, PROFILE)
    assert any("'kubernetes'" in e for e in errors)
    assert any("'django'" in e for e in errors)


def test_draft_may_mention_acknowledged_gap():
    msg = draft().message + " I have not used Kubernetes in production yet."
    assert check_draft(draft(message=msg), assessment(), PYTHON_JOB, PROFILE) == []


def test_no_draft_for_weak_fit():
    errors = check_draft(draft(), assessment(verdict="weak", score=40), PYTHON_JOB, PROFILE)
    assert any("do not draft" in e for e in errors)


def test_java_is_not_matched_inside_javascript():
    msg = draft().message + " Comfortable reading JavaScript."
    errors = check_draft(draft(message=msg), assessment(), PYTHON_JOB, PROFILE + "\n- JavaScript")
    assert not any("'java'" in e for e in errors)
