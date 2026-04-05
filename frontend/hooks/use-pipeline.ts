"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchPipelineStatus,
  triggerPipelineHarvest,
  triggerPipelineAnalyze,
  triggerPipelinePatterns,
  triggerPipelineRunAll,
  triggerPipelineCoach,
  cancelPipeline,
} from "@/lib/api";
import type { PipelineState } from "@/lib/types";

const IDLE_STATE: PipelineState = {
  task: null,
  status: "idle",
  progress: "",
  detail: null,
  result: null,
  error: null,
  started_at: null,
  finished_at: null,
  triggered_by: null,
};

export function usePipeline() {
  const [state, setState] = useState<PipelineState>(IDLE_STATE);
  const [dismissed, setDismissed] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll pipeline status
  const poll = useCallback(async () => {
    try {
      const s = await fetchPipelineStatus();
      setState(s);
      return s;
    } catch {
      // Ignore polling errors
      return null;
    }
  }, []);

  // Start polling when a task is running
  useEffect(() => {
    if (state.status === "running") {
      setDismissed(false);
      if (!intervalRef.current) {
        intervalRef.current = setInterval(poll, 2000);
      }
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [state.status, poll]);

  // Initial fetch on mount
  useEffect(() => {
    poll();
  }, [poll]);

  const startHarvest = useCallback(
    async (player?: string) => {
      setDismissed(false);
      await triggerPipelineHarvest(player);
      // Immediately poll to get the running state
      await poll();
    },
    [poll]
  );

  const startAnalyze = useCallback(async () => {
    setDismissed(false);
    await triggerPipelineAnalyze();
    await poll();
  }, [poll]);

  const startPatterns = useCallback(
    async (player?: string) => {
      setDismissed(false);
      await triggerPipelinePatterns(player);
      await poll();
    },
    [poll]
  );

  const startRunAll = useCallback(
    async (player?: string) => {
      setDismissed(false);
      await triggerPipelineRunAll(player);
      await poll();
    },
    [poll]
  );

  const startCoach = useCallback(
    async (provider?: string, player?: string) => {
      setDismissed(false);
      await triggerPipelineCoach(provider, player);
      await poll();
    },
    [poll]
  );

  const cancel = useCallback(async () => {
    await cancelPipeline();
    await poll();
  }, [poll]);

  const dismiss = useCallback(() => {
    setDismissed(true);
  }, []);

  return {
    state,
    dismissed,
    startHarvest,
    startAnalyze,
    startPatterns,
    startRunAll,
    startCoach,
    cancel,
    dismiss,
    refresh: poll,
  };
}
