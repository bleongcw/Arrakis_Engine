"use client";

// ArrakisEngine — Chess Coaching AI
// Copyright (C) 2026 Bernard Leong
// Licensed under AGPL-3.0. See LICENSE file.

import Link from "next/link";
import type { TournamentPrepOpponent } from "@/lib/types";

/**
 * v1.21.0 Tournament Prep — one opponent's at-a-glance card in the roster
 * grid. Links to the full Hunt view (deep dive + Deep Scan) and shows
 * scan coverage so you know who's been tactically profiled.
 */
export function OpponentCard({
  opponent,
  player,
  onRemove,
}: {
  opponent: TournamentPrepOpponent;
  player: string;
  onRemove: (id: number) => void;
}) {
  const s = opponent.summary;
  const scanned = opponent.deep_scan?.analyzed_games ?? 0;
  const huntHref =
    `/${player}/hunt?opponent=${encodeURIComponent(opponent.username)}` +
    `&platform=${encodeURIComponent(opponent.platform)}`;

  return (
    <div
      className="rounded-lg border border-border p-3 flex flex-col gap-2"
      data-testid={`opponent-card-${opponent.username}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <Link
            href={huntHref}
            className="text-sm font-semibold hover:underline truncate block"
          >
            {opponent.username}
          </Link>
          <span className="text-[11px] text-muted-foreground">
            {opponent.platform}
          </span>
        </div>
        <button
          onClick={() => onRemove(opponent.id)}
          className="text-muted-foreground/60 hover:text-red-600 text-xs"
          title="Remove from roster"
          aria-label={`Remove ${opponent.username}`}
        >
          ✕
        </button>
      </div>

      {opponent.status === "pending" || !s ? (
        <p className="text-xs text-muted-foreground italic">
          Not fetched yet — run Prep Roster.
        </p>
      ) : (
        <div className="text-xs text-muted-foreground">
          <div>
            {s.total_games} games · {s.win_rate.toFixed(0)}% win rate
          </div>
          <div className="mt-0.5">
            {s.wins}W / {s.losses}L / {s.draws}D
          </div>
        </div>
      )}

      <div className="mt-auto flex items-center justify-between text-[11px]">
        <span
          className={
            scanned > 0
              ? "text-emerald-700 dark:text-emerald-400"
              : "text-muted-foreground"
          }
        >
          {scanned > 0 ? `🔬 ${scanned} scanned` : "Not deep-scanned"}
        </span>
        <Link href={huntHref} className="text-primary hover:underline">
          Scout →
        </Link>
      </div>
    </div>
  );
}
