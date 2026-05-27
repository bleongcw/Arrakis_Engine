"use client";

// ArrakisEngine — Chess Coaching AI
// Copyright (C) 2026 Bernard Leong
// Licensed under AGPL-3.0. See LICENSE file.

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { motifLabel } from "@/lib/motifs";

/**
 * v1.15.0: Tactical Themes card on the Patterns page.
 *
 * Pairs visually with the existing Tactical Awareness card — that one
 * tells you HOW OFTEN you miss tactics; this one tells you WHICH
 * TACTICAL THEMES you miss most.
 *
 * Data source: `stats.motif_summary` (added in v1.15.0 by
 * `src/patterns.py::_compute_motif_summary`).
 *
 * Renders nothing when the prop is undefined (older patterns rows that
 * pre-date v1.15.0). When `total_critical_moves === 0`, renders an
 * empty-state message instead of an empty bar chart.
 */

type MotifEntry = {
  motif: string;
  missed: number;
  found: number;
  miss_rate: number;
};

export type MotifSummaryData = {
  period_days: number;
  total_critical_moves: number;
  by_motif: MotifEntry[];
  top_missed: string | null;
  top_missed_count: number;
};

const FOUND_COLOR = "#22c55e"; // emerald — matches MotifBadgeRow
const MISSED_COLOR = "#f59e0b"; // amber — matches MotifBadgeRow

function MotifRow({ entry }: { entry: MotifEntry }) {
  const total = entry.missed + entry.found;
  if (total === 0) return null;

  const meta = motifLabel(entry.motif);
  const foundPct = (entry.found / total) * 100;
  const missedPct = (entry.missed / total) * 100;

  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium">
          {meta.icon} {meta.label}
        </span>
        <span className="text-xs text-muted-foreground">
          {entry.found} found · {entry.missed} missed · {Math.round(entry.miss_rate)}% miss rate
        </span>
      </div>
      <div className="w-full h-7 rounded-md overflow-hidden flex">
        {foundPct > 0 && (
          <div
            className="h-full flex items-center justify-center text-xs font-semibold text-white"
            style={{ width: `${foundPct}%`, backgroundColor: FOUND_COLOR, minWidth: foundPct > 5 ? "auto" : 0 }}
          >
            {foundPct >= 10 && entry.found}
          </div>
        )}
        {missedPct > 0 && (
          <div
            className="h-full flex items-center justify-center text-xs font-semibold text-white"
            style={{ width: `${missedPct}%`, backgroundColor: MISSED_COLOR, minWidth: missedPct > 5 ? "auto" : 0 }}
          >
            {missedPct >= 10 && entry.missed}
          </div>
        )}
      </div>
    </div>
  );
}

function MotifInfoModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div className="relative bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-2xl w-[380px] p-5 text-sm" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-3">
          <h4 className="font-bold text-base text-zinc-900 dark:text-zinc-100">Tactical Themes</h4>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-xl leading-none -mt-1">×</button>
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 text-xs mb-3">
          Every critical move is scanned for 8 named tactical themes (fork,
          pin, skewer, discovered check, mate threat, removing the defender,
          hanging piece, trapped piece). This card aggregates those tags
          across your recent games.
        </p>
        <ul className="text-xs space-y-1.5 text-zinc-600 dark:text-zinc-400">
          <li><span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: FOUND_COLOR, marginRight: 6 }} />
            <strong>Found</strong> — you executed the theme the engine wanted</li>
          <li><span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: MISSED_COLOR, marginRight: 6 }} />
            <strong>Missed</strong> — the best move had this theme; your move didn't</li>
        </ul>
        <p className="text-zinc-600 dark:text-zinc-400 text-xs mt-3">
          The most-missed theme is your biggest tactical blind spot — practice
          it first.
        </p>
        <p className="text-zinc-500 dark:text-zinc-500 text-[10px] mt-2">
          Themes are detected by python-chess on each critical move
          (introduced in v1.14.0; aggregated in v1.15.0).
        </p>
      </div>
    </div>,
    document.body
  );
}

export function MotifThemes({ data }: { data?: MotifSummaryData }) {
  const [showInfo, setShowInfo] = useState(false);

  if (!data) {
    // Older patterns row that pre-dates v1.15.0 — render nothing
    // rather than show a broken-looking empty card.
    return null;
  }

  const sorted = [...(data.by_motif || [])]
    .filter((e) => e.missed + e.found > 0)
    .sort((a, b) => b.missed - a.missed || b.found - a.found);

  const emptyState = data.total_critical_moves === 0 || sorted.length === 0;

  const topMeta = data.top_missed ? motifLabel(data.top_missed) : null;

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Tactical Themes
          </h3>
          <button
            onClick={() => setShowInfo(true)}
            className="text-sm text-muted-foreground hover:text-foreground cursor-help select-none transition-colors"
            title="What are tactical themes?"
          >
            &#9432;
          </button>
        </div>
        {showInfo && <MotifInfoModal onClose={() => setShowInfo(false)} />}
        {topMeta && data.top_missed_count > 0 && (
          <div className="text-right">
            <span className="text-2xl font-bold text-amber-500">{data.top_missed_count}</span>
            <span className="text-xs text-muted-foreground ml-1">
              {topMeta.icon} {topMeta.label}
            </span>
          </div>
        )}
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        {emptyState
          ? `No tactical themes detected yet over the last ${data.period_days} days. Coach more games or run rescan-motifs.`
          : `${data.total_critical_moves} critical moves scanned over the last ${data.period_days} days. Most-missed theme is your biggest blind spot.`}
      </p>

      {!emptyState && (
        <>
          {/* Legend */}
          <div className="flex items-center gap-4 mb-3 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: FOUND_COLOR }} />
              <span>Found</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: MISSED_COLOR }} />
              <span>Missed</span>
            </div>
          </div>

          {sorted.map((entry) => (
            <MotifRow key={entry.motif} entry={entry} />
          ))}
        </>
      )}
    </div>
  );
}
