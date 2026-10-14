import { useEffect, useRef, useState } from "react";
import { clearMarks, deleteResume, getProfile, putProfile, uploadResume } from "./api";
import type { Preferences, Profile, ProfileView } from "./types";

const PERIODS = [
  { value: "month", label: "per month" },
  { value: "hour", label: "per hour" },
  { value: "year", label: "per year" },
] as const;

export default function ProfilePage() {
  const [view, setView] = useState<ProfileView | null>(null);
  const [draft, setDraft] = useState<Profile | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  function load(v: ProfileView) {
    setView(v);
    setDraft(v.profile);
  }

  useEffect(() => {
    getProfile()
      .then(load)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  async function run(action: () => Promise<ProfileView>, done: string) {
    setBusy(true);
    setError(null);
    try {
      load(await action());
      setStatus(done);
      setTimeout(() => setStatus(null), 2500);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  if (!view || !draft) {
    return <p className={error ? "error" : "muted"}>{error ?? "Loading profile…"}</p>;
  }

  const dirty = JSON.stringify(draft) !== JSON.stringify(view.profile);
  const prefs = draft.preferences;
  const setPrefs = (patch: Partial<Preferences>) => setDraft({ ...draft, preferences: { ...prefs, ...patch } });
  const { learned } = view;
  const marked = learned.applied.length + learned.dismissed.length;

  return (
    <div className="profile">
      <section className="panel">
        <header className="section-head">
          <div>
            <h2>Resume</h2>
            <p className="muted">
              {draft.resume_meta
                ? `From ${draft.resume_meta.filename}. Edit anything that's missing or wrong.`
                : "Upload your resume, or paste and edit it here."}
            </p>
          </div>
          <div className="row">
            <input
              ref={fileInput}
              type="file"
              accept=".pdf,.docx,.txt,.md"
              hidden
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) run(() => uploadResume(file), "Resume uploaded");
              }}
            />
            {draft.resume_meta && (
              <button className="btn ghost" disabled={busy} onClick={() => run(deleteResume, "Resume removed")}>
                Remove upload
              </button>
            )}
            <button className="btn" disabled={busy} onClick={() => fileInput.current?.click()}>
              {draft.resume_meta ? "Replace" : "Upload PDF or DOCX"}
            </button>
          </div>
        </header>
        <textarea
          className="resume-text"
          value={draft.resume_text}
          onChange={(e) => setDraft({ ...draft, resume_text: e.target.value })}
          rows={14}
          spellCheck={false}
          aria-label="Resume text"
        />
      </section>

      <section className="panel">
        <header className="section-head">
          <div>
            <h2>What you want</h2>
            <p className="muted">Used for the appeal score: would you want the job?</p>
          </div>
        </header>
        <div className="form-grid">
          <label className="field wide">
            <span>Roles you're looking for</span>
            <input value={prefs.roles} onChange={(e) => setPrefs({ roles: e.target.value })} maxLength={500} />
          </label>
          <label className="field">
            <span>Minimum pay</span>
            <span className="money">
              <select
                className="period"
                value={prefs.min_pay_currency}
                onChange={(e) => setPrefs({ min_pay_currency: e.target.value as Preferences["min_pay_currency"] })}
                aria-label="Currency"
              >
                <option value="PHP">₱</option>
                <option value="USD">$</option>
              </select>
              <input
                type="number"
                min={0}
                value={prefs.min_pay_amount || ""}
                placeholder="Any"
                onChange={(e) => setPrefs({ min_pay_amount: Math.max(0, Number(e.target.value) || 0) })}
                aria-label="Minimum pay amount"
              />
              <select
                className="period"
                value={prefs.min_pay_period}
                onChange={(e) => setPrefs({ min_pay_period: e.target.value as Preferences["min_pay_period"] })}
                aria-label="Pay period"
              >
                {PERIODS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </span>
          </label>
          <label className="field toggle">
            <input
              type="checkbox"
              checked={prefs.remote_only}
              onChange={(e) => setPrefs({ remote_only: e.target.checked })}
            />
            <span>Fully remote only</span>
          </label>
          <label className="field wide">
            <span>Not interested in</span>
            <input
              value={prefs.not_interested}
              onChange={(e) => setPrefs({ not_interested: e.target.value })}
              placeholder="e.g. data entry, cold calling"
              maxLength={500}
            />
          </label>
          <label className="field wide">
            <span>Anything else</span>
            <textarea
              value={prefs.notes}
              onChange={(e) => setPrefs({ notes: e.target.value })}
              rows={2}
              placeholder="e.g. prefer startups, open to a night shift for US clients"
              maxLength={1000}
            />
          </label>
        </div>
      </section>

      <section className="panel">
        <header className="section-head">
          <div>
            <h2>Learned from your choices</h2>
            <p className="muted">
              Jobs you mark <em>applied</em> or <em>not interested</em> teach the ranking what you like.
            </p>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={draft.use_learned}
              onChange={(e) => setDraft({ ...draft, use_learned: e.target.checked })}
            />
            <span>Use in ranking</span>
          </label>
        </header>
        {marked === 0 ? (
          <p className="muted">Nothing yet. Mark a few jobs on the Jobs page and this fills in.</p>
        ) : (
          <div className="learned">
            <div className="stats">
              <span>
                <strong>{learned.applied.length}</strong> applied
              </span>
              <span>
                <strong>{learned.dismissed.length}</strong> not interested
              </span>
              {learned.median_pay_usd_month && (
                <span>
                  typical pay <strong>≈ ${learned.median_pay_usd_month.toLocaleString()}/mo</strong>
                </span>
              )}
            </div>
            {learned.top_skills.length > 0 && (
              <ul className="skills" aria-label="Skills common in jobs you applied to">
                {learned.top_skills.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            )}
            <div className="title-lists">
              {learned.applied.length > 0 && (
                <div>
                  <h3>Applied</h3>
                  <ul>{learned.applied.slice(0, 10).map((t) => <li key={t}>{t}</li>)}</ul>
                </div>
              )}
              {learned.dismissed.length > 0 && (
                <div>
                  <h3>Not interested</h3>
                  <ul>{learned.dismissed.slice(0, 10).map((t) => <li key={t}>{t}</li>)}</ul>
                </div>
              )}
            </div>
            <button
              className="link"
              disabled={busy}
              onClick={() => {
                if (confirm("Forget every applied and not-interested mark?")) {
                  run(async () => {
                    await clearMarks();
                    return getProfile();
                  }, "History cleared");
                }
              }}
            >
              Clear history
            </button>
          </div>
        )}
      </section>

      <details className="panel preview">
        <summary>What Jev sees</summary>
        <p className="muted">The exact profile text each job is scored against (saved version).</p>
        <pre>{view.composed}</pre>
      </details>

      {(dirty || status || error) && (
      <div className="savebar" role="region" aria-label="Save changes">
        {error && <span className="error">{error}</span>}
        {status && !dirty && <span className="saved">{status} ✓</span>}
        {dirty && <span className="muted">Unsaved changes</span>}
        <button className="btn ghost" disabled={!dirty || busy} onClick={() => setDraft(view.profile)}>
          Discard
        </button>
        <button className="btn primary" disabled={!dirty || busy} onClick={() => run(() => putProfile(draft), "Saved")}>
          Save profile
        </button>
      </div>
      )}
    </div>
  );
}
