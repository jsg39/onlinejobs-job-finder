import { useEffect, useState } from "react";
import { getResume } from "./api";
import { SOURCES } from "./types";
import type { ResumeInfo, RunStatus, Source } from "./types";

const KEYWORD_KEY = "ojagent:keyword";
const SOURCE_KEY = "ojagent:source";
const CRAWL_DELAY_S = 5;
const MIN_POSTINGS = 5;
// Each site's cap is in SOURCES (types.ts): three 30-card result pages. For both sites
// the count is the total, split about evenly between them.

function savedKeyword(): string {
  try {
    return localStorage.getItem(KEYWORD_KEY) || "python";
  } catch {
    return "python";
  }
}

function savedSource(): Source {
  try {
    const s = localStorage.getItem(SOURCE_KEY);
    if (s && Object.keys(SOURCES).includes(s)) return s as Source;
  } catch {
    // fine: fall through to the default
  }
  return "onlinejobs";
}

interface Props {
  active: RunStatus | null;
  onStart: (keyword: string, postings: number, source: Source) => void;
  startError: string | null;
}

export default function SearchPanel({ active, onStart, startError }: Props) {
  const [keyword, setKeyword] = useState(savedKeyword);
  const [source, setSource] = useState<Source>(savedSource);
  const [postings, setPostings] = useState<number | "">(30);
  const [resume, setResume] = useState<ResumeInfo | null>(null);
  const running = active?.status === "running";
  const maxPostings = SOURCES[source].max;

  useEffect(() => {
    getResume().then((r) => setResume(r.resume)).catch(() => {});
  }, []);

  function pickSource(next: Source) {
    setSource(next);
    if (Number(postings) > SOURCES[next].max) setPostings(SOURCES[next].max);
    try {
      localStorage.setItem(SOURCE_KEY, next);
    } catch {
      // fine: site just isn't remembered
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const k = keyword.trim();
    if (!k) return;
    const n = Math.min(maxPostings, Math.max(MIN_POSTINGS, Number(postings) || 30));
    setPostings(n);
    try {
      localStorage.setItem(KEYWORD_KEY, k);
    } catch {
      // fine: keyword just isn't remembered
    }
    onStart(k, n, source);
  }

  return (
    <section className="panel">
      <form className="search" onSubmit={submit}>
        <label className="field site">
          <span>Job site</span>
          <select value={source} onChange={(e) => pickSource(e.target.value as Source)} disabled={running}>
            {(Object.keys(SOURCES) as Source[]).map((key) => (
              <option key={key} value={key}>
                {SOURCES[key].label}
              </option>
            ))}
          </select>
        </label>
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
              max={maxPostings}
              step={5}
              value={postings}
              onChange={(e) => setPostings(e.target.value === "" ? "" : Number(e.target.value))}
              disabled={running}
              aria-label={`Number of newest postings to scan, ${MIN_POSTINGS} to ${maxPostings}`}
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
