import { useEffect, useState } from "react";
import { DEFAULT_FILTERS, type Filters, isDefault, PERIOD_SUFFIX, type PayPeriod } from "./filters";
import Tip, { TIPS } from "./Tip";

const OPEN_KEY = "ojagent:filtersOpen";
// onlinejobs.ph's "Any" job type means the employer is flexible on hours.
const TYPE_LABELS: Record<string, string> = { Any: "Flexible" };

interface Props {
  filters: Filters;
  onChange: (f: Filters) => void;
  jobTypes: string[];
  shown: number;
  total: number;
}

function activeCount(f: Filters): number {
  const d = DEFAULT_FILTERS;
  return [
    f.minMatch !== d.minMatch,
    f.minPay !== d.minPay,
    f.types.length > 0,
    f.hideRisky !== d.hideRisky,
    f.minPay > 0 && f.includeUnlistedPay !== d.includeUnlistedPay,
  ].filter(Boolean).length;
}

export default function FilterBar({ filters: f, onChange, jobTypes, shown, total }: Props) {
  const [open, setOpen] = useState(() => {
    try {
      return localStorage.getItem(OPEN_KEY) !== "0";
    } catch {
      return true;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(OPEN_KEY, open ? "1" : "0");
    } catch {
      // fine: panel just opens by default
    }
  }, [open]);

  const set = (patch: Partial<Filters>) => onChange({ ...f, ...patch });
  const toggleType = (t: string) =>
    set({ types: f.types.includes(t) ? f.types.filter((x) => x !== t) : [...f.types, t] });
  const active = activeCount(f);

  return (
    <section className={`filters${open ? "" : " closed"}`} aria-label="Filters">
      <header className="filters-head">
        <button className="filters-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
          <span className="caret" aria-hidden>
            ▸
          </span>
          Filters
          {active > 0 && <span className="count">{active}</span>}
        </button>
        <span className="muted">
          {shown} of {total} jobs
        </span>
        {!isDefault(f) && (
          <button className="link" onClick={() => onChange(DEFAULT_FILTERS)}>
            Reset
          </button>
        )}
      </header>

      {open && (
        <div className="filters-body">
          <label className="filter match">
            <span>
              <Tip tip={TIPS.match}>Min match</Tip>
              <strong>{f.minMatch.toFixed(1)}+</strong>
            </span>
            <input
              type="range"
              min={0}
              max={4}
              step={0.1}
              value={f.minMatch}
              onChange={(e) => set({ minMatch: Number(e.target.value) })}
            />
          </label>

          <label className="filter pay">
            <span>
              <Tip tip={TIPS.pay}>Min pay</Tip>
            </span>
            <span className="money">
              <span aria-hidden>$</span>
              <input
                type="number"
                inputMode="numeric"
                min={0}
                step={f.payPeriod === "hour" ? 1 : f.payPeriod === "year" ? 1000 : 100}
                placeholder="Any"
                value={f.minPay || ""}
                onChange={(e) => set({ minPay: Math.max(0, Number(e.target.value) || 0) })}
                aria-label="Minimum pay in US dollars"
              />
              <select
                className="period"
                value={f.payPeriod}
                onChange={(e) => set({ payPeriod: e.target.value as PayPeriod, minPay: 0 })}
                aria-label="Pay period"
              >
                {(Object.keys(PERIOD_SUFFIX) as PayPeriod[]).map((p) => (
                  <option key={p} value={p}>
                    {PERIOD_SUFFIX[p]}
                  </option>
                ))}
              </select>
            </span>
          </label>

          {jobTypes.length > 1 && (
            <div className="filter types">
              <span>Job type</span>
              <div className="chips" role="group" aria-label="Job type">
                {jobTypes.map((t) => (
                  <button
                    key={t}
                    className={f.types.includes(t) ? "chip on" : "chip"}
                    aria-pressed={f.types.includes(t)}
                    onClick={() => toggleType(t)}
                  >
                    {TYPE_LABELS[t] ?? t}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="checks">
            <label>
              <input
                type="checkbox"
                checked={f.includeUnlistedPay}
                disabled={f.minPay === 0}
                onChange={(e) => set({ includeUnlistedPay: e.target.checked })}
              />
              Include unlisted pay
            </label>
            <label>
              <input type="checkbox" checked={f.hideRisky} onChange={(e) => set({ hideRisky: e.target.checked })} />
              Hide likely scams
            </label>
          </div>
        </div>
      )}
    </section>
  );
}
