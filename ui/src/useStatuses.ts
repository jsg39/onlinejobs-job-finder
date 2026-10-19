import { useCallback, useEffect, useState } from "react";
import { getMarks, putMark } from "./api";
import type { Job, MarkedJob, Status } from "./types";

/**
 * Applied / not-interested marks. They live on the backend, where they teach the
 * profile what you like; the UI updates at once and rolls back if the save fails.
 */
export function useStatuses() {
  const [statuses, setStatuses] = useState<Record<string, Status>>({});
  const [markedJobs, setMarkedJobs] = useState<Record<string, MarkedJob>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMarks()
      .then((r) => {
        setStatuses(r.marks);
        setMarkedJobs(r.jobs);
        setNotes(r.notes);
      })
      .catch(() => {});
  }, []);

  const setStatus = useCallback((job: Job, status: Status | null, note = "") => {
    let previous: Record<string, Status> = {};
    setStatuses((prev) => {
      previous = prev;
      const next = { ...prev };
      if (status) next[job.id] = status;
      else delete next[job.id];
      return next;
    });
    putMark(job, status, note)
      .then((r) => {
        setStatuses(r.marks);
        setMarkedJobs(r.jobs);
        setNotes(r.notes);
        setError(null);
      })
      .catch((e) => {
        setStatuses(previous);
        setError(e instanceof Error ? e.message : String(e));
      });
  }, []);

  return { statuses, markedJobs, notes, setStatus, error };
}
