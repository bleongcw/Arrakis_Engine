"use client";

import { useState, useEffect, useMemo } from "react";
import { ChessBoard } from "@/components/game-detail/chess-board";
import { MoveControls } from "@/components/game-detail/move-controls";
import { useChessNavigation } from "@/hooks/use-chess-navigation";
import { parseMoveText } from "@/lib/chess/pgn";
import {
  findCanonicalLine,
  findDeviationIndex,
  type LibraryOpening,
} from "@/lib/chess/openings";
import { lichessAnalysisUrl } from "@/lib/chess/lichess";
import type {
  OpponentProfile,
  OpponentOpeningEntry,
  OpponentRepresentativeGame,
} from "@/lib/types";

// ── Opening library — fetched once for canonical-line lookup + deviation
//    highlighting. Cached at module scope for the lifetime of the page.

let _libraryCache: LibraryOpening[] | null = null;
let _libraryPromise: Promise<LibraryOpening[]> | null = null;

function loadOpeningLibrary(): Promise<LibraryOpening[]> {
  if (_libraryCache) return Promise.resolve(_libraryCache);
  if (_libraryPromise) return _libraryPromise;
  _libraryPromise = fetch("/data/openings.json")
    .then((r) => r.json() as Promise<LibraryOpening[]>)
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

function _formatDate(d: string | null): string {
  if (!d) return "—";
  const datePart = d.split(" ")[0];
  const parts = datePart.split("-");
  if (parts.length !== 3) return d;
  const [y, m, day] = parts;
  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const monthIdx = parseInt(m, 10) - 1;
  if (monthIdx < 0 || monthIdx > 11) return d;
  return `${parseInt(day, 10)} ${monthNames[monthIdx]} ${y}`;
}

// ── Annotated move list with deviation highlight ─────────────────────────

function AnnotatedMoves({
  gameMoves,
  canonical,
}: {
  /** The actual SAN moves from the game, already parsed by chess.js (via
   *  useChessNavigation in the parent). Pre-parsed because chess.com PGNs
   *  contain clock annotations like `{[%clk 0:09:55]}` that broke the
   *  earlier regex parser; chess.js handles them correctly. */
  gameMoves: string[];
  canonical: LibraryOpening | null;
}) {
  const bookMoves = useMemo(
    () => (canonical ? parseMoveText(canonical.moves) : []),
    [canonical],
  );

  const deviationIdx = useMemo(
    () => (bookMoves.length > 0 ? findDeviationIndex(gameMoves, bookMoves) : -1),
    [gameMoves, bookMoves],
  );

  // Cap displayed moves to keep the panel readable. Show enough to cover
  // the deviation point + a few more, max 24 plies (~12 moves).
  const cap = Math.min(gameMoves.length, Math.max(deviationIdx + 6, 16));
  const visible = gameMoves.slice(0, cap);

  const parts: React.ReactNode[] = [];
  let moveNum = 1;
  for (let i = 0; i < visible.length; i++) {
    const isWhiteMove = i % 2 === 0;
    if (isWhiteMove) {
      parts.push(
        <span key={`num-${moveNum}`} className="text-muted-foreground">
          {moveNum}.
        </span>,
      );
    }
    const inBook = i < bookMoves.length && visible[i] === bookMoves[i];
    const isDeviation = deviationIdx >= 0 && i === deviationIdx;
    parts.push(
      <span
        key={`m-${i}`}
        className={
          isDeviation
            ? "text-orange-500 font-bold"
            : inBook
              ? "text-emerald-600 dark:text-emerald-400"
              : ""
        }
        title={
          isDeviation && i < bookMoves.length
            ? `Deviation — book move was ${bookMoves[i]}`
            : inBook
              ? "Book move"
              : undefined
        }
      >
        {isDeviation && (
          <span className="text-orange-400 text-[10px] align-super mr-0.5">!</span>
        )}
        {inBook && (
          <span className="text-emerald-400 text-[10px] align-super mr-0.5">{"✓"}</span>
        )}
        {visible[i]}
      </span>,
    );
    parts.push(<span key={`s-${i}`}> </span>);
    if (!isWhiteMove) moveNum++;
  }

  return (
    <div className="text-[11px] font-mono leading-relaxed bg-muted/40 p-2 rounded">
      {parts}
      {gameMoves.length > cap && (
        <span className="text-muted-foreground"> …</span>
      )}
      {deviationIdx >= 0 && deviationIdx < bookMoves.length && (
        <p className="text-[10px] text-orange-500 mt-1 font-sans">
          Deviation at move {Math.floor(deviationIdx / 2) + 1}: opponent
          played <span className="font-mono font-bold">{gameMoves[deviationIdx]}</span>
          , book is <span className="font-mono font-bold">{bookMoves[deviationIdx]}</span>
        </p>
      )}
    </div>
  );
}

// ── Expanded view: mini-board + game flip + annotated moves + Lichess ──

function OpeningExpandedView({
  entry,
  library,
}: {
  entry: OpponentOpeningEntry;
  library: LibraryOpening[];
}) {
  const reps = entry.representative_games || [];
  const [repIdx, setRepIdx] = useState(0);
  // Reset rep index whenever the entry identity changes (e.g. user toggles
  // White/Black tab and a different opening enters this row's slot).
  useEffect(() => {
    setRepIdx(0);
  }, [entry.name, entry.eco, reps.length]);

  // Choose what to render on the board: actual rep PGN if available,
  // else canonical line as a fallback.
  const canonical = useMemo(
    () => findCanonicalLine(entry.name, library),
    [entry.name, library],
  );
  const currentRep: OpponentRepresentativeGame | null =
    reps[repIdx] ?? null;
  const fallbackPgn = canonical?.moves ?? "";
  const boardPgn = currentRep?.pgn ?? fallbackPgn;
  const orientation = (currentRep?.opponent_color as "white" | "black") || "white";
  const nav = useChessNavigation(boardPgn, orientation);

  if (!boardPgn) {
    return (
      <div className="border-t border-border/50 mt-3 pt-3">
        <p className="text-xs text-muted-foreground italic">
          No game data available for this opening.
        </p>
      </div>
    );
  }

  return (
    <div className="border-t border-border/50 mt-3 pt-3 px-1 grid grid-cols-1 md:grid-cols-[260px_1fr] gap-4">
      {/* Left: mini-board */}
      <div>
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
      </div>

      {/* Right: game flip + annotated moves + Lichess link */}
      <div className="space-y-3 text-xs">
        {/* Game flip controls — only when we have actual rep games */}
        {reps.length > 0 && (
          <div>
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
                Game {repIdx + 1} of {reps.length}
              </span>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setRepIdx((i) => Math.max(0, i - 1))}
                  disabled={repIdx === 0}
                  className="px-2 py-0.5 text-[11px] rounded border bg-background disabled:opacity-40"
                  aria-label="Previous representative game"
                >
                  ← Prev
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setRepIdx((i) => Math.min(reps.length - 1, i + 1))
                  }
                  disabled={repIdx >= reps.length - 1}
                  className="px-2 py-0.5 text-[11px] rounded border bg-background disabled:opacity-40"
                  aria-label="Next representative game"
                >
                  Next →
                </button>
              </div>
            </div>
            {currentRep && (
              <p className="text-[10px] text-muted-foreground">
                {_formatDate(currentRep.date_played)}
                {currentRep.opponent_color
                  ? ` · opponent played ${currentRep.opponent_color}`
                  : ""}
                {currentRep.game_url && (
                  <>
                    {" · "}
                    <a
                      href={currentRep.game_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      view source ↗
                    </a>
                  </>
                )}
              </p>
            )}
          </div>
        )}

        {/* Annotated move list with deviation highlight */}
        <div>
          <h5 className="font-semibold text-muted-foreground uppercase tracking-wider text-[10px] mb-1">
            {reps.length > 0 ? "How the game went" : "Canonical line (no game data)"}
          </h5>
          <AnnotatedMoves gameMoves={nav.moves} canonical={canonical} />
          {reps.length === 0 && (
            <p className="text-[10px] text-muted-foreground mt-1 italic">
              Refresh this profile to fetch actual games for this opening.
            </p>
          )}
        </div>

        {/* Lichess link */}
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
      </div>
    </div>
  );
}

// ── Single row ────────────────────────────────────────────────────────────

function OpeningRow({
  entry,
  variant,
  expanded,
  onToggle,
  library,
}: {
  entry: OpponentOpeningEntry;
  variant: "weakness" | "strength";
  expanded: boolean;
  onToggle: () => void;
  library: LibraryOpening[];
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
      <button
        type="button"
        onClick={onToggle}
        className="w-full text-left flex items-start justify-between gap-3 cursor-pointer group"
        aria-expanded={expanded}
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
          <div className="text-xs text-muted-foreground mt-0.5">
            {entry.total} game{entry.total === 1 ? "" : "s"}
            {variant === "weakness"
              ? ` · ${entry.losses}L / ${entry.wins}W / ${entry.draws}D`
              : ` · ${entry.wins}W / ${entry.losses}L / ${entry.draws}D`}
          </div>
        </div>
        <div className="text-right shrink-0 flex items-center gap-2">
          <div>
            <div className={`text-lg font-bold ${colorClass}`}>{entry.rate}%</div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
              {label}
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
      <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden mt-2">
        <div
          className={`h-full ${barClass} transition-all duration-500`}
          style={{ width: `${Math.min(entry.rate, 100)}%` }}
        />
      </div>
      {expanded && <OpeningExpandedView entry={entry} library={library} />}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────

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
  const [expanded, setExpanded] = useState<string | null>(null);
  const [library, setLibrary] = useState<LibraryOpening[]>([]);

  useEffect(() => {
    loadOpeningLibrary().then(setLibrary);
  }, []);

  // Reset expansion whenever the player switches White/Black tabs so
  // a click in one tab doesn't appear "open" in the other.
  useEffect(() => {
    setExpanded(null);
  }, [color]);

  const weaknesses = profile.weaknesses[color] || [];
  const strengths = profile.strengths[color] || [];
  const empty = weaknesses.length === 0 && strengths.length === 0;
  const hasGames = profile.total_games > 0;
  const accumulated = profile.meta.accumulated_games;

  const toggle = (key: string) => {
    setExpanded((cur) => (cur === key ? null : key));
  };

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
              {typeof accumulated === "number" && accumulated !== profile.total_games && (
                <span className="ml-2 text-[10px] uppercase tracking-wider">
                  ({accumulated} accumulated)
                </span>
              )}
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
          <strong>{profile.meta.platform}</strong> in the lookback window.
          Check the username spelling and platform, then try again.
        </p>
      ) : empty ? (
        <p className="text-sm text-muted-foreground text-center py-6">
          {profile.meta.username} has played as {color} but no opening
          appears in 2+ games yet — try the other color.
        </p>
      ) : (
        <>
          <p className="text-xs text-muted-foreground -mt-1">
            <strong>Click any row</strong> to see how the opponent played the line —
            actual games (not just averages), with deviations from book theory
            highlighted in orange.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Weaknesses */}
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
                  {weaknesses.map((entry) => {
                    const key = `weakness|${entry.name}`;
                    return (
                      <OpeningRow
                        key={key}
                        entry={entry}
                        variant="weakness"
                        expanded={expanded === key}
                        onToggle={() => toggle(key)}
                        library={library}
                      />
                    );
                  })}
                </div>
              )}
            </div>

            {/* Strengths */}
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
                  {strengths.map((entry) => {
                    const key = `strength|${entry.name}`;
                    return (
                      <OpeningRow
                        key={key}
                        entry={entry}
                        variant="strength"
                        expanded={expanded === key}
                        onToggle={() => toggle(key)}
                        library={library}
                      />
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
