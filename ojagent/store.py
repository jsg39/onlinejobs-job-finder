"""SQLite memory: fetched postings, assessments, and drafts persist across runs."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import ApplicationDraft, FitAssessment, JobPosting

_SCHEMA = """
CREATE TABLE IF NOT EXISTS postings (
    job_id TEXT PRIMARY KEY, data TEXT NOT NULL, fetched_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assessments (
    job_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS drafts (
    job_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.executescript(_SCHEMA)

    def save_posting(self, p: JobPosting) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO postings VALUES (?, ?, ?)",
            (p.job_id, p.model_dump_json(), _now()),
        )
        self.db.commit()

    def get_posting(self, job_id: str) -> JobPosting | None:
        row = self.db.execute("SELECT data FROM postings WHERE job_id = ?", (job_id,)).fetchone()
        return JobPosting.model_validate_json(row[0]) if row else None

    def save_assessment(self, a: FitAssessment, run_id: str) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO assessments VALUES (?, ?, ?, ?)",
            (a.job_id, run_id, a.model_dump_json(), _now()),
        )
        self.db.commit()

    def get_assessment(self, job_id: str) -> FitAssessment | None:
        row = self.db.execute(
            "SELECT data FROM assessments WHERE job_id = ?", (job_id,)
        ).fetchone()
        return FitAssessment.model_validate_json(row[0]) if row else None

    def assessed_ids(self) -> set[str]:
        return {r[0] for r in self.db.execute("SELECT job_id FROM assessments")}

    def save_draft(self, d: ApplicationDraft, run_id: str) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO drafts VALUES (?, ?, ?, ?)",
            (d.job_id, run_id, d.model_dump_json(), _now()),
        )
        self.db.commit()

    def get_draft(self, job_id: str) -> ApplicationDraft | None:
        row = self.db.execute("SELECT data FROM drafts WHERE job_id = ?", (job_id,)).fetchone()
        return ApplicationDraft.model_validate_json(row[0]) if row else None

    def run_results(self, run_id: str) -> list[dict]:
        """Everything a run saved, joined. Reports are built from this, not from model prose."""
        rows = self.db.execute(
            """SELECT a.job_id, p.data, a.data, d.data FROM assessments a
               JOIN postings p ON p.job_id = a.job_id
               LEFT JOIN drafts d ON d.job_id = a.job_id AND d.run_id = a.run_id
               WHERE a.run_id = ?""",
            (run_id,),
        ).fetchall()
        return [
            {
                "posting": JobPosting.model_validate_json(p),
                "assessment": FitAssessment.model_validate_json(a),
                "draft": ApplicationDraft.model_validate_json(d) if d else None,
            }
            for _, p, a, d in rows
        ]
