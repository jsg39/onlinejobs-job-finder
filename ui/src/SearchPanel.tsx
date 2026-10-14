import { useEffect, useState } from "react";
import { getResume } from "./api";
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
  const running = active?.status === "running";

  useEffect(() => {
    getResume().then((r) => setResume(r.resume)).catch(() => {});
  }, []);

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

      <p className="resume">
        <span className="muted">
          Matching against {resume ? <strong>{resume.filename}</strong> : "your profile"}.
        </span>
        <a className="link" href="#/profile">
          Edit profile →
        </a>
      </p>
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
