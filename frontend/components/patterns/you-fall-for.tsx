"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import type { TrapEntry } from "@/lib/types";

function YouFallForInfoModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div className="relative bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-2xl w-[400px] p-5 text-sm" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-3">
          <h4 className="font-bold text-base text-zinc-900 dark:text-zinc-100">Trap Patterns</h4>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-xl leading-none -mt-1">&times;</button>
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 text-xs mb-3">
          Named opening traps detected in your games using the Lichess
          chess-openings database (CC0). The matcher looks at the actual
          move sequence and identifies well-known beginner traps:
        </p>
        <ul className="text-xs space-y-1.5 text-zinc-600 dark:text-zinc-400">
          <li><strong>Your Arsenal</strong> — traps you successfully use to win. Keep practising these.</li>
          <li><strong>You Fall For</strong> — traps your opponents have used to beat you. Study how to defend or sidestep them.</li>
        </ul>
        <p className="text-zinc-500 dark:text-zinc-500 text-[10px] mt-3">
          Frequency labels: <strong>Rare</strong> (1-2 games), <strong>Occasional</strong> (3-5 games), <strong>Frequent</strong> (6+ games).
          The library covers ~100 well-known traps including Stafford, Elephant, Fried Liver, Englund, and Halloween.
        </p>
      </div>
    </div>,
    document.body
  );
}

function _formatDate(d: string): string {
  // Accept "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS"
  const datePart = d.split(" ")[0];
  const parts = datePart.split("-");
  if (parts.length !== 3) return d;
  const [, m, day] = parts;
  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const monthIdx = parseInt(m, 10) - 1;
  if (monthIdx < 0 || monthIdx > 11) return d;
  return `${parseInt(day, 10)} ${monthNames[monthIdx]}`;
}

function TrapRow({ entry, variant }: { entry: TrapEntry; variant: "arsenal" | "fall" }) {
  const accent =
    variant === "arsenal"
      ? "border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/50 dark:bg-emerald-950/20"
      : "border-red-200 dark:border-red-900/50 bg-red-50/50 dark:bg-red-950/20";
  const countColor =
    variant === "arsenal"
      ? "text-emerald-600 dark:text-emerald-400"
      : "text-red-500 dark:text-red-400";

  const lastDate = entry.recent_dates[0] ? _formatDate(entry.recent_dates[0]) : "—";
  const winPct = Math.round(entry.win_rate);
  const lossPct = entry.total > 0 ? Math.round((entry.losses / entry.total) * 100) : 0;

  return (
    <div className={`border rounded-lg p-3 ${accent}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium truncate" title={entry.name}>
            {entry.eco && (
              <span className="inline-block text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded mr-2 align-middle">
                {entry.eco}
              </span>
            )}
            {entry.name}
          </div>
          <div className="text-xs text-muted-foreground mt-1 flex items-center gap-2">
            <span>{entry.frequency_label}</span>
            <span>·</span>
            <span title="Last occurrence">📅 {lastDate}</span>
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className={`text-base font-bold ${countColor}`}>{entry.count}×</div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
            {variant === "arsenal" ? `${winPct}% wins` : `${lossPct}% / ${winPct}%`}
          </div>
        </div>
      </div>
    </div>
  );
}

export function YouFallFor({
  arsenal,
  falls,
}: {
  arsenal?: TrapEntry[];
  falls?: TrapEntry[];
}) {
  const [showInfo, setShowInfo] = useState(false);
  const arsenalList = arsenal || [];
  const fallsList = falls || [];
  const empty = arsenalList.length === 0 && fallsList.length === 0;

  return (
    <div className="border rounded-lg bg-muted/30 p-4 mt-4">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Trap Patterns
          </h3>
          <button
            onClick={() => setShowInfo(true)}
            className="text-sm text-muted-foreground hover:text-foreground cursor-help select-none transition-colors"
            title="What is this?"
          >
            &#9432;
          </button>
        </div>
      </div>
      {showInfo && <YouFallForInfoModal onClose={() => setShowInfo(false)} />}

      <p className="text-xs text-muted-foreground mb-4">
        Recurring named opening traps in your games — the ones you fall into,
        and the ones you use successfully. Detected against the Lichess CC0
        opening database.
      </p>

      {empty ? (
        <p className="text-sm text-muted-foreground text-center py-6">
          No named trap patterns detected yet. Either you're avoiding the
          common beginner traps (good!) or there aren't enough games yet.
        </p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Left: Your Arsenal */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
                Your Arsenal
              </span>
              <span className="text-[10px] text-muted-foreground">keep using!</span>
            </div>
            {arsenalList.length === 0 ? (
              <p className="text-xs text-muted-foreground italic py-4">
                No named traps in your winning repertoire yet.
              </p>
            ) : (
              <div className="space-y-2">
                {arsenalList.map((entry) => (
                  <TrapRow key={entry.name} entry={entry} variant="arsenal" />
                ))}
              </div>
            )}
          </div>

          {/* Right: You Fall For */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold text-red-500 dark:text-red-400 uppercase tracking-wider">
                You Fall For
              </span>
              <span className="text-[10px] text-muted-foreground">avoid these!</span>
            </div>
            {fallsList.length === 0 ? (
              <p className="text-xs text-muted-foreground italic py-4">
                No recurring named-trap losses. Nice defending.
              </p>
            ) : (
              <div className="space-y-2">
                {fallsList.map((entry) => (
                  <TrapRow key={entry.name} entry={entry} variant="fall" />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
