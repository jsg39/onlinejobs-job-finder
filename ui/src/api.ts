import type { ResumeInfo, Run, RunStatus } from "./types";

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

export const deleteResume = () => call<{ resume: null }>("/api/resume", { method: "DELETE" });

export function uploadResume(file: File) {
  const form = new FormData();
  form.append("file", file);
  return call<{ resume: ResumeInfo }>("/api/resume", { method: "POST", body: form });
}

export const startRun = (keyword: string, pages: number) =>
  call<RunStatus>("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keyword, pages }),
  });

export const getRun = (id: string) => call<RunStatus>(`/api/runs/${id}`);

export const getActiveRun = () => call<{ run: RunStatus | null }>("/api/runs/active");
