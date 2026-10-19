import { useState } from "react";
import { PERIOD_SUFFIX, type PayPeriod, payIn } from "./filters";
import Tip, { TIPS } from "./Tip";
import type { Job, Status } from "./types";

interface Props {
  job: Job;
  payPeriod: PayPeriod;
  status?: Status;
  note?: string;
  onStatus: (status: Status | null, note?: string) => void;
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

function money(n: number, period: PayPeriod) {
  const digits = period === "hour" && n < 100 ? 2 : 0;
  return n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: digits });
}

/** "≈ $1,123–1,498/mo" in the period the user filters by; hidden when it would repeat the posted pay. */
function approxPay(job: Job, period: PayPeriod): string | null {
  const p = payIn(job, period);
  if (!p) return null;
  const text = (job.pay ?? "").toLowerCase();
  const usd = text.includes("$") && !/aud|cad|sgd|nzd/.test(text);
  const postedIn: PayPeriod | null = /hour|\bhr\b/.test(text) ? "hour" : /year|annual/.test(text) ? "year" : /month|\bmo\b/.test(text) ? "month" : null;
  if (usd && postedIn === period) return null;
  const range = p.min === p.max ? money(p.min, period) : `${money(p.min, period)}–${money(p.max, period)}`;
  return `≈ $${range}${PERIOD_SUFFIX[period]}`;
}

function Meter({ label, value, tip }: { label: string; value: number; tip: string }) {
  return (
    <Tip tip={tip}>
      <span className="meter">
        <span className="meter-label">{label}</span>
        <span className="meter-track">
          <span className="meter-fill" style={{ width: `${(value / 4) * 100}%` }} />
        </span>
        <span className="meter-value">{value.toFixed(1)}</span>
      </span>
    </Tip>
  );
}

// Shortlists can mix sites, so the button says where the posting lives.
const siteName = (url: string): string => (url.includes("jobstreet.com") ? "JobStreet" : "onlinejobs.ph");

export default function JobCard({ job, payPeriod, status, note, onStatus }: Props) {
  // The optional "why not?" box, shown on Not interested and when editing a saved reason.
  const [asking, setAsking] = useState(false);
  const [draft, setDraft] = useState("");
  const ask = () => {
    setDraft(note ?? "");
    setAsking(true);
  };
  const dismiss = (reason: string) => {
    setAsking(false);
    onStatus("dismissed", reason.trim());
  };

  const approx = approxPay(job, payPeriod);
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
            {approx && (
              <Tip tip={TIPS.pay}>
                <span className="pay-approx">{approx}</span>
              </Tip>
            )}
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
        <Tip tip={TIPS.match}>
          <div className="rank" aria-label={`Match ${job.rank.toFixed(1)} out of 4`}>
            <strong>{job.rank.toFixed(1)}</strong>
            <span>match</span>
          </div>
        </Tip>
      </header>

      <div className="meters">
        <Meter label="Fit" value={job.fit} tip={TIPS.fit} />
        <Meter label="Appeal" value={job.appeal} tip={TIPS.appeal} />
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

      {status === "dismissed" && note && !asking && (
        <p className="reason">
          <span className="muted">Your reason:</span> {note}
        </p>
      )}

      {asking ? (
        <form
          className="reason-form"
          onSubmit={(e) => {
            e.preventDefault();
            dismiss(draft);
          }}
        >
          <label className="field grow">
            Why not? Optional, and it teaches your profile.
            <input
              autoFocus
              maxLength={300}
              value={draft}
              placeholder="e.g. pay too low, on-site, too junior, not coding"
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Escape" && setAsking(false)}
            />
          </label>
          <div className="actions">
            <button className="btn primary" type="submit">
              {status ? "Save reason" : "Not interested"}
            </button>
            {!status && (
              <button className="btn" type="button" onClick={() => dismiss("")}>
                Skip reason
              </button>
            )}
            <button className="btn ghost" type="button" onClick={() => setAsking(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <footer className="actions">
          <a className="btn primary" href={job.url} target="_blank" rel="noreferrer">
            Open on {siteName(job.url)} ↗
          </a>
          {status ? (
            <>
              <button className="btn" onClick={() => onStatus(null)}>
                Undo {status === "applied" ? "applied" : "not interested"}
              </button>
              {status === "dismissed" && (
                <button className="btn ghost" onClick={ask}>
                  {note ? "Edit reason" : "Add reason"}
                </button>
              )}
            </>
          ) : (
            <>
              <button className="btn" onClick={() => onStatus("applied")}>
                Mark applied
              </button>
              <button className="btn ghost" onClick={ask}>
                Not interested
              </button>
            </>
          )}
        </footer>
      )}
    </article>
  );
}
