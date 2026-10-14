"""Seeding, composing and learning for the app's candidate profile."""

from ojagent.profile_store import JobSnapshot, Mark, Preferences, Profile, compose, learned_summary, seed_from_markdown

MD = """# Me

## Preferences
- Looking for: fully remote full-time roles in backend or data engineering. No hybrid.
- Minimum pay: PHP 50,000/month (about USD 860/month, or about USD 5/hour full-time).
- Not interested in: data entry, cold calling.

## Experience
- Built FastAPI services.
"""


def mark(status, title, skills=(), at="2026-10-14T08:00:00", pay=None):
    return Mark(status=status, at=at, job=JobSnapshot(id=title, title=title, skills=list(skills), pay_usd_month=pay))


def test_seed_reads_preferences_and_keeps_the_rest_as_resume():
    p = seed_from_markdown(MD)
    assert p.preferences.roles == "backend or data engineering" and p.preferences.remote_only
    assert (p.preferences.min_pay_amount, p.preferences.min_pay_currency, p.preferences.min_pay_period) == (50000, "PHP", "month")
    assert p.preferences.not_interested == "data entry, cold calling"
    assert p.resume_text.startswith("## Experience") and "Preferences" not in p.resume_text


def test_seed_prefers_an_uploaded_resume():
    assert seed_from_markdown(MD, "My uploaded resume").resume_text == "My uploaded resume"


def test_compose_states_pay_in_usd_too():
    text = compose(Profile(preferences=Preferences(min_pay_amount=20, min_pay_period="hour")), {})
    assert "- Minimum pay: USD 20/hour (about USD 3,467/month)." in text


def test_learning_lists_recent_choices_and_shared_skills():
    marks = {
        "a": mark("applied", "LLM Engineer", ["Python", "LangChain", "Software"], at="2026-10-14T09:00:00", pay={"min": 1000, "max": 2000}),
        "b": mark("applied", "Backend Dev", ["Python", "FastAPI"], at="2026-10-14T08:00:00", pay={"min": 900, "max": 1500}),
        "c": mark("applied", "AI Engineer", ["Python", "LangChain"], at="2026-10-14T07:00:00"),
        "d": mark("dismissed", "Data Entry VA"),
    }
    learned = learned_summary(marks)
    assert learned["applied"] == ["LLM Engineer", "Backend Dev", "AI Engineer"]  # newest first
    assert learned["top_skills"] == ["Python", "LangChain"]  # seen at least twice; generic tags dropped
    assert learned["median_pay_usd_month"] == 2000
    text = compose(Profile(), marks)
    assert "## Learned from the candidate's choices" in text and "Marked not interested: Data Entry VA." in text


def test_learning_can_be_switched_off():
    marks = {"a": mark("applied", "LLM Engineer")}
    assert "Learned" not in compose(Profile(use_learned=False), marks)
