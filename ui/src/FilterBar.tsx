import { DEFAULT_FILTERS, type Filters, isDefault } from "./filters";
import Tip, { TIPS } from "./Tip";

const PAY_OPTIONS = [0, 500, 800, 1000, 1500, 2000, 3000];

interface Props {
  filters: Filters;
  onChange: (f: Filters) => void;
  jobTypes: string[];
  shown: number;
  total: number;
}

export default function FilterBar({ filters: f, onChange, jobTypes, shown, total }: Props) {
  const set = (patch: Partial<Filters>) => onChange({ ...f, ...patch });
  const toggleType = (t: string) =>
    set({ types: f.types.includes(t) ? f.types.filter((x) => x !== t) : [...f.types, t] });

  return (
    <section className="filters" aria-label="Filters">
      <div className="filter-row">
        <label className="filter">
          <span>
            <Tip tip={TIPS.match}>Min match</Tip> <strong>{f.minMatch.toFixed(1)}+</strong>
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

        <label className="filter">
          <span>
            <Tip tip={TIPS.pay}>Min pay</Tip>
          </span>
          <select value={f.minPay} onChange={(e) => set({ minPay: Number(e.target.value) })}>
            {PAY_OPTIONS.map((p) => (
              <option key={p} value={p}>
                {p === 0 ? "Any" : `≈ $${p.toLocaleString()}/mo`}
              </option>
            ))}
          </select>
        </label>

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

      {jobTypes.length > 1 && (
        <div className="chips" role="group" aria-label="Job type">
          {jobTypes.map((t) => (
            <button
              key={t}
              className={f.types.includes(t) ? "chip on" : "chip"}
              aria-pressed={f.types.includes(t)}
              onClick={() => toggleType(t)}
            >
              {t}
            </button>
          ))}
        </div>
      )}

      <p className="filter-summary muted">
        Showing {shown} of {total} scored jobs
        {!isDefault(f) && (
          <>
            {" · "}
            <button className="link" onClick={() => onChange(DEFAULT_FILTERS)}>
              Reset filters
            </button>
          </>
        )}
      </p>
    </section>
  );
}
