import { useCallback, useEffect, useMemo, useState } from "react";
import JobCard from "./JobCard";
import type { Job, Run } from "./types";
import { useStatuses } from "./useStatuses";

type Tab = "foryou" | "applied" | "dismissed" | "below";

const TABS: { id: Tab; label: string }[] = [
  { id: "foryou", label: "For you" },
  { id: "applied", label: "Applied" },
  { id: "dismissed", label: "Not interested" },
  { id: "below", label: "Below the bar" },
];

export default function App() {
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("foryou");
  const { statuses, setStatus } = useStatuses();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/latest.json", { cache: "no-store" });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
      setRun(body);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const groups = useMemo(() => {
    const g: Record<Tab, Job[]> = { foryou: [], applied: [], dismissed: [], below: [] };
    for (const job of run?.jobs ?? []) {
      const s = statuses[job.id];
      if (s) g[s].push(job);
      else g[job.shortlisted ? "foryou" : "below"].push(job);
    }
    return g;
  }, [run, statuses]);

  if (error && !run) {
    return (
      <main className="page">
        <div className="empty">
          <h1>No shortlist yet</h1>
          <p>{error}</p>
          <code>python -m ojagent.triage</code>
          <button className="btn" onClick={load}>
            Try again
          </button>
        </div>
      </main>
    );
  }
  if (!run) return <main className="page"><p className="muted">Loading…</p></main>;

  const when = new Date(run.generated_at).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
  const jobs = groups[tab];
  const { stats } = run;

  return (
    <main className="page">
      <header className="top">
        <div>
          <h1>Jobs worth your time</h1>
          <p className="muted">
            {groups.foryou.length} new match{groups.foryou.length === 1 ? "" : "es"} from{" "}
            {stats.scanned} Python postings · {when}
          </p>
        </div>
        <button className="btn" onClick={load} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </header>

      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            className={tab === t.id ? "tab active" : "tab"}
            onClick={() => setTab(t.id)}
          >
            {t.label} <span className="count">{groups[t.id].length}</span>
          </button>
        ))}
      </nav>

      {tab === "below" && jobs.length > 0 && (
        <p className="muted note">Read and scored, but under the {run.min_rank}/4 match bar or flagged as risky.</p>
      )}

      <section className="list">
        {jobs.length === 0 ? (
          <p className="muted empty-tab">
            {tab === "foryou" ? "You're all caught up. Run triage again later for new postings." : "Nothing here."}
          </p>
        ) : (
          jobs.map((job) => (
            <JobCard key={job.id} job={job} status={statuses[job.id]} onStatus={(s) => setStatus(job.id, s)} />
          ))
        )}
      </section>

      <footer className="foot">
        <p className="muted">
          {run.used_jev
            ? `Jev skipped ${stats.hidden} clear mismatches · fetched ${stats.fetched}`
            : `No Jev: fetched all ${stats.fetched}`}
          {" · "}
          {stats.seconds.total ?? "?"} s
          {stats.llm_calls > 0 &&
            ` · LLM ${stats.llm_calls} calls, ${(stats.llm_input_tokens + stats.llm_output_tokens).toLocaleString()} tokens`}
        </p>
        {run.hidden.length > 0 && (
          <details>
            <summary>Skipped by Jev ({run.hidden.length})</summary>
            <ul className="hidden-list">
              {run.hidden.map((h) => (
                <li key={h.id}>
                  <a href={h.url} target="_blank" rel="noreferrer">
                    {h.title}
                  </a>
                  <span className="muted"> {Math.round(h.fit_probability * 100)}%</span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </footer>
    </main>
  );
}
