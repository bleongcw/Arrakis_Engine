"use client";

import { useState, useRef, useCallback } from "react";
import { triggerCoaching, fetchGameDetail } from "@/lib/api";
import type { GameDetail } from "@/lib/types";

export function useCoaching(gameId: number) {
  const [isCoaching, setIsCoaching] = useState(false);
  const [status, setStatus] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startCoaching = useCallback(
    async (provider: "claude" | "openai", onComplete: (detail: GameDetail) => void) => {
      setIsCoaching(true);
      setStatus(`Coaching with ${provider === "claude" ? "Claude" : "ChatGPT"}...`);

      try {
        await triggerCoaching(gameId, provider);

        // Poll for completion
        let attempts = 0;
        pollRef.current = setInterval(async () => {
          attempts++;
          try {
            const detail = await fetchGameDetail(gameId);
            if (
              detail.coaching?.narrative &&
              detail.coaching.provider?.includes(provider)
            ) {
              if (pollRef.current) clearInterval(pollRef.current);
              setIsCoaching(false);
              setStatus(
                `Coached with ${detail.coaching.provider}`
              );
              onComplete(detail);
            }
          } catch {
            // ignore polling errors
          }
          if (attempts >= 60) {
            if (pollRef.current) clearInterval(pollRef.current);
            setIsCoaching(false);
            setStatus("Coaching timed out. Refresh to check.");
          }
        }, 3000);
      } catch (err) {
        setIsCoaching(false);
        setStatus(`Error: ${err}`);
      }
    },
    [gameId]
  );

  return { isCoaching, status, startCoaching };
}
