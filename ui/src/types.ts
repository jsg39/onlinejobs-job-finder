// Shape of out/latest.json, written by ojagent/triage.py:to_json.

export type Source = "onlinejobs" | "jobstreet" | "all";

export const SOURCES: Record<Source, { label: string; max: number }> = {
  onlinejobs: { label: "onlinejobs.ph", max: 90 },
  jobstreet: { label: "JobStreet", max: 90 },
  all: { label: "onlinejobs.ph + JobStreet", max: 90 }, // max is the total across both sites
};

export interface Job {
  id: string;
  title: string;
  url: string;
  pay: string | null;
  pay_usd_month: { min: number; max: number } | null; // approximate, for filtering
  pay_usd_hour?: { min: number; max: number } | null; // at the posting's hours; absent in older runs
  type: string | null;
  hours: string | null;
  posted: string | null; // ISO with offset, e.g. 2026-10-13T04:49:34+08:00
  rank: number; // 0-4, mean of fit and appeal
  fit: number; // 0-4: would they hire me?
  appeal: number; // 0-4: would I want it?
  scam: number; // 0-1
  brief: Brief | null; // LLM-written; null when no LLM was available
  snippet: string; // the posting's opening lines, used when there is no brief
  matching_skills: string[];
  skills: string[];
  shortlisted: boolean;
}

export interface Brief {
  role: string;
  fits: string[];
  gaps: string[];
}

export interface HiddenJob {
  id: string;
  title: string;
  url: string;
  fit_probability: number;
}

export interface Run {
  keyword?: string;
  source?: string; // absent in results saved before JobStreet support
  generated_at: string;
  used_jev: boolean;
  min_rank: number;
  stats: {
    scanned: number;
    hidden: number;
    fetched: number;
    shortlisted: number;
    seconds: Record<string, number>;
    llm_calls: number;
    llm_input_tokens: number;
    llm_output_tokens: number;
  };
  jobs: Job[];
  hidden: HiddenJob[];
}

export type Status = "applied" | "dismissed";

export interface ResumeInfo {
  filename: string;
  uploaded_at: string;
  chars: number;
}

export interface RunStatus {
  id: string;
  keyword: string;
  postings: number;
  source: string;
  status: "running" | "done" | "error";
  stage: string;
  stage_label: string;
  done: number;
  total: number;
  elapsed: number;
  error: string | null;
  result: Run | null;
}

export interface Preferences {
  roles: string;
  remote_only: boolean;
  min_pay_amount: number;
  min_pay_currency: "USD" | "PHP";
  min_pay_period: "hour" | "month" | "year";
  not_interested: string;
  notes: string;
}

export interface Profile {
  preferences: Preferences;
  resume_text: string;
  resume_meta: ResumeInfo | null;
  use_learned: boolean;
}

export interface Learned {
  applied: string[];
  dismissed: string[];
  top_skills: string[];
  types: string[];
  median_pay_usd_month: number | null;
}

export interface ProfileView {
  profile: Profile;
  learned: Learned;
  composed: string; // the exact text Jev and the LLM rank against
}
