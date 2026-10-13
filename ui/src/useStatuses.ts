import { useCallback, useState } from "react";
import type { Status } from "./types";

const KEY = "ojagent:statuses";

function load(): Record<string, Status> {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}");
  } catch {
    return {};
  }
}

/** Applied / not-interested marks, kept in this browser across runs. */
export function useStatuses() {
  const [statuses, setStatuses] = useState<Record<string, Status>>(load);

  const setStatus = useCallback((id: string, status: Status | null) => {
    setStatuses((prev) => {
      const next = { ...prev };
      if (status) next[id] = status;
      else delete next[id];
      try {
        localStorage.setItem(KEY, JSON.stringify(next));
      } catch {
        // storage blocked: marks last for this session only
      }
      return next;
    });
  }, []);

  return { statuses, setStatus };
}
