import type { Job, MarkedJob, Profile, ProfileView, ResumeInfo, Run, RunStatus, Source, Status } from "./types";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { cache: "no-store", ...init });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`;
    throw new Error(detail);
  }
  return body as T;
}

export const getLatest = () => call<Run>("/api/latest");

export const getResume = () => call<{ resume: ResumeInfo | null }>("/api/resume");

export const deleteResume = () => call<{ resume: null } & ProfileView>("/api/resume", { method: "DELETE" });

export function uploadResume(file: File) {
  const form = new FormData();
  form.append("file", file);
  return call<{ resume: ResumeInfo } & ProfileView>("/api/resume", { method: "POST", body: form });
}

export const startRun = (keyword: string, postings: number, source: Source) =>
  call<RunStatus>("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keyword, postings, source }),
  });

export const getRun = (id: string) => call<RunStatus>(`/api/runs/${id}`);

export const getActiveRun = () => call<{ run: RunStatus | null }>("/api/runs/active");

export const getProfile = () => call<ProfileView>("/api/profile");

export const refreshSummary = () => call<ProfileView>("/api/profile/summary", { method: "POST" });

export const putProfile = (profile: Profile) =>
  call<ProfileView>("/api/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });

// Marks keep the whole job, so applied jobs still show after a new search replaces the results.
export interface MarksView {
  marks: Record<string, Status>;
  jobs: Record<string, MarkedJob>;
  notes: Record<string, string>; // the user's reasons, only for marks that have one
}

export const getMarks = () => call<MarksView>("/api/marks");

export const putMark = (job: Job, status: Status | null, note = "") =>
  call<MarksView>(`/api/marks/${job.id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, note, job: status && { ...job, role: job.brief?.role ?? null } }),
  });

export const clearMarks = () => call<MarksView>("/api/marks", { method: "DELETE" });
