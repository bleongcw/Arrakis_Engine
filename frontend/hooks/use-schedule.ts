"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchScheduleStatus,
  toggleSchedule as apiToggle,
  updateScheduleInterval as apiUpdateInterval,
} from "@/lib/api";
import type { ScheduleState } from "@/lib/types";

const DEFAULT_STATE: ScheduleState = {
  enabled: false,
  interval_hours: 6,
  next_run_time: null,
  last_run_at: null,
  last_run_status: null,
  last_run_message: null,
};

export function useSchedule() {
  const [state, setState] = useState<ScheduleState>(DEFAULT_STATE);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const poll = useCallback(async () => {
    try {
      const s = await fetchScheduleStatus();
      setState(s);
    } catch {
      // Ignore polling errors (backend may not be running)
    }
  }, []);

  // Poll every 30s
  useEffect(() => {
    poll();
    intervalRef.current = setInterval(poll, 30000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [poll]);

  const toggle = useCallback(
    async (enabled: boolean) => {
      const s = await apiToggle(enabled);
      setState(s);
    },
    []
  );

  const updateInterval = useCallback(
    async (hours: number) => {
      const s = await apiUpdateInterval(hours);
      setState(s);
    },
    []
  );

  return { state, toggle, updateInterval, refresh: poll };
}
