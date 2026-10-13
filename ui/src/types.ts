// Shape of out/latest.json, written by ojagent/triage.py:to_json.

export interface Job {
  id: string;
  title: string;
  url: string;
  pay: string | null;
  pay_usd_month: { min: number; max: number } | null; // approximate, for filtering
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
  pages: number;
  status: "running" | "done" | "error";
  stage: string;
  stage_label: string;
  done: number;
  total: number;
  elapsed: number;
  error: string | null;
  result: Run | null;
}
