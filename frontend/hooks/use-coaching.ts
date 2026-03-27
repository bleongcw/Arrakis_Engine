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

      // Capture the old provider to detect when coaching is done
      // (the provider field changes to "provider:model" format)
      let oldProvider: string | null = null;
      try {
        const before = await fetchGameDetail(gameId);
        oldProvider = before.coaching?.provider || null;
      } catch {
        // ignore — we'll poll anyway
      }

      try {
        await triggerCoaching(gameId, provider);

        // Poll for completion — detect by checking:
        // 1. coaching_status goes back to "complete" (backend sets to "pending" then "complete")
        // 2. coaching.provider changes to include the new provider
        let attempts = 0;
        let sawPending = false;

        pollRef.current = setInterval(async () => {
          attempts++;
          try {
            const detail = await fetchGameDetail(gameId);
            const game = detail.game;
            const coaching = detail.coaching;

            // Track if we've seen the "pending" state (confirms backend received request)
            if (game.coaching_status === "pending") {
              sawPending = true;
            }

            // Coaching is done when:
            // - Status is "complete" AND we saw it go to pending first
            //   (or the provider changed, meaning new coaching was stored)
            const providerChanged = coaching?.provider !== oldProvider;
            const isComplete = game.coaching_status === "complete";

            if (isComplete && (sawPending || providerChanged)) {
              if (pollRef.current) clearInterval(pollRef.current);
              setIsCoaching(false);
              setStatus(`Coached with ${coaching?.provider || provider}`);
              onComplete(detail);
            }

            // Error state
            if (game.coaching_status === "error" && sawPending) {
              if (pollRef.current) clearInterval(pollRef.current);
              setIsCoaching(false);
              setStatus("Coaching failed. Check server logs.");
            }
          } catch {
            // ignore polling errors
          }
          if (attempts >= 90) {
            // 90 * 3s = 4.5 minutes timeout
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
