"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import {
  type JournalEntry,
  updateJournalNote,
  deleteJournalNote,
} from "@/lib/api";
import type { GameListItem } from "@/lib/types";
import { parseTrendSummary } from "@/lib/summary";
import { useLiveRelativeTime } from "@/lib/relative-time";
import { Button } from "@/components/ui/button";
import { TimelineNode } from "./timeline-thread";

/** v1.11.0: A single Journal entry card on the threaded feed.
 *  v1.12.0: notes (kind='note') gain inline edit + delete actions.
 *
 * Visual:
 *   - Left border (2px, muted) provides the timeline rail
 *   - Colored TimelineNode dot sits on the rail at the card's date line
 *   - Header: kind icon · live-updating relative timestamp · platform + model badges
 *   - Body: review paragraphs (expandable) or note body
 *   - Footer: clickable referenced-game pills
 *
 * Behavior:
 *   - `defaultExpanded=true` (latest entries) → full body shown
 *   - `defaultExpanded=false` (older entries) → one-line preview, click to expand
 *   - `pulseOnMount=true` → 2-second emerald glow + scroll-into-view, used when
 *     a freshly-generated entry lands during the user's session
 *   - For `kind='note'`, a ⋯ menu shows Edit / Delete (v1.12.0)
 */

const MAX_NOTE_BODY_LEN = 4000; // mirrors src/journal.py

const KIND_ICONS: Record<string, string> = {
  review: "📖",
  note: "📝",
};

const KIND_LABELS: Record<string, string> = {
  review: "Review",
  note: "Note",
};

export interface EntryCardProps {
  entry: JournalEntry;
  player: string;
  games: GameListItem[];
  defaultExpanded?: boolean;
  pulseOnMount?: boolean;
  /** v1.12.0: called after the user edits or deletes a note so the parent
   *  can refetch the feed. No-op for review entries (those are immutable). */
  onChanged?: () => void;
}

export function EntryCard({
  entry,
  player,
  games,
  defaultExpanded = true,
  pulseOnMount = false,
  onChanged,
}: EntryCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [pulsing, setPulsing] = useState(pulseOnMount);
  const ref = useRef<HTMLElement | null>(null);
  // v1.12.0: note edit + delete state
  const [editing, setEditing] = useState(false);
  const [editBody, setEditBody] = useState(entry.body || "");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const isNote = entry.kind === "note";

  const startEdit = useCallback(() => {
    setEditBody(entry.body || "");
    setActionError(null);
    setEditing(true);
  }, [entry.body]);

  const cancelEdit = useCallback(() => {
    setEditing(false);
    setEditBody(entry.body || "");
    setActionError(null);
  }, [entry.body]);

  const saveEdit = useCallback(async () => {
    const trimmed = editBody.trim();
    if (!trimmed || trimmed.length > MAX_NOTE_BODY_LEN) return;
    setBusy(true);
    setActionError(null);
    try {
      await updateJournalNote(entry.id, trimmed);
      setEditing(false);
      onChanged?.();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to update note");
    } finally {
      setBusy(false);
    }
  }, [editBody, entry.id, onChanged]);

  const handleDelete = useCallback(async () => {
    if (!isNote) return;
    if (!window.confirm("Delete this note? This cannot be undone.")) return;
    setBusy(true);
    setActionError(null);
    try {
      await deleteJournalNote(entry.id);
      onChanged?.();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to delete note");
      setBusy(false);
    }
  }, [isNote, entry.id, onChanged]);

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
        {/* v1.12.0: edit/delete actions for notes only. Reviews stay
            immutable — the "⋯" affordance is only rendered for kind='note'. */}
        {isNote && !editing && (
          <div className="ml-auto flex items-center gap-1">
            <button
              type="button"
              onClick={startEdit}
              disabled={busy}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Edit note"
              title="Edit note"
            >
              Edit
            </button>
            <span className="text-muted-foreground/40 text-xs">·</span>
            <button
              type="button"
              onClick={handleDelete}
              disabled={busy}
              className="text-xs text-muted-foreground hover:text-red-600 dark:hover:text-red-400 transition-colors"
              aria-label="Delete note"
              title="Delete note"
            >
              Delete
            </button>
          </div>
        )}
        {!expanded && !editing && (
          <button
            type="button"
            onClick={() => setExpanded(true)}
            className="ml-auto text-xs text-muted-foreground hover:text-foreground"
          >
            expand ↓
          </button>
        )}
      </header>

      {/* v1.12.0: inline edit mode for notes */}
      {editing ? (
        <div className="space-y-2 pt-1 pb-3">
          <textarea
            value={editBody}
            onChange={(e) => setEditBody(e.target.value)}
            rows={4}
            className="w-full min-h-[5rem] p-2 rounded-md border bg-background text-sm
                       focus:outline-none focus:ring-2 focus:ring-blue-500/40 resize-y"
            disabled={busy}
            autoFocus
            aria-label="Edit note body"
          />
          {actionError && (
            <p className="text-xs text-red-600 dark:text-red-400">{actionError}</p>
          )}
          <div className="flex items-center justify-end gap-2">
            <span className="text-[10px] text-muted-foreground mr-auto">
              {editBody.length} / {MAX_NOTE_BODY_LEN}
            </span>
            <Button size="sm" variant="ghost" onClick={cancelEdit} disabled={busy}>
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={saveEdit}
              disabled={
                busy ||
                editBody.trim().length === 0 ||
                editBody.length > MAX_NOTE_BODY_LEN
              }
            >
              {busy ? "Saving…" : "Save"}
            </Button>
          </div>
        </div>
      ) : expanded ? (
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
          {actionError && (
            <p className="text-xs text-red-600 dark:text-red-400">{actionError}</p>
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
