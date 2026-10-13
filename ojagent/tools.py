"""The agent's tools. Each one validates its input and returns a JSON-able dict.

Tool errors are returned to the model as data ({"ok": false, "errors": [...]}) rather
than raised, so the model can read what went wrong and retry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError

from .models import ApplicationDraft, FitAssessment
from .scraper import JobSource
from .store import Store
from .verify import check_assessment, check_draft

MAX_DESCRIPTION_CHARS = 6000
MAX_SNIPPET_CHARS = 280


class SearchJobsArgs(BaseModel):
    keyword: str | None = Field(
        default=None, description="Search keyword, e.g. 'python'. Omit for all latest jobs."
    )
    page: int = Field(default=0, ge=0, le=5, description="Result page, 30 jobs each, newest first.")


class GetJobDetailsArgs(BaseModel):
    job_id: str


class FinishArgs(BaseModel):
    summary: str = Field(description="Short note on what you did and anything the user should know.")


def _inline_refs(schema: dict) -> dict:
    """Pydantic emits $defs/$ref; some providers' tool schemas don't accept them."""
    defs = schema.pop("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            # Drop pydantic's "title" metadata, but not a property that happens to be named title.
            return {k: walk(v) for k, v in node.items() if not (k == "title" and isinstance(v, str))}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


@dataclass
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    fn: Callable[[Any], dict]

    def spec(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": _inline_refs(self.args_model.model_json_schema()),
            },
        }


@dataclass
class Toolbox:
    source: JobSource
    store: Store
    profile: str
    run_id: str
    viewed: set[str] = field(default_factory=set)
    finished: bool = False
    final_summary: str = ""
    rejections: int = 0

    def __post_init__(self) -> None:
        self.tools = {
            t.name: t
            for t in [
                Tool(
                    "search_jobs",
                    "List the latest onlinejobs.ph postings (newest first). Each result says "
                    "whether it was already assessed in a previous run.",
                    SearchJobsArgs,
                    self.search_jobs,
                ),
                Tool(
                    "get_job_details",
                    "Fetch the full posting: description, pay, hours, required skills. You must "
                    "read a posting before assessing it.",
                    GetJobDetailsArgs,
                    self.get_job_details,
                ),
                Tool(
                    "save_fit_assessment",
                    "Record how well the candidate fits a posting you have read. Quotes are "
                    "checked word-for-word against the posting and the profile; if any check "
                    "fails, nothing is saved and you get the errors back to fix.",
                    FitAssessment,
                    self.save_fit_assessment,
                ),
                Tool(
                    "save_application_draft",
                    "Save an application subject and message for a job you assessed as "
                    "'strong' or 'possible'. Checked against the profile and the employer's "
                    "application instructions; fix and retry if rejected.",
                    ApplicationDraft,
                    self.save_application_draft,
                ),
                Tool(
                    "finish",
                    "Call once when you are done. The user's report is built from saved "
                    "assessments and drafts, not from this summary.",
                    FinishArgs,
                    self.finish,
                ),
            ]
        }

    def specs(self) -> list[dict]:
        return [t.spec() for t in self.tools.values()]

    def dispatch(self, name: str, raw_args: str) -> dict:
        result = self._call(name, raw_args)
        if not result.get("ok"):
            self.rejections += 1
        return result

    def _call(self, name: str, raw_args: str) -> dict:
        tool = self.tools.get(name)
        if tool is None:
            return {"ok": False, "errors": [f"unknown tool {name!r}"]}
        try:
            args = tool.args_model.model_validate(json.loads(raw_args or "{}"))
        except (json.JSONDecodeError, ValidationError) as e:
            return {"ok": False, "errors": [f"invalid arguments: {e}"]}
        try:
            return tool.fn(args)
        except Exception as e:  # network/parse failures are reported, not fatal
            return {"ok": False, "errors": [f"{type(e).__name__}: {e}"]}

    # --- tool implementations -------------------------------------------------

    def search_jobs(self, args: SearchJobsArgs) -> dict:
        jobs = self.source.search(args.keyword, args.page)
        done = self.store.assessed_ids()
        return {
            "ok": True,
            "count": len(jobs),
            "jobs": [
                {
                    **j.model_dump(exclude={"url"}),
                    "snippet": j.snippet[:MAX_SNIPPET_CHARS],
                    "already_assessed": j.job_id in done,
                }
                for j in jobs
            ],
        }

    def get_job_details(self, args: GetJobDetailsArgs) -> dict:
        posting = self.store.get_posting(args.job_id)
        if posting is None:
            posting = self.source.get_job(args.job_id)
            self.store.save_posting(posting)
        self.viewed.add(posting.job_id)
        data = posting.model_dump()
        if len(posting.description) > MAX_DESCRIPTION_CHARS:
            data["description"] = posting.description[:MAX_DESCRIPTION_CHARS] + " [truncated]"
        return {"ok": True, "posting": data}

    def save_fit_assessment(self, a: FitAssessment) -> dict:
        if a.job_id not in self.viewed:
            return {"ok": False, "errors": ["call get_job_details for this job_id first"]}
        posting = self.store.get_posting(a.job_id)
        assert posting is not None
        errors = check_assessment(a, posting, self.profile)
        if errors:
            return {"ok": False, "errors": errors}
        self.store.save_assessment(a, self.run_id)
        return {"ok": True, "saved": a.job_id, "verdict": a.verdict}

    def save_application_draft(self, d: ApplicationDraft) -> dict:
        assessment = self.store.get_assessment(d.job_id)
        if assessment is None or d.job_id not in self.viewed:
            return {"ok": False, "errors": ["save a fit assessment for this job in this run first"]}
        posting = self.store.get_posting(d.job_id)
        assert posting is not None
        errors = check_draft(d, assessment, posting, self.profile)
        if errors:
            return {"ok": False, "errors": errors}
        self.store.save_draft(d, self.run_id)
        return {"ok": True, "saved": d.job_id}

    def finish(self, args: FinishArgs) -> dict:
        missing = [
            job_id
            for job_id in sorted(self.viewed)
            if (a := self.store.get_assessment(job_id))
            and a.verdict in ("strong", "possible")
            and self.store.get_draft(job_id) is None
        ]
        if missing:
            return {
                "ok": False,
                "errors": [f"not done: call save_application_draft for {', '.join(missing)} first"],
            }
        self.finished = True
        self.final_summary = args.summary
        return {"ok": True}
