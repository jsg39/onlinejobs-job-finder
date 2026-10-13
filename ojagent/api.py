"""FastAPI backend for the UI: upload a resume, start a triage run, follow its progress.

    uvicorn ojagent.api:app --port 8000

A run scrapes onlinejobs.ph with the 5 s crawl delay, so it takes minutes. It runs on a
background thread; the UI polls GET /api/runs/{id}. One run at a time keeps the
crawl polite.
"""

from __future__ import annotations

import io
import json
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .config import ROOT, load_settings
from .llm import LLM, OpenAICompatibleLLM
from .prefilter import JevPrefilter
from .scraper import JobSource, OnlineJobsClient
from .triage import render, to_json, triage

MAX_RESUME_BYTES = 5 * 1024 * 1024
STAGE_LABELS = {
    "search": "Searching onlinejobs.ph",
    "screen": "Jev is screening postings",
    "fetch": "Reading postings (5 s each, per robots.txt)",
    "score": "Jev is scoring postings",
    "summarize": "Writing summaries",
    "done": "Done",
}


def extract_resume_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        from pypdf import PdfReader

        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
    elif ext == ".docx":
        import docx

        doc = docx.Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs]
        parts += [cell.text for table in doc.tables for row in table.rows for cell in row.cells]
        text = "\n".join(parts)
    elif ext in (".txt", ".md"):
        text = data.decode("utf-8", "replace")
    else:
        raise ValueError("Upload a PDF, DOCX, TXT or MD resume.")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 200:
        raise ValueError("Couldn't read enough text from that file. Is it a scanned image?")
    return text


def preferences_section(profile: str) -> str:
    match = re.search(r"^## Preferences\n.*?(?=^## |\Z)", profile, re.M | re.S)
    return match.group(0).strip() if match else ""


def build_profile(base_profile: str, resume: str | None) -> str:
    """The uploaded resume plus the preferences (pay floor, remote) a resume doesn't state."""
    if not resume:
        return base_profile
    return f"# Candidate profile\n\n{preferences_section(base_profile)}\n\n## Resume\n{resume}\n"


class RunRequest(BaseModel):
    keyword: str = Field(default="python", min_length=1, max_length=60)
    pages: int = Field(default=1, ge=1, le=3)


@dataclass
class Run:
    keyword: str
    pages: int
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    status: str = "running"  # running | done | error
    stage: str = "search"
    done: int = 0
    total: int = 0
    started: float = field(default_factory=time.time)
    finished: float | None = None
    error: str | None = None
    result: dict | None = None

    def view(self) -> dict:
        return {
            "id": self.id,
            "keyword": self.keyword,
            "pages": self.pages,
            "status": self.status,
            "stage": self.stage,
            "stage_label": STAGE_LABELS.get(self.stage, self.stage),
            "done": self.done,
            "total": self.total,
            "elapsed": round((self.finished or time.time()) - self.started, 1),
            "error": self.error,
            "result": self.result,
        }


def _default_jev() -> JevPrefilter | None:
    key = load_settings().typesafe_api_key
    return JevPrefilter(key) if key else None


def _default_llm() -> LLM | None:
    try:
        s = load_settings()
    except SystemExit:  # no LLM key: Jev-only, summaries come from the posting text
        return None
    return OpenAICompatibleLLM(s.model, s.api_key, s.base_url)


def create_app(
    make_source: Callable[[], JobSource] = OnlineJobsClient,
    make_jev: Callable[[], JevPrefilter | None] = _default_jev,
    make_llm: Callable[[], LLM | None] = _default_llm,
    profile_path: Path = ROOT / "profile.md",
    data_dir: Path = ROOT / "data",
    out_dir: Path = ROOT / "out",
) -> FastAPI:
    app = FastAPI(title="ojagent", description="Job triage for onlinejobs.ph")
    resume_txt, resume_meta = data_dir / "resume.txt", data_dir / "resume.json"
    runs: dict[str, Run] = {}
    lock = threading.Lock()

    def current_resume() -> str | None:
        return resume_txt.read_text(encoding="utf-8") if resume_txt.exists() else None

    def execute(run: Run) -> None:
        def progress(stage: str, done: int, total: int) -> None:
            run.stage, run.done, run.total = stage, done, total

        try:
            jev, llm = make_jev(), make_llm()
            if jev is None and llm is None:
                raise RuntimeError("Set TYPESAFE_API_KEY (and optionally an LLM key) in .env")
            profile = build_profile(profile_path.read_text(encoding="utf-8"), current_resume())
            result = triage(make_source(), jev, profile, llm=llm, pages=run.pages,
                            keyword=run.keyword, progress=progress)
            data = to_json(result, profile)
            data["keyword"] = run.keyword
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = out_dir / f"triage-{datetime.now():%Y%m%d-%H%M%S}-{'jev' if jev else 'no-jev'}"
            stem.with_suffix(".md").write_text(render(result, profile), encoding="utf-8")
            text = json.dumps(data, ensure_ascii=False, indent=1)
            stem.with_suffix(".json").write_text(text, encoding="utf-8")
            (out_dir / "latest.json").write_text(text, encoding="utf-8")
            run.result, run.status = data, "done"
        except Exception as e:
            run.error, run.status = f"{type(e).__name__}: {e}", "error"
        finally:
            run.finished = time.time()

    @app.get("/api/resume")
    def get_resume() -> dict:
        if not resume_meta.exists():
            return {"resume": None}
        return {"resume": json.loads(resume_meta.read_text(encoding="utf-8"))}

    @app.post("/api/resume")
    async def upload_resume(file: UploadFile = File(...)) -> dict:
        data = await file.read(MAX_RESUME_BYTES + 1)
        if len(data) > MAX_RESUME_BYTES:
            raise HTTPException(413, "Resume must be under 5 MB.")
        try:
            text = extract_resume_text(file.filename or "", data)
        except ValueError as e:
            raise HTTPException(422, str(e))
        data_dir.mkdir(parents=True, exist_ok=True)
        resume_txt.write_text(text, encoding="utf-8")
        meta = {
            "filename": Path(file.filename or "resume").name,
            "uploaded_at": datetime.now().isoformat(timespec="seconds"),
            "chars": len(text),
        }
        resume_meta.write_text(json.dumps(meta), encoding="utf-8")
        return {"resume": meta}

    @app.delete("/api/resume")
    def delete_resume() -> dict:
        resume_txt.unlink(missing_ok=True)
        resume_meta.unlink(missing_ok=True)
        return {"resume": None}

    @app.post("/api/runs", status_code=202)
    def start_run(req: RunRequest) -> dict:
        with lock:
            if any(r.status == "running" for r in runs.values()):
                raise HTTPException(409, "A search is already running.")
            run = Run(keyword=req.keyword.strip(), pages=req.pages)
            runs[run.id] = run
        threading.Thread(target=execute, args=(run,), daemon=True).start()
        return run.view()

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        run = runs.get(run_id)
        if run is None:
            raise HTTPException(404, "Unknown run.")
        return run.view()

    @app.get("/api/latest")
    def latest() -> dict:
        path = out_dir / "latest.json"
        if not path.exists():
            raise HTTPException(404, "No results yet. Start a search.")
        return json.loads(path.read_text(encoding="utf-8"))

    return app


app = create_app()
