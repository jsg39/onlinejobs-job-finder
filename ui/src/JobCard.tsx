import type { Job, Status } from "./types";

interface Props {
  job: Job;
  status?: Status;
  onStatus: (status: Status | null) => void;
}

function formatPosted(posted: string | null): string | null {
  if (!posted) return null;
  const d = new Date(posted.replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return posted;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function Meter({ label, value }: { label: string; value: number }) {
  return (
    <div className="meter" title={`${label} ${value.toFixed(1)} / 4`}>
      <span className="meter-label">{label}</span>
      <span className="meter-track">
        <span className="meter-fill" style={{ width: `${(value / 4) * 100}%` }} />
      </span>
      <span className="meter-value">{value.toFixed(1)}</span>
    </div>
  );
}

export default function JobCard({ job, status, onStatus }: Props) {
  const posted = formatPosted(job.posted);
  const meta = [job.type, job.hours && `${job.hours} hrs/wk`, posted && `Posted ${posted}`].filter(Boolean);

  return (
    <article className={`card${status ? ` is-${status}` : ""}`}>
      <header className="card-head">
        <div className="card-title">
          <a href={job.url} target="_blank" rel="noreferrer">
            {job.title}
          </a>
          <div className="meta">
            <span className="pay">{job.pay || "Pay not listed"}</span>
            {meta.map((m) => (
              <span key={m as string}>{m}</span>
            ))}
          </div>
        </div>
        <div className="rank" aria-label={`Match ${job.rank.toFixed(1)} out of 4`}>
          <strong>{job.rank.toFixed(1)}</strong>
          <span>match</span>
        </div>
      </header>

      <div className="meters">
        <Meter label="Fit" value={job.fit} />
        <Meter label="Appeal" value={job.appeal} />
      </div>

      <p className="summary">
        {job.summary}
        {!job.summary_by_llm && <span className="source"> (from the posting)</span>}
      </p>

      {job.matching_skills.length > 0 && (
        <ul className="skills" aria-label="Skills you have">
          {job.matching_skills.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      )}

      {job.scam >= 0.3 && (
        <p className="warning">Possible red flags ({Math.round(job.scam * 100)}% scam signal). Read carefully.</p>
      )}

      <footer className="actions">
        <a className="btn primary" href={job.url} target="_blank" rel="noreferrer">
          Open posting ↗
        </a>
        {status ? (
          <button className="btn" onClick={() => onStatus(null)}>
            Undo {status === "applied" ? "applied" : "not interested"}
          </button>
        ) : (
          <>
            <button className="btn" onClick={() => onStatus("applied")}>
              Mark applied
            </button>
            <button className="btn ghost" onClick={() => onStatus("dismissed")}>
              Not interested
            </button>
          </>
        )}
      </footer>
    </article>
  );
}
