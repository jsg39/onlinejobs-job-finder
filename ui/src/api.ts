import type { Job, Profile, ProfileView, ResumeInfo, Run, RunStatus, Status } from "./types";

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

export const startRun = (keyword: string, postings: number) =>
  call<RunStatus>("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keyword, postings }),
  });

export const getRun = (id: string) => call<RunStatus>(`/api/runs/${id}`);

export const getActiveRun = () => call<{ run: RunStatus | null }>("/api/runs/active");

export const getProfile = () => call<ProfileView>("/api/profile");

export const putProfile = (profile: Profile) =>
  call<ProfileView>("/api/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });

export const getMarks = () => call<{ marks: Record<string, Status> }>("/api/marks");

export const putMark = (job: Job, status: Status | null) =>
  call<{ marks: Record<string, Status> }>(`/api/marks/${job.id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      status,
      job: status && {
        id: job.id,
        title: job.title,
        type: job.type,
        skills: job.skills,
        pay_usd_month: job.pay_usd_month,
        role: job.brief?.role ?? null,
      },
    }),
  });

export const clearMarks = () => call<{ marks: Record<string, Status> }>("/api/marks", { method: "DELETE" });
