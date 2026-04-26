"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import type { LossOpeningAnalysis, LossOpeningEntry } from "@/lib/types";

function FixYourOpeningsInfoModal({ onClose }: { onClose: () => void }) {
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
          <h4 className="font-bold text-base text-zinc-900 dark:text-zinc-100">Fix Your Openings</h4>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-xl leading-none -mt-1">&times;</button>
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 text-xs mb-3">
          Two views of your opening repertoire by outcome, split by color:
        </p>
        <ul className="text-xs space-y-1.5 text-zinc-600 dark:text-zinc-400">
          <li><strong>Your ELO Leaks</strong> — openings where you lose the most often. Study these lines first &mdash; they bleed the most rating.</li>
          <li><strong>Your Strengths</strong> — openings where you win the most often. Keep playing these and look for chances to steer into them.</li>
        </ul>
        <p className="text-zinc-500 dark:text-zinc-500 text-[10px] mt-3">
          Openings need at least 2 games to appear. The percentage shows your loss-rate (left column) or win-rate (right column) in that opening.
        </p>
      </div>
    </div>,
    document.body
  );
}

function OpeningRow({
  entry,
  variant,
  player,
}: {
  entry: LossOpeningEntry;
  variant: "loss" | "win";
  player: string;
}) {
  const colorClass =
    variant === "loss"
      ? "text-red-500 dark:text-red-400"
      : "text-emerald-600 dark:text-emerald-400";
  const barClass =
    variant === "loss"
      ? "bg-red-500/80 dark:bg-red-400/80"
      : "bg-emerald-500/80 dark:bg-emerald-400/80";
  const label = variant === "loss" ? "Losses" : "Wins";

  return (
    <div className="border rounded-lg bg-card p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium truncate" title={entry.name}>
            {entry.name}
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {entry.total} game{entry.total === 1 ? "" : "s"}
            {variant === "loss"
              ? ` · ${entry.losses}L / ${entry.wins}W / ${entry.draws}D`
              : ` · ${entry.wins}W / ${entry.losses}L / ${entry.draws}D`}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className={`text-lg font-bold ${colorClass}`}>{entry.rate}%</div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
            {label}
          </div>
        </div>
      </div>
      <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden mt-2">
        <div
          className={`h-full ${barClass} transition-all duration-500`}
          style={{ width: `${Math.min(entry.rate, 100)}%` }}
        />
      </div>
      {entry.recent_game_ids.length > 0 && (
        <div className="mt-2 flex items-center gap-2 text-xs">
          <Link
            href={`/${player}/games/${entry.recent_game_ids[0]}`}
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            Study most recent →
          </Link>
        </div>
      )}
    </div>
  );
}

export function FixYourOpenings({
  data,
  strengths,
  player,
}: {
  data?: LossOpeningAnalysis;
  strengths?: LossOpeningAnalysis;
  player: string;
}) {
  const [showInfo, setShowInfo] = useState(false);
  const [color, setColor] = useState<"white" | "black">("white");

  const losses = (data && data[color]) || [];
  const wins = (strengths && strengths[color]) || [];

  const empty = losses.length === 0 && wins.length === 0;

  return (
    <div className="border rounded-lg bg-muted/30 p-4">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Fix Your Openings
          </h3>
          <button
            onClick={() => setShowInfo(true)}
            className="text-sm text-muted-foreground hover:text-foreground cursor-help select-none transition-colors"
            title="What is this?"
          >
            &#9432;
          </button>
        </div>
        {/* Color toggle */}
        <div className="flex rounded-md border bg-background p-0.5 text-xs">
          <button
            onClick={() => setColor("white")}
            className={`px-3 py-1 rounded ${color === "white" ? "bg-muted font-medium" : "text-muted-foreground"}`}
          >
            as White
          </button>
          <button
            onClick={() => setColor("black")}
            className={`px-3 py-1 rounded ${color === "black" ? "bg-muted font-medium" : "text-muted-foreground"}`}
          >
            as Black
          </button>
        </div>
      </div>
      {showInfo && <FixYourOpeningsInfoModal onClose={() => setShowInfo(false)} />}

      <p className="text-xs text-muted-foreground mb-4">
        Where you bleed ELO and what to keep using. Switch between colors to
        see your repertoire from each side.
      </p>

      {empty ? (
        <p className="text-sm text-muted-foreground text-center py-6">
          Need more games to surface opening patterns. Each opening needs at
          least 2 games to appear.
        </p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Left column: ELO leaks */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold text-red-500 dark:text-red-400 uppercase tracking-wider">
                Your ELO Leaks
              </span>
              <span className="text-[10px] text-muted-foreground">study these first</span>
            </div>
            {losses.length === 0 ? (
              <p className="text-xs text-muted-foreground italic py-4">
                No recurring losing openings as {color}. Nice.
              </p>
            ) : (
              <div className="space-y-2">
                {losses.map((entry) => (
                  <OpeningRow
                    key={entry.name}
                    entry={entry}
                    variant="loss"
                    player={player}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Right column: strengths */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
                Your Strengths
              </span>
              <span className="text-[10px] text-muted-foreground">keep using!</span>
            </div>
            {wins.length === 0 ? (
              <p className="text-xs text-muted-foreground italic py-4">
                No recurring winning openings as {color} yet.
              </p>
            ) : (
              <div className="space-y-2">
                {wins.map((entry) => (
                  <OpeningRow
                    key={entry.name}
                    entry={entry}
                    variant="win"
                    player={player}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
