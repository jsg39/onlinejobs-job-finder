import { useCallback, useEffect, useMemo, useState } from "react";
import { getActiveRun, getLatest, getRun, startRun } from "./api";
import FilterBar from "./FilterBar";
import { passes, useFilters } from "./filters";
import JobCard from "./JobCard";
import SearchPanel from "./SearchPanel";
import type { Job, Run, RunStatus } from "./types";
import { useStatuses } from "./useStatuses";

type Tab = "foryou" | "applied" | "dismissed";

const TABS: { id: Tab; label: string }[] = [
  { id: "foryou", label: "For you" },
  { id: "applied", label: "Applied" },
  { id: "dismissed", label: "Not interested" },
];
const POLL_MS = 1500;

export default function App() {
  const [run, setRun] = useState<Run | null>(null);
  const [active, setActive] = useState<RunStatus | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [backendDown, setBackendDown] = useState(false);
  const [tab, setTab] = useState<Tab>("foryou");
  const { statuses, setStatus } = useStatuses();
  const [filters, setFilters] = useFilters();

  useEffect(() => {
    getLatest().then(setRun).catch(() => {});
    getActiveRun()
      .then((r) => r.run && setActive(r.run))
      .catch(() => setBackendDown(true));
  }, []);

  // Poll while a search runs; show its results when it finishes.
  useEffect(() => {
    if (active?.status !== "running") return;
    const timer = setInterval(async () => {
      try {
        const next = await getRun(active.id);
        setActive(next);
        if (next.status === "done" && next.result) {
          setRun(next.result);
          setTab("foryou");
        }
      } catch {
        // transient; try again next tick
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [active?.id, active?.status]);

  const onStart = useCallback(async (keyword: string, pages: number) => {
    setStartError(null);
    try {
      setActive(await startRun(keyword, pages));
      setBackendDown(false);
    } catch (e) {
      setStartError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  // "For you" is every unmarked job that passes the user's filters, best match first.
  const { groups, unmarked } = useMemo(() => {
    const g: Record<Tab, Job[]> = { foryou: [], applied: [], dismissed: [] };
    let unmarked = 0;
    for (const job of run?.jobs ?? []) {
      const s = statuses[job.id];
      if (s) g[s].push(job);
      else {
        unmarked++;
        if (passes(job, filters)) g.foryou.push(job);
      }
    }
    return { groups: g, unmarked };
  }, [run, statuses, filters]);

  const jobTypes = useMemo(
    () => [...new Set((run?.jobs ?? []).map((j) => j.type).filter((t): t is string => !!t))].sort(),
    [run],
  );

  const jobs = groups[tab];

  return (
    <main className="page">
      <header className="top">
        <h1>Jobs worth your time</h1>
        <p className="muted">
          {run
            ? `${groups.foryou.length} match${groups.foryou.length === 1 ? "" : "es"} from ${run.stats.scanned} "${
                run.keyword ?? "python"
              }" postings · ${new Date(run.generated_at).toLocaleString(undefined, {
                month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
              })}`
            : "Search onlinejobs.ph and get a shortlist ranked against your resume."}
        </p>
      </header>

      {backendDown && (
        <p className="error">
          Can't reach the backend. Start it with <code>uvicorn ojagent.api:app --port 8000</code>.
        </p>
      )}

      <SearchPanel active={active} onStart={onStart} startError={startError} />

      {run && (
        <>
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

          {tab === "foryou" && (
            <FilterBar
              filters={filters}
              onChange={setFilters}
              jobTypes={jobTypes}
              shown={groups.foryou.length}
              total={unmarked}
            />
          )}

          <section className="list">
            {jobs.length === 0 ? (
              <p className="muted empty-tab">
                {tab === "foryou"
                  ? unmarked
                    ? "No jobs match these filters. Try a lower match or pay."
                    : "You're all caught up. Search again later for new postings."
                  : "Nothing here."}
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
                ? `Jev skipped ${run.stats.hidden} clear mismatches · read ${run.stats.fetched}`
                : `No Jev: read all ${run.stats.fetched}`}
              {` · ${run.stats.seconds.total ?? "?"} s`}
              {run.stats.llm_calls > 0 &&
                ` · LLM ${run.stats.llm_calls} calls, ${(
                  run.stats.llm_input_tokens + run.stats.llm_output_tokens
                ).toLocaleString()} tokens`}
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
        </>
      )}
    </main>
  );
}
