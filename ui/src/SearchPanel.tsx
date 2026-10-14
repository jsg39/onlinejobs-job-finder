import { useEffect, useState } from "react";
import { getResume } from "./api";
import type { ResumeInfo, RunStatus } from "./types";

const KEYWORD_KEY = "ojagent:keyword";
const CRAWL_DELAY_S = 5;
const MIN_POSTINGS = 5;
const MAX_POSTINGS = 90; // the API caps a scan at three 30-card result pages

function savedKeyword(): string {
  try {
    return localStorage.getItem(KEYWORD_KEY) || "python";
  } catch {
    return "python";
  }
}

interface Props {
  active: RunStatus | null;
  onStart: (keyword: string, postings: number) => void;
  startError: string | null;
}

export default function SearchPanel({ active, onStart, startError }: Props) {
  const [keyword, setKeyword] = useState(savedKeyword);
  const [postings, setPostings] = useState<number | "">(30);
  const [resume, setResume] = useState<ResumeInfo | null>(null);
  const running = active?.status === "running";

  useEffect(() => {
    getResume().then((r) => setResume(r.resume)).catch(() => {});
  }, []);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const k = keyword.trim();
    if (!k) return;
    const n = Math.min(MAX_POSTINGS, Math.max(MIN_POSTINGS, Number(postings) || 30));
    setPostings(n);
    try {
      localStorage.setItem(KEYWORD_KEY, k);
    } catch {
      // fine: keyword just isn't remembered
    }
    onStart(k, n);
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
        <label className="field scan">
          <span>Postings to scan</span>
          <span className="money">
            <input
              type="number"
              inputMode="numeric"
              min={MIN_POSTINGS}
              max={MAX_POSTINGS}
              step={5}
              value={postings}
              onChange={(e) => setPostings(e.target.value === "" ? "" : Number(e.target.value))}
              disabled={running}
              aria-label={`Number of newest postings to scan, ${MIN_POSTINGS} to ${MAX_POSTINGS}`}
            />
            <span aria-hidden>newest</span>
          </span>
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
