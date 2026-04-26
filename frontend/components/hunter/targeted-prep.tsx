"use client";

import { useState } from "react";
import type {
  OpponentProfile,
  OpponentOpeningEntry,
} from "@/lib/types";

function _formatDate(d: string | null): string {
  if (!d) return "—";
  // Accept "YYYY-MM-DD HH:MM:SS" or ISO
  const datePart = d.split(" ")[0];
  const parts = datePart.split("-");
  if (parts.length !== 3) return d;
  const [y, m, day] = parts;
  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const monthIdx = parseInt(m, 10) - 1;
  if (monthIdx < 0 || monthIdx > 11) return d;
  return `${parseInt(day, 10)} ${monthNames[monthIdx]} ${y}`;
}

function OpeningRow({
  entry,
  variant,
}: {
  entry: OpponentOpeningEntry;
  variant: "weakness" | "strength";
}) {
  const colorClass =
    variant === "weakness"
      ? "text-red-500 dark:text-red-400"
      : "text-emerald-600 dark:text-emerald-400";
  const barClass =
    variant === "weakness"
      ? "bg-red-500/80 dark:bg-red-400/80"
      : "bg-emerald-500/80 dark:bg-emerald-400/80";
  const label = variant === "weakness" ? "Loses" : "Wins";

  return (
    <div className="border rounded-lg bg-card p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium truncate" title={entry.name}>
            {entry.name}
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {entry.total} game{entry.total === 1 ? "" : "s"}
            {variant === "weakness"
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
    </div>
  );
}

interface TargetedPrepProps {
  profile: OpponentProfile;
  onRefresh: () => void;
  refreshing?: boolean;
}

export function TargetedPrep({
  profile,
  onRefresh,
  refreshing = false,
}: TargetedPrepProps) {
  const [color, setColor] = useState<"white" | "black">("white");

  const weaknesses = profile.weaknesses[color] || [];
  const strengths = profile.strengths[color] || [];
  const empty = weaknesses.length === 0 && strengths.length === 0;
  const hasGames = profile.total_games > 0;

  return (
    <div className="border rounded-lg bg-muted/30 p-4 space-y-4">
      {/* Header: opponent identity + stats + refresh */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <span>{profile.meta.username}</span>
            <span className="text-xs font-normal px-2 py-0.5 rounded bg-muted text-muted-foreground">
              {profile.meta.platform}
            </span>
          </h2>
          {hasGames ? (
            <p className="text-xs text-muted-foreground mt-1">
              {profile.total_games} games · {profile.results.wins}W /{" "}
              {profile.results.losses}L / {profile.results.draws}D ·{" "}
              <span className="font-medium">
                {profile.results.win_rate}% win rate
              </span>
            </p>
          ) : (
            <p className="text-xs text-muted-foreground mt-1">
              No recent games found for this opponent.
            </p>
          )}
          <p className="text-[10px] text-muted-foreground mt-1">
            {profile.meta.cached
              ? `Cached · last fetched ${_formatDate(profile.meta.fetched_at)}`
              : `Fresh fetch · ${_formatDate(profile.meta.fetched_at)}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Color toggle */}
          <div className="flex rounded-md border bg-background p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setColor("white")}
              className={`px-3 py-1 rounded ${color === "white" ? "bg-muted font-medium" : "text-muted-foreground"}`}
            >
              as White
            </button>
            <button
              type="button"
              onClick={() => setColor("black")}
              className={`px-3 py-1 rounded ${color === "black" ? "bg-muted font-medium" : "text-muted-foreground"}`}
            >
              as Black
            </button>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            className="text-xs px-2 py-1 rounded border bg-background hover:bg-muted disabled:opacity-50"
            title="Force a fresh fetch (bypasses 24h cache)"
          >
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      {!hasGames ? (
        <p className="text-sm text-muted-foreground text-center py-6">
          No public games found for{" "}
          <strong>{profile.meta.username}</strong> on{" "}
          <strong>{profile.meta.platform}</strong> in the last 3 months.
          Check the username spelling and platform, then try again.
        </p>
      ) : empty ? (
        <p className="text-sm text-muted-foreground text-center py-6">
          {profile.meta.username} has played as {color} but no opening
          appears in 2+ games yet — try the other color.
        </p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Weaknesses — what they LOSE = our hunting targets */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold text-red-500 dark:text-red-400 uppercase tracking-wider">
                Their Weaknesses
              </span>
              <span className="text-[10px] text-muted-foreground">
                target these openings
              </span>
            </div>
            {weaknesses.length === 0 ? (
              <p className="text-xs text-muted-foreground italic py-4">
                No recurring losing openings as {color}.
              </p>
            ) : (
              <div className="space-y-2">
                {weaknesses.map((entry) => (
                  <OpeningRow
                    key={entry.name}
                    entry={entry}
                    variant="weakness"
                  />
                ))}
              </div>
            )}
          </div>

          {/* Strengths — what they WIN = avoid these lines */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
                Their Strengths
              </span>
              <span className="text-[10px] text-muted-foreground">
                avoid these lines
              </span>
            </div>
            {strengths.length === 0 ? (
              <p className="text-xs text-muted-foreground italic py-4">
                No standout winning openings as {color}.
              </p>
            ) : (
              <div className="space-y-2">
                {strengths.map((entry) => (
                  <OpeningRow
                    key={entry.name}
                    entry={entry}
                    variant="strength"
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
