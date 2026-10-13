import type { Job, Status } from "./types";

interface Props {
  job: Job;
  status?: Status;
  onStatus: (status: Status | null) => void;
}

function ago(d: Date): string {
  const mins = Math.round((Date.now() - d.getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

/** "Oct 13, 4:49 AM · 5h ago" in the viewer's timezone. */
function formatPosted(posted: string | null): { text: string; title?: string } | null {
  if (!posted) return null;
  const d = new Date(posted);
  if (Number.isNaN(d.getTime())) return { text: posted };
  const when = d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  return { text: `${when} · ${ago(d)}`, title: d.toString() };
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
  const meta = [job.type, job.hours && `${job.hours} hrs/wk`].filter(Boolean);

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
            {posted && (
              <time dateTime={job.posted ?? undefined} title={posted.title}>
                Posted {posted.text}
              </time>
            )}
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

      {job.brief ? (
        <div className="brief">
          <p className="role">{job.brief.role}</p>
          {(job.brief.fits.length > 0 || job.brief.gaps.length > 0) && (
            <ul className="bullets">
              {job.brief.fits.map((f) => (
                <li key={f} className="fit">
                  <span aria-label="Fits">✓</span>
                  {f}
                </li>
              ))}
              {job.brief.gaps.map((g) => (
                <li key={g} className="gap">
                  <span aria-label="Gap">△</span>
                  {g}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <p className="summary">
          {job.snippet}
          <span className="source"> (from the posting)</span>
        </p>
      )}

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
