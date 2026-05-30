"use client";

// ArrakisEngine — Chess Coaching AI
// Copyright (C) 2026 Bernard Leong
// Licensed under AGPL-3.0. See LICENSE file.

import type { OpeningTarget } from "@/lib/types";

/**
 * v1.21.0 Tournament Prep — combined opening analysis across the roster.
 *
 * "Prep these" = openings the field collectively LOSES to (your attacking
 * targets). "Avoid these" = openings the field WINS with (lines to dodge).
 * Each row carries how many opponents share it + the aggregate rate.
 */

function TargetRow({ row, tone }: { row: OpeningTarget; tone: "prep" | "avoid" }) {
  const accent =
    tone === "prep"
      ? "text-emerald-700 dark:text-emerald-400"
      : "text-red-700 dark:text-red-400";
  return (
    <li className="py-2 border-b border-border last:border-0">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium">
          {row.opening}
          {row.eco && (
            <span className="ml-1 text-xs text-muted-foreground">{row.eco}</span>
          )}
          <span className="ml-1 text-xs text-muted-foreground">
            · as {row.color}
          </span>
        </span>
        <span className={`text-xs font-semibold whitespace-nowrap ${accent}`}>
          {row.opponent_count} opp · {Math.round(row.agg_rate)}%
        </span>
      </div>
      <div className="text-[11px] text-muted-foreground mt-0.5">
        {row.opponents.join(", ")}
      </div>
    </li>
  );
}

export function OpeningTargets({
  targets,
  cautions,
}: {
  targets: OpeningTarget[];
  cautions: OpeningTarget[];
}) {
  const lead = targets[0];
  return (
    <div data-testid="opening-targets">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-1">
        Opening Targets
      </h3>
      {lead ? (
        <p
          className="text-sm font-medium mb-3 text-emerald-700 dark:text-emerald-400"
          data-testid="opening-targets-headline"
        >
          🎯 Prep the {lead.opening} as {lead.color} — {lead.opponent_count} of
          this field lose to it ({Math.round(lead.agg_rate)}% loss rate).
        </p>
      ) : (
        <p className="text-xs text-muted-foreground mb-3 italic">
          No shared opening targets yet — add more opponents or run Prep Roster.
        </p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h4 className="text-xs font-semibold text-emerald-700 dark:text-emerald-400 mb-1">
            Prep these (the field loses to)
          </h4>
          {targets.length ? (
            <ul data-testid="prep-list">
              {targets.map((r) => (
                <TargetRow key={`${r.opening}-${r.color}`} row={r} tone="prep" />
              ))}
            </ul>
          ) : (
            <p className="text-xs text-muted-foreground italic">None shared.</p>
          )}
        </div>
        <div>
          <h4 className="text-xs font-semibold text-red-700 dark:text-red-400 mb-1">
            Avoid these (the field wins with)
          </h4>
          {cautions.length ? (
            <ul data-testid="avoid-list">
              {cautions.map((r) => (
                <TargetRow key={`${r.opening}-${r.color}`} row={r} tone="avoid" />
              ))}
            </ul>
          ) : (
            <p className="text-xs text-muted-foreground italic">None shared.</p>
          )}
        </div>
      </div>
    </div>
  );
}
