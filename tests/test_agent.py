"""Agent loop and tool behaviour, driven by a scripted LLM (no network)."""

from ojagent.agent import Agent
from ojagent.store import Store
from tests.conftest import PROFILE, ScriptedLLM

GOOD_ASSESSMENT = {
    "job_id": "100",
    "verdict": "strong",
    "score": 80,
    "reasoning": "Python/FastAPI/PostgreSQL match.",
    "matched": [
        {
            "requirement_quote": "Experience with PostgreSQL",
            "profile_evidence_quote": "Built REST APIs with FastAPI and PostgreSQL",
        }
    ],
    "gaps": ["Kubernetes"],
    "required_phrases": ["PINEAPPLE"],
}
GOOD_DRAFT = {
    "job_id": "100",
    "subject": "PINEAPPLE | Python Backend Developer with FastAPI + PostgreSQL",
    "message": " ".join(["I built REST APIs with FastAPI and PostgreSQL."] * 12),
    "profile_facts_used": ["Built REST APIs with FastAPI and PostgreSQL"],
}


def make_agent(llm, source, store=None):
    return Agent(llm=llm, source=source, store=store or Store(), profile=PROFILE, max_steps=10)


def test_happy_path_saves_assessment_and_draft(source):
    llm = ScriptedLLM(
        [
            [("search_jobs", {"keyword": "python"})],
            [("get_job_details", {"job_id": "100"})],
            [("save_fit_assessment", GOOD_ASSESSMENT)],
            [("save_application_draft", GOOD_DRAFT)],
            [("finish", {"summary": "1 strong fit."})],
        ]
    )
    store = Store()
    result = make_agent(llm, source, store).run("go")
    assert result.finished and result.stop_reason == "finished"
    assert result.rejections == 0
    rows = store.run_results(result.run_id)
    assert len(rows) == 1 and rows[0]["draft"].subject.startswith("PINEAPPLE")
    assert result.input_tokens == 500


def test_validator_rejection_is_fed_back_and_model_can_fix_it(source):
    bad = {**GOOD_DRAFT, "subject": "Python Backend Developer"}  # missing code word
    llm = ScriptedLLM(
        [
            [("get_job_details", {"job_id": "100"})],
            [("save_fit_assessment", GOOD_ASSESSMENT)],
            [("save_application_draft", bad)],
            [("save_application_draft", GOOD_DRAFT)],
            [("finish", {"summary": "done"})],
        ]
    )
    store = Store()
    result = make_agent(llm, source, store).run("go")
    assert result.rejections == 1
    tool_msgs = [m for m in llm.seen[3] if m["role"] == "tool"]
    assert "PINEAPPLE" in tool_msgs[-1]["content"]  # the model saw why it failed
    assert store.get_draft("100").subject.startswith("PINEAPPLE")


def test_finish_is_refused_while_a_good_fit_has_no_draft(source):
    llm = ScriptedLLM(
        [
            [("get_job_details", {"job_id": "100"})],
            [("save_fit_assessment", GOOD_ASSESSMENT)],
            [("finish", {"summary": "done early"})],
            [("save_application_draft", GOOD_DRAFT)],
            [("finish", {"summary": "done"})],
        ]
    )
    store = Store()
    result = make_agent(llm, source, store).run("go")
    assert result.finished and result.rejections == 1
    assert "save_application_draft for 100" in [m for m in llm.seen[3] if m["role"] == "tool"][-1]["content"]
    assert store.get_draft("100") is not None


def test_cannot_assess_a_job_it_never_read(source):
    llm = ScriptedLLM([[("save_fit_assessment", GOOD_ASSESSMENT)], [("finish", {"summary": "x"})]])
    store = Store()
    result = make_agent(llm, source, store).run("go")
    assert result.rejections == 1 and store.get_assessment("100") is None


def test_tool_failures_and_bad_arguments_do_not_crash_the_loop(source):
    llm = ScriptedLLM(
        [
            [("get_job_details", {"job_id": "999"})],  # source raises
            [("save_fit_assessment", {"job_id": "100"})],  # missing fields
            [("no_such_tool", {})],
            [("finish", {"summary": "x"})],
        ]
    )
    result = make_agent(llm, source).run("go")
    assert result.finished and result.rejections == 3


def test_step_budget_stops_a_looping_model(source):
    llm = ScriptedLLM([[("search_jobs", {})]] * 50)
    result = make_agent(llm, source).run("go")
    assert not result.finished and result.stop_reason == "max_steps" and result.steps == 10


def test_text_only_replies_are_nudged_then_stopped(source):
    llm = ScriptedLLM(["thinking...", "still thinking", "hmm"])
    result = make_agent(llm, source).run("go")
    assert result.stop_reason == "no_tool_call"


def test_memory_marks_jobs_assessed_in_earlier_runs(source):
    store = Store()
    make_agent(
        ScriptedLLM(
            [
                [("get_job_details", {"job_id": "100"})],
                [("save_fit_assessment", GOOD_ASSESSMENT)],
                [("finish", {"summary": "x"})],
            ]
        ),
        source,
        store,
    ).run("go")
    llm = ScriptedLLM([[("search_jobs", {})], [("finish", {"summary": "x"})]])
    make_agent(llm, source, store).run("go")
    search_result = [m for m in llm.seen[1] if m["role"] == "tool"][0]["content"]
    assert '"job_id": "100"' in search_result and '"already_assessed": true' in search_result
    assert '"already_assessed": false' in search_result  # job 200 is new


def test_cached_posting_is_not_refetched(source):
    store = Store()
    turns = [[("get_job_details", {"job_id": "100"})], [("finish", {"summary": "x"})]]
    make_agent(ScriptedLLM(list(turns)), source, store).run("go")
    make_agent(ScriptedLLM(list(turns)), source, store).run("go")
    assert source.fetches == ["100"]
