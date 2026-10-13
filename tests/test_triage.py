"""Triage pipeline with a fake source and a fake Jev (no network)."""

from ojagent.triage import matching_skills, render, summarize, triage
from tests.conftest import DESIGN_JOB, PROFILE, PYTHON_JOB


class FakeJev:
    def __init__(self, card_probs, fit, scam=None, appeal=None, fail_cards=False):
        self.card_probs, self.fit, self.scam = card_probs, fit, scam or {}
        self.appeal = appeal or {}
        self.fail_cards = fail_cards

    def fit_probabilities(self, profile, jobs):
        if self.fail_cards:
            raise RuntimeError("jev down")
        return {j.job_id: self.card_probs[j.job_id] for j in jobs}

    def ask(self, state, questions):
        title = state["job"]["title"]
        return {
            "fit": {"type": "score", "score": self.fit[title]},
            "appeal": {"type": "score", "score": self.appeal.get(title, self.fit[title])},
            "scam": {"type": "noul", "noul": self.scam.get(title, 0.02)},
        }


FITS = {PYTHON_JOB.title: 3.4, DESIGN_JOB.title: 0.2}


def test_hidden_cards_are_never_fetched(source):
    result = triage(source, FakeJev({"100": 0.9, "200": 0.05}, FITS), PROFILE)
    assert source.fetches == ["100"]
    assert result.hidden == {"200": 0.05}
    assert [s.posting.job_id for s in result.scored] == ["100"]


def test_fetch_all_baseline_reads_everything(source):
    result = triage(source, FakeJev({}, FITS), PROFILE, fetch_all=True)
    assert source.fetches == ["100", "200"] and not result.hidden
    assert [s.posting.job_id for s in result.scored] == ["100", "200"]
    assert "screen_cards" not in result.timings


def test_card_screen_failure_fetches_everything(source):
    result = triage(source, FakeJev({}, FITS, fail_cards=True), PROFILE)
    assert source.fetches == ["100", "200"]


def test_report_shortlists_good_fits_with_link_and_pay(source):
    result = triage(source, FakeJev({"100": 0.9, "200": 0.05}, FITS), PROFILE)
    md = render(result, PROFILE)
    shortlist = md.split("## Shortlist")[1].split("## Hidden")[0]
    assert f"[{PYTHON_JOB.title}]({PYTHON_JOB.url})" in shortlist
    assert "Rank 3.4/4" in shortlist and "$1,000/month" in shortlist
    assert "Matching skills: Python, FastAPI" in shortlist
    assert "Graphic Designer" in md.split("## Hidden by Jev")[1]


def test_scam_signal_keeps_job_off_the_shortlist(source):
    jev = FakeJev({"100": 0.9, "200": 0.9}, FITS, scam={PYTHON_JOB.title: 0.8})
    md = render(triage(source, jev, PROFILE), PROFILE)
    assert "Nothing cleared the bar" in md
    assert "80%" in md.split("## Also read")[1]


def test_summarize_cuts_at_a_sentence():
    text = "First sentence here. " * 30
    out = summarize(text, limit=100)
    assert out.endswith(".") and len(out) <= 100


def test_matching_skills_needs_whole_words():
    p = PYTHON_JOB.model_copy(update={"skills": ["Python", "Go", "React"]})
    assert matching_skills(p, "Python and React, no golang") == ["Python", "React"]


def test_rank_blends_fit_and_appeal(source):
    # The design job is an easy hire but unwanted; the Python job is wanted and a decent fit.
    jev = FakeJev({"100": 0.9, "200": 0.9}, {PYTHON_JOB.title: 2.6, DESIGN_JOB.title: 3.8},
                  appeal={PYTHON_JOB.title: 3.6, DESIGN_JOB.title: 0.2})
    result = triage(source, jev, PROFILE)
    assert [s.posting.job_id for s in result.scored] == ["100", "200"]
    assert result.scored[0].rank == 3.1
    shortlist = render(result, PROFILE).split("## Shortlist")[1].split("## Also read")[0]
    assert PYTHON_JOB.title in shortlist and DESIGN_JOB.title not in shortlist


def test_searches_python_by_default(source):
    calls = []
    source.search = lambda keyword=None, page=0: calls.append(keyword) or []
    triage(source, FakeJev({}, {}), PROFILE)
    assert calls == ["python"]
