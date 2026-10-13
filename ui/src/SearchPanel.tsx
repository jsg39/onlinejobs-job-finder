import { useEffect, useRef, useState } from "react";
import { deleteResume, getResume, uploadResume } from "./api";
import type { ResumeInfo, RunStatus } from "./types";

const KEYWORD_KEY = "ojagent:keyword";
const CRAWL_DELAY_S = 5;

function savedKeyword(): string {
  try {
    return localStorage.getItem(KEYWORD_KEY) || "python";
  } catch {
    return "python";
  }
}

interface Props {
  active: RunStatus | null;
  onStart: (keyword: string, pages: number) => void;
  startError: string | null;
}

export default function SearchPanel({ active, onStart, startError }: Props) {
  const [keyword, setKeyword] = useState(savedKeyword);
  const [pages, setPages] = useState(1);
  const [resume, setResume] = useState<ResumeInfo | null>(null);
  const [resumeError, setResumeError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const running = active?.status === "running";

  useEffect(() => {
    getResume().then((r) => setResume(r.resume)).catch(() => {});
  }, []);

  async function onFile(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    setResumeError(null);
    try {
      setResume((await uploadResume(file)).resume);
    } catch (e) {
      setResumeError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function onRemove() {
    await deleteResume().catch(() => {});
    setResume(null);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const k = keyword.trim();
    if (!k) return;
    try {
      localStorage.setItem(KEYWORD_KEY, k);
    } catch {
      // fine: keyword just isn't remembered
    }
    onStart(k, pages);
  }

  return (
    <section className="panel">
      <form className="search" onSubmit={submit}>
        <label className="field grow">
          <span>Search keyword</span>
          <input
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="python"
            maxLength={60}
            disabled={running}
          />
        </label>
        <label className="field">
          <span>Scan</span>
          <select value={pages} onChange={(e) => setPages(Number(e.target.value))} disabled={running}>
            <option value={1}>30 newest</option>
            <option value={2}>60 newest</option>
            <option value={3}>90 newest</option>
          </select>
        </label>
        <button className="btn primary find" type="submit" disabled={running || !keyword.trim()}>
          {running ? "Searching…" : "Find my top jobs"}
        </button>
      </form>

      <div className="resume">
        <input
          ref={fileInput}
          type="file"
          accept=".pdf,.docx,.txt,.md"
          hidden
          onChange={(e) => onFile(e.target.files?.[0])}
        />
        {resume ? (
          <>
            <span className="resume-name">
              Matching against <strong>{resume.filename}</strong>
            </span>
            <button className="link" onClick={() => fileInput.current?.click()} disabled={uploading || running}>
              Replace
            </button>
            <button className="link" onClick={onRemove} disabled={uploading || running}>
              Remove
            </button>
          </>
        ) : (
          <>
            <span className="muted">Matching against your saved profile.</span>
            <button className="link" onClick={() => fileInput.current?.click()} disabled={uploading || running}>
              {uploading ? "Uploading…" : "Upload resume (PDF, DOCX)"}
            </button>
          </>
        )}
      </div>
      {resumeError && <p className="error">{resumeError}</p>}
      {startError && <p className="error">{startError}</p>}

      {running && active && <Progress run={active} />}
      {active?.status === "error" && <p className="error">Search failed: {active.error}</p>}
    </section>
  );
}

function Progress({ run }: { run: RunStatus }) {
  const pct = run.total ? Math.min(100, (run.done / run.total) * 100) : 0;
  const remaining = run.stage === "fetch" ? (run.total - run.done) * CRAWL_DELAY_S : null;
  return (
    <div className="progress" role="status" aria-live="polite">
      <div className="progress-text">
        <span>
          {run.stage_label}
          {run.total > 0 && run.stage !== "screen" && ` · ${run.done}/${run.total}`}
        </span>
        <span className="muted">
          {Math.round(run.elapsed)} s{remaining ? ` · about ${Math.ceil(remaining / 60)} min left` : ""}
        </span>
      </div>
      <div className="progress-track">
        <div className={`progress-fill${run.total ? "" : " indeterminate"}`} style={{ width: `${pct || 30}%` }} />
      </div>
    </div>
  );
}
