"use client";

import { useState, useEffect, useMemo } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { ChessBoard } from "@/components/game-detail/chess-board";
import { MoveControls } from "@/components/game-detail/move-controls";
import { useChessNavigation } from "@/hooks/use-chess-navigation";
import { lichessAnalysisUrl } from "@/lib/chess/lichess";
import type { TrapEntry } from "@/lib/types";

// ── Trap library — fetched once and cached at module scope ───────────────

interface LibraryTrap {
  eco: string;
  name: string;
  moves_san: string;
  moves: string[];
  depth: number;
}

let _libraryCache: LibraryTrap[] | null = null;
let _libraryPromise: Promise<LibraryTrap[]> | null = null;

function loadTrapLibrary(): Promise<LibraryTrap[]> {
  if (_libraryCache) return Promise.resolve(_libraryCache);
  if (_libraryPromise) return _libraryPromise;
  _libraryPromise = fetch("/data/traps.json")
    .then((r) => r.json() as Promise<LibraryTrap[]>)
    .then((data) => {
      _libraryCache = data;
      return data;
    })
    .catch(() => {
      _libraryCache = [];
      return [];
    });
  return _libraryPromise;
}

// ── Helpers ──────────────────────────────────────────────────────────────

function _formatDate(d: string): string {
  const datePart = d.split(" ")[0];
  const parts = datePart.split("-");
  if (parts.length !== 3) return d;
  const [, m, day] = parts;
  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const monthIdx = parseInt(m, 10) - 1;
  if (monthIdx < 0 || monthIdx > 11) return d;
  return `${parseInt(day, 10)} ${monthNames[monthIdx]}`;
}

// ── Info modal ────────────────────────────────────────────────────────────

function YouFallForInfoModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div className="relative bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-2xl w-[420px] p-5 text-sm" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-3">
          <h4 className="font-bold text-base text-zinc-900 dark:text-zinc-100">Trap Patterns</h4>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-xl leading-none -mt-1">&times;</button>
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 text-xs mb-3">
          Named opening traps detected in your games using the Lichess
          chess-openings database (CC0). Click any row to see how the
          trap unfolds, link to your actual games where it happened,
          and study the line on Lichess.
        </p>
        <ul className="text-xs space-y-1.5 text-zinc-600 dark:text-zinc-400">
          <li><strong>Your Arsenal</strong> — traps you successfully use to win. Keep practising these.</li>
          <li><strong>You Fall For</strong> — traps your opponents have used to beat you. Study how to defend or sidestep them.</li>
        </ul>
        <p className="text-zinc-500 dark:text-zinc-500 text-[10px] mt-3">
          Frequency labels: <strong>Rare</strong> (1-2 games), <strong>Occasional</strong> (3-5 games), <strong>Frequent</strong> (6+ games).
        </p>
      </div>
    </div>,
    document.body
  );
}

// ── Expanded detail view ──────────────────────────────────────────────────

function TrapExpandedView({
  entry,
  player,
  libraryTrap,
}: {
  entry: TrapEntry;
  player: string;
  libraryTrap: LibraryTrap | null;
}) {
  const movesSan = libraryTrap?.moves_san ?? "";
  const nav = useChessNavigation(movesSan, "white");

  return (
    <div className="border-t border-border/50 mt-3 pt-3 px-1 grid grid-cols-1 md:grid-cols-[260px_1fr] gap-4">
      {/* Left: mini-board */}
      <div>
        {libraryTrap ? (
          <>
            <ChessBoard
              position={nav.currentFen}
              orientation={nav.boardOrientation}
              maxWidth={260}
            />
            <MoveControls
              onStart={nav.goToStart}
              onBack={nav.goBack}
              onForward={nav.goForward}
              onEnd={nav.goToEnd}
            />
            <p className="text-[10px] text-muted-foreground text-center mt-1">
              Move {nav.moveIndex + 1} of {nav.totalMoves}
            </p>
          </>
        ) : (
          <p className="text-xs text-muted-foreground italic p-4 text-center border rounded-lg">
            Trap library entry not loaded.
          </p>
        )}
      </div>

      {/* Right: line text + game links + Lichess link */}
      <div className="space-y-3 text-xs">
        {libraryTrap && (
          <div>
            <h5 className="font-semibold text-muted-foreground uppercase tracking-wider text-[10px] mb-1">
              How the trap unfolds
            </h5>
            <p className="font-mono text-[11px] leading-relaxed bg-muted/40 p-2 rounded">
              {libraryTrap.moves_san}
            </p>
          </div>
        )}

        {entry.recent_game_ids && entry.recent_game_ids.length > 0 && (
          <div>
            <h5 className="font-semibold text-muted-foreground uppercase tracking-wider text-[10px] mb-1">
              Recent games where this happened
            </h5>
            <ul className="space-y-1">
              {entry.recent_game_ids.map((gid, i) => {
                const date = entry.recent_dates[i];
                return (
                  <li key={gid}>
                    <Link
                      href={`/${player}/games/${gid}`}
                      className="text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      {date ? _formatDate(date) : `Game #${gid}`} → view full game
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {libraryTrap && (
          <div>
            <a
              href={lichessAnalysisUrl(nav.endFen)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 hover:underline text-[11px]"
            >
              🔍 Study this position on Lichess →
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Single row ────────────────────────────────────────────────────────────

function TrapRow({
  entry,
  variant,
  expanded,
  onToggle,
  player,
  libraryTrap,
}: {
  entry: TrapEntry;
  variant: "arsenal" | "fall";
  expanded: boolean;
  onToggle: () => void;
  player: string;
  libraryTrap: LibraryTrap | null;
}) {
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
      <button
        type="button"
        onClick={onToggle}
        className="w-full text-left flex items-start justify-between gap-3 cursor-pointer group"
        aria-expanded={expanded}
        aria-controls={`trap-detail-${variant}-${entry.name}`}
      >
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium truncate group-hover:underline" title={entry.name}>
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
        <div className="text-right shrink-0 flex items-center gap-2">
          <div>
            <div className={`text-base font-bold ${countColor}`}>{entry.count}×</div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
              {variant === "arsenal" ? `${winPct}% wins` : `${lossPct}% / ${winPct}%`}
            </div>
          </div>
          <span
            className={`text-muted-foreground transition-transform ${expanded ? "rotate-180" : ""}`}
            aria-hidden="true"
          >
            ▾
          </span>
        </div>
      </button>

      {expanded && (
        <div id={`trap-detail-${variant}-${entry.name}`}>
          <TrapExpandedView entry={entry} player={player} libraryTrap={libraryTrap} />
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────

export function YouFallFor({
  arsenal,
  falls,
  player,
}: {
  arsenal?: TrapEntry[];
  falls?: TrapEntry[];
  player: string;
}) {
  const [showInfo, setShowInfo] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null); // composite key: variant|name
  const [library, setLibrary] = useState<LibraryTrap[]>([]);

  useEffect(() => {
    loadTrapLibrary().then(setLibrary);
  }, []);

  const arsenalList = arsenal || [];
  const fallsList = falls || [];
  const empty = arsenalList.length === 0 && fallsList.length === 0;

  // Build a quick lookup by name. Library entries may not match every trap
  // exactly (the matcher uses longest-prefix), so we look up by full name.
  const byName = useMemo(() => {
    const m = new Map<string, LibraryTrap>();
    for (const t of library) m.set(t.name, t);
    return m;
  }, [library]);

  const toggle = (key: string) => {
    setExpanded((cur) => (cur === key ? null : key));
  };

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
        Recurring named opening traps in your games. <strong>Click any row</strong> to
        see how the trap unfolds on a board, jump to the actual games where it
        happened, and study the line on Lichess.
      </p>

      {empty ? (
        <p className="text-sm text-muted-foreground text-center py-6">
          No named trap patterns detected yet. Either you&apos;re avoiding the
          common beginner traps (good!) or there aren&apos;t enough games yet.
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
                {arsenalList.map((entry) => {
                  const key = `arsenal|${entry.name}`;
                  return (
                    <TrapRow
                      key={key}
                      entry={entry}
                      variant="arsenal"
                      expanded={expanded === key}
                      onToggle={() => toggle(key)}
                      player={player}
                      libraryTrap={byName.get(entry.name) || null}
                    />
                  );
                })}
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
                {fallsList.map((entry) => {
                  const key = `fall|${entry.name}`;
                  return (
                    <TrapRow
                      key={key}
                      entry={entry}
                      variant="fall"
                      expanded={expanded === key}
                      onToggle={() => toggle(key)}
                      player={player}
                      libraryTrap={byName.get(entry.name) || null}
                    />
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
