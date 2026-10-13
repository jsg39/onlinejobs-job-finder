import { useEffect, useState } from "react";
import type { Job } from "./types";

export interface Filters {
  minMatch: number; // 0-4
  minPay: number; // approximate USD/month, 0 = any
  includeUnlistedPay: boolean;
  types: string[]; // empty = all
  hideRisky: boolean;
}

export const DEFAULT_FILTERS: Filters = {
  minMatch: 2.5,
  minPay: 0,
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
    if (!job.pay_usd_month) return f.includeUnlistedPay;
    if (job.pay_usd_month.max < f.minPay) return false;
  }
  return true;
}

export function isDefault(f: Filters): boolean {
  return JSON.stringify(f) === JSON.stringify(DEFAULT_FILTERS);
}
