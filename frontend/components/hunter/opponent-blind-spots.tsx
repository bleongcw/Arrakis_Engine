"use client";

// ArrakisEngine — Chess Coaching AI
// Copyright (C) 2026 Bernard Leong
// Licensed under AGPL-3.0. See LICENSE file.

import { useCallback, useRef, useState } from "react";
import { MotifThemes } from "@/components/patterns/motif-themes";
import type { MotifSummaryData } from "@/components/patterns/motif-themes";
import { motifLabel } from "@/lib/motifs";
import { triggerHuntScan, fetchPipelineStatus } from "@/lib/api";
import type { OpponentProfile, HuntPlatform } from "@/lib/types";

/**
 * v1.20.0 Hunter Mode Deep Scan — "Tactical Blind Spots".
 *
 * Opt-in: runs Stockfish + the 12 motif detectors over the opponent's
 * last N games (background job), then renders the themes they MISS via
 * the shared <MotifThemes> card, retitled and reframed as "themes to
 * bait them into". Slow by design — the button carries a time warning.
 */

const SCAN_TASK = "hunt_scan";

function buildHeadline(summary: MotifSummaryData): string | null {
  const top = (summary.by_motif || []).find((m) => m.missed > 0);
  if (!top) return null;
  const label = motifLabel(top.motif).label;
  return `Bait ${label.toLowerCase()} — misses ${Math.round(
    top.miss_rate,
  )}% of ${label.toLowerCase()} tactics across ${summary.total_critical_moves} critical moves.`;
}

export function OpponentBlindSpots({
  opponent,
  platform,
  profile,
  onScanComplete,
}: {
  opponent: string;
  platform: HuntPlatform;
  profile: OpponentProfile;
  onScanComplete: () => void;
}) {
  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const summary = (profile.motif_summary ?? null) as MotifSummaryData | null;
  const deepScan = profile.deep_scan;
  const analyzed = deepScan?.analyzed_games ?? 0;
  const hasResults =
    !!summary && (summary.total_critical_moves ?? 0) >= 0 && analyzed > 0;
  const headline = summary ? buildHeadline(summary) : null;

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const runScan = useCallback(async () => {
    setError(null);
    setScanning(true);
    setProgress("Starting deep scan...");
    try {
      await triggerHuntScan(opponent, platform);
    } catch (e) {
      setScanning(false);
      setError(e instanceof Error ? e.message : "Failed to start deep scan.");
      return;
    }
    pollRef.current = setInterval(async () => {
      const s = await fetchPipelineStatus().catch(() => null);
      if (!s) return;
      if (s.task === SCAN_TASK && s.status === "running") {
        setProgress(s.progress || "Scanning...");
        return;
      }
      // Terminal (complete / error / idle) — stop and refresh.
      stopPolling();
      setScanning(false);
      if (s.status === "error") {
        setError(s.error || "Deep scan failed.");
      } else {
        onScanComplete();
      }
    }, 2000);
  }, [opponent, platform, onScanComplete, stopPolling]);

  return (
    <div data-testid="opponent-blind-spots">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Tactical Blind Spots
        </h3>
        <button
          onClick={runScan}
          disabled={scanning}
          className="text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
        >
          {scanning
            ? "Deep scanning…"
            : analyzed > 0
              ? "Re-scan (Stockfish)"
              : "Deep Scan (Stockfish)"}
        </button>
      </div>
      <p className="text-xs text-muted-foreground mb-3">
        Runs Stockfish over the opponent&apos;s recent games to find the
        tactical themes they MISS — the patterns to bait them into. This is a
        full engine analysis and takes several minutes.
        {analyzed > 0 && (
          <span className="ml-1">
            Scanned {analyzed} game{analyzed === 1 ? "" : "s"} so far.
          </span>
        )}
      </p>

      {scanning && (
        <div
          className="mb-3 text-xs text-muted-foreground flex items-center gap-2"
          data-testid="blind-spots-progress"
        >
          <span className="inline-block w-3 h-3 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          {progress}
        </div>
      )}

      {error && (
        <p className="text-xs text-destructive mb-3" data-testid="blind-spots-error">
          {error}
        </p>
      )}

      {hasResults && headline && (
        <p
          className="text-sm font-medium mb-3 text-amber-700 dark:text-amber-400"
          data-testid="blind-spots-headline"
        >
          🎯 {headline}
        </p>
      )}

      {hasResults ? (
        <MotifThemes data={summary ?? undefined} />
      ) : (
        !scanning && (
          <p className="text-xs text-muted-foreground italic">
            No deep scan yet — run one to reveal this opponent&apos;s tactical
            blind spots.
          </p>
        )
      )}
    </div>
  );
}
