// Shape of out/latest.json, written by ojagent/triage.py:to_json.

export interface Job {
  id: string;
  title: string;
  url: string;
  pay: string | null;
  type: string | null;
  hours: string | null;
  posted: string | null;
  rank: number; // 0-4, mean of fit and appeal
  fit: number; // 0-4: would they hire me?
  appeal: number; // 0-4: would I want it?
  scam: number; // 0-1
  summary: string;
  summary_by_llm: boolean;
  matching_skills: string[];
  skills: string[];
  shortlisted: boolean;
}

export interface HiddenJob {
  id: string;
  title: string;
  url: string;
  fit_probability: number;
}

export interface Run {
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
