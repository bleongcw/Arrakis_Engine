"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { JournalEntry } from "@/lib/api";
import type { GameListItem } from "@/lib/types";
import { parseTrendSummary } from "@/lib/summary";
import { useLiveRelativeTime } from "@/lib/relative-time";
import { TimelineNode } from "./timeline-thread";

/** v1.11.0: A single Journal entry card on the threaded feed.
 *
 * Visual:
 *   - Left border (2px, muted) provides the timeline rail
 *   - Colored TimelineNode dot sits on the rail at the card's date line
 *   - Header: kind icon · live-updating relative timestamp · platform + model badges
 *   - Body: 4-paragraph review text (expandable)
 *   - Footer: clickable referenced-game pills
 *
 * Behavior:
 *   - `defaultExpanded=true` (latest entries) → full body shown
 *   - `defaultExpanded=false` (older entries) → one-line preview, click to expand
 *   - `pulseOnMount=true` → 2-second emerald glow + scroll-into-view, used when
 *     a freshly-generated entry lands during the user's session
 */

const KIND_ICONS: Record<string, string> = {
  review: "📖",
  note: "📝",
  tournament_game: "🏆",
};

const KIND_LABELS: Record<string, string> = {
  review: "Review",
  note: "Note",
  tournament_game: "Tournament Game",
};

export interface EntryCardProps {
  entry: JournalEntry;
  player: string;
  games: GameListItem[];
  defaultExpanded?: boolean;
  pulseOnMount?: boolean;
}

export function EntryCard({
  entry,
  player,
  games,
  defaultExpanded = true,
  pulseOnMount = false,
}: EntryCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [pulsing, setPulsing] = useState(pulseOnMount);
  const ref = useRef<HTMLElement | null>(null);

  // Scroll-into-view + pulse when a freshly-generated entry lands.
  // Only fires on mount when pulseOnMount=true to avoid spam.
  useEffect(() => {
    if (!pulseOnMount || !ref.current) return;
    ref.current.scrollIntoView({ behavior: "smooth", block: "center" });
    // Hold the glow for 2 seconds then fade out
    const timer = setTimeout(() => setPulsing(false), 2000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Live-updating relative timestamp ("today" → "yesterday" → "3 days ago")
  const relative = useLiveRelativeTime(entry.created_at);

  // Resolve referenced game IDs → list items so we can render pills with links
  const refGames = (entry.refs || [])
    .map((id) => games.find((g) => g.id === id))
    .filter((g): g is GameListItem => Boolean(g));

  const icon = KIND_ICONS[entry.kind] ?? "📄";
  const kindLabel = KIND_LABELS[entry.kind] ?? entry.kind.replace(/_/g, " ");
  const paragraphs = parseTrendSummary(entry.body || "");
  const previewText = paragraphs[0]?.split(/(?<=[.!?])\s/)[0]?.slice(0, 140) ?? "";

  return (
    <article
      ref={ref}
      data-entry-id={entry.id}
      className={
        // Left border = the timeline rail. Padding leaves room for the node.
        // `transition-colors duration-500` makes the pulse fade out smoothly.
        "relative pl-6 ml-2 border-l-2 border-border " +
        "rounded-r-md transition-colors duration-500 " +
        (pulsing ? "bg-emerald-500/10" : "bg-transparent")
      }
    >
      <TimelineNode kind={entry.kind} title={`${kindLabel} · ${entry.platform}`} />

      <header className="flex items-baseline gap-2 flex-wrap pb-1">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-sm font-semibold hover:text-foreground/80 cursor-pointer text-left"
          aria-expanded={expanded}
          title={expanded ? "Collapse" : "Expand"}
        >
          {icon} {kindLabel}
        </button>
        <span className="text-xs text-muted-foreground">· {relative}</span>
        <span
          className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
          title={`Platform: ${entry.platform}`}
        >
          {entry.platform}
        </span>
        {entry.provider && (
          <span
            className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
            title={`Model: ${entry.provider}`}
          >
            {entry.provider.split(":")[1] || entry.provider}
          </span>
        )}
        {!expanded && (
          <button
            type="button"
            onClick={() => setExpanded(true)}
            className="ml-auto text-xs text-muted-foreground hover:text-foreground"
          >
            expand ↓
          </button>
        )}
      </header>

      {expanded ? (
        <div className="space-y-3 pt-1 pb-3">
          {paragraphs.map((p, i) => (
            <p key={i} className="text-sm leading-relaxed whitespace-pre-wrap">
              {p}
            </p>
          ))}
          {refGames.length > 0 && (
            <div className="pt-1 flex items-center gap-1.5 flex-wrap">
              <span className="text-xs text-muted-foreground">Referenced games:</span>
              {refGames.map((g) => (
                <Link
                  key={g.id}
                  href={`/${player}/games/${g.id}`}
                  className="text-xs px-2 py-0.5 rounded border border-emerald-500/40 hover:bg-emerald-500/10 transition-colors"
                  title={`${g.date_played} · ${g.result} as ${g.player_color}`}
                >
                  #{g.id} {g.result === "win" ? "✓" : g.result === "loss" ? "✗" : "="}
                </Link>
              ))}
            </div>
          )}
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="block w-full text-left text-xs text-muted-foreground pb-3 hover:text-foreground transition-colors"
        >
          {previewText}
          {previewText && paragraphs[0]?.length > 140 ? "…" : ""}
        </button>
      )}
    </article>
  );
}
