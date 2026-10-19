import { useCallback, useEffect, useMemo, useState } from "react";
import { getActiveRun, getLatest, getRun, startRun } from "./api";
import FilterBar from "./FilterBar";
import { passes, useFilters } from "./filters";
import JobCard from "./JobCard";
import ProfilePage from "./ProfilePage";
import SearchPanel from "./SearchPanel";
import { SOURCES } from "./types";
import type { Job, MarkedJob, Run, RunStatus, Source } from "./types";
import { useStatuses } from "./useStatuses";

type Tab = "foryou" | "applied" | "dismissed";

const TABS: { id: Tab; label: string }[] = [
  { id: "foryou", label: "For you" },
  { id: "applied", label: "Applied" },
  { id: "dismissed", label: "Not interested" },
];
const POLL_MS = 1500;

type Page = "jobs" | "profile";
const pageFromHash = (): Page => (location.hash === "#/profile" ? "profile" : "jobs");

function usePage(): Page {
  const [page, setPage] = useState<Page>(pageFromHash);
  useEffect(() => {
    const onHash = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  return page;
}

// Fill in what an old, slim mark snapshot lacks so it renders as a card.
const fromMark = (j: MarkedJob): Job => ({
  url: `https://www.onlinejobs.ph/jobseekers/job/${j.id}`,
  pay: null,
  pay_usd_month: null,
  type: null,
  hours: null,
  posted: null,
  rank: 0,
  fit: 0,
  appeal: 0,
  scam: 0,
  brief: null,
  snippet: "",
  matching_skills: [],
  skills: [],
  shortlisted: false,
  ...j,
});

// Older saved results have no source; they were all onlinejobs.ph.
const sourceLabel = (source?: string): string =>
  (source && SOURCES[source as Source]?.label) || SOURCES.onlinejobs.label;

export default function App() {
  const [run, setRun] = useState<Run | null>(null);
  const [active, setActive] = useState<RunStatus | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [backendDown, setBackendDown] = useState(false);
  const [tab, setTab] = useState<Tab>("foryou");
  const { statuses, markedJobs, notes, setStatus, error: markError } = useStatuses();
  const page = usePage();
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

  const onStart = useCallback(async (keyword: string, postings: number, source: Source) => {
    setStartError(null);
    try {
      setActive(await startRun(keyword, postings, source));
      setBackendDown(false);
    } catch (e) {
      setStartError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  // "For you" is every unmarked job in the latest results that passes the user's filters,
  // best match first. Applied and not interested come from the saved marks, so they span every search.
  const { groups, unmarked } = useMemo(() => {
    const g: Record<Tab, Job[]> = { foryou: [], applied: [], dismissed: [] };
    let unmarked = 0;
    const inRun = new Map((run?.jobs ?? []).map((j) => [j.id, j]));
    for (const job of run?.jobs ?? []) {
      if (statuses[job.id]) continue;
      unmarked++;
      if (passes(job, filters)) g.foryou.push(job);
    }
    for (const [id, s] of Object.entries(statuses)) {
      const job = inRun.get(id) ?? (markedJobs[id] && fromMark(markedJobs[id]));
      if (job) g[s].push(job);
    }
    return { groups: g, unmarked };
  }, [run, statuses, markedJobs, filters]);

  const jobTypes = useMemo(
    () => [...new Set((run?.jobs ?? []).map((j) => j.type).filter((t): t is string => !!t))].sort(),
    [run],
  );

  const jobs = groups[tab];

  const nav = (
    <nav className="pages" aria-label="Pages">
      <a href="#/" aria-current={page === "jobs" ? "page" : undefined}>
        Jobs
      </a>
      <a href="#/profile" aria-current={page === "profile" ? "page" : undefined}>
        Profile
      </a>
    </nav>
  );

  if (page === "profile") {
    return (
      <main className="page">
        {nav}
        <header className="top">
          <h1>Your profile</h1>
          <p className="muted">What every job is scored against. Changes apply to your next search.</p>
        </header>
        <ProfilePage />
      </main>
    );
  }

  return (
    <main className="page">
      {nav}
      <header className="top">
        <h1>Jobs worth your time</h1>
        <p className="muted">
          {run
            ? `${groups.foryou.length} match${groups.foryou.length === 1 ? "" : "es"} from ${run.stats.scanned} "${
                run.keyword ?? "python"
              }" postings on ${sourceLabel(run.source)} · ${new Date(run.generated_at).toLocaleString(undefined, {
                month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
              })}`
            : "Search a job site and get a shortlist ranked against your resume."}
        </p>
      </header>

      {backendDown && (
        <p className="error">
          Can't reach the backend. Start it with <code>uvicorn ojagent.api:app --port 8000</code>.
        </p>
      )}

      <SearchPanel active={active} onStart={onStart} startError={startError} />
      {markError && <p className="error">Couldn't save that mark: {markError}</p>}

      {(run || Object.keys(statuses).length > 0) && (
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
                <JobCard
                  key={job.id}
                  job={job}
                  payPeriod={filters.payPeriod}
                  status={statuses[job.id]}
                  note={notes[job.id]}
                  onStatus={(s, n) => setStatus(job, s, n)}
                />
              ))
            )}
          </section>

          {run && (
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
          )}
        </>
      )}
    </main>
  );
}
