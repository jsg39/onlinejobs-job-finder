import { useEffect, useState } from "react";
import type { Job } from "./types";

export type PayPeriod = "hour" | "month" | "year";
export const PERIOD_SUFFIX: Record<PayPeriod, string> = { hour: "/hr", month: "/mo", year: "/yr" };
const FULL_TIME_HOURS_PER_MONTH = 40 * (52 / 12);

/** A job's approximate USD pay range in the chosen period, or null if unknown. */
export function payIn(job: Job, period: PayPeriod): { min: number; max: number } | null {
  const m = job.pay_usd_month;
  if (!m) return null;
  if (period === "month") return m;
  if (period === "year") return { min: m.min * 12, max: m.max * 12 };
  return job.pay_usd_hour ?? { min: m.min / FULL_TIME_HOURS_PER_MONTH, max: m.max / FULL_TIME_HOURS_PER_MONTH };
}

export interface Filters {
  minMatch: number; // 0-4
  minPay: number; // approximate USD in payPeriod units, 0 = any
  payPeriod: PayPeriod;
  includeUnlistedPay: boolean;
  types: string[]; // empty = all
  hideRisky: boolean;
}

export const DEFAULT_FILTERS: Filters = {
  minMatch: 2.5,
  minPay: 0,
  payPeriod: "month",
  includeUnlistedPay: true,
  types: [],
  hideRisky: true,
};

const KEY = "ojagent:filters";

export function useFilters() {
  const [filters, setFilters] = useState<Filters>(() => {
    try {
      return { ...DEFAULT_FILTERS, ...JSON.parse(localStorage.getItem(KEY) ?? "{}") };
    } catch {
      return DEFAULT_FILTERS;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(filters));
    } catch {
      // storage blocked: filters reset on reload
    }
  }, [filters]);
  return [filters, setFilters] as const;
}

export function passes(job: Job, f: Filters): boolean {
  if (job.rank < f.minMatch) return false;
  if (f.hideRisky && job.scam >= 0.5) return false;
  if (f.types.length && !f.types.includes(job.type ?? "")) return false;
  if (f.minPay > 0) {
    // Ranges pass if their top end reaches the floor: "$800-1,200" can still pay $1,000.
    const pay = payIn(job, f.payPeriod);
    if (!pay) return f.includeUnlistedPay;
    if (pay.max < f.minPay) return false;
  }
  return true;
}

export function isDefault(f: Filters): boolean {
  // The pay period is a display unit, not a filter, so it doesn't count.
  return JSON.stringify({ ...f, payPeriod: "month" }) === JSON.stringify(DEFAULT_FILTERS);
}
