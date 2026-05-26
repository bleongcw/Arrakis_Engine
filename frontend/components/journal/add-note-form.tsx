"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { createJournalNote, type JournalEntry } from "@/lib/api";

/** v1.12.0: Inline form for adding a parent-authored note to the Journal.
 *
 * UX choices:
 *   - Inline (not modal) so it doesn't fight with the sticky day-group
 *     headers and stays in the flow of the page.
 *   - "Add Note" button toggles the form open; auto-focuses the textarea.
 *   - 4000 character soft limit (matches src/journal.py::MAX_NOTE_BODY_LEN);
 *     live character counter; submit disabled at 0 or over the limit.
 *   - Cmd/Ctrl+Enter submits.
 *   - On success: form clears + closes + calls onCreated so the page
 *     refetches and the new entry pulses into view.
 */

const MAX_BODY_LEN = 4000;

export interface AddNoteFormProps {
  player: string;
  /** Default platform tag for the new note. Inherited from the page's
   *  current scope; user doesn't pick this in v1.12.0. */
  defaultPlatform?: string;
  /** Called with the created entry so the parent can refetch + pulse it. */
  onCreated: (entry: JournalEntry) => void;
}

export function AddNoteForm({
  player,
  defaultPlatform = "chess.com",
  onCreated,
}: AddNoteFormProps) {
  const [open, setOpen] = useState(false);
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Focus the textarea when the form opens
  useEffect(() => {
    if (open && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [open]);

  const trimmed = body.trim();
  const canSubmit = trimmed.length > 0 && trimmed.length <= MAX_BODY_LEN && !submitting;
  const overLimit = body.length > MAX_BODY_LEN;

  const reset = useCallback(() => {
    setBody("");
    setError(null);
    setOpen(false);
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const { entry } = await createJournalNote(player, trimmed, defaultPlatform);
      reset();
      onCreated(entry);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create note");
    } finally {
      setSubmitting(false);
    }
  }, [canSubmit, player, trimmed, defaultPlatform, onCreated, reset]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Cmd+Enter / Ctrl+Enter submits
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        handleSubmit();
      } else if (e.key === "Escape") {
        e.preventDefault();
        reset();
      }
    },
    [handleSubmit, reset],
  );

  if (!open) {
    return (
      <Button
        size="sm"
        variant="outline"
        onClick={() => setOpen(true)}
      >
        📝 Add Note
      </Button>
    );
  }

  return (
    <Card className="border-l-4 border-l-blue-500 w-full">
      <CardContent className="pt-4 space-y-2">
        <div className="text-xs text-muted-foreground flex items-center justify-between">
          <span>📝 New note · {defaultPlatform}</span>
          <button
            type="button"
            onClick={reset}
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Cancel"
          >
            ×
          </button>
        </div>
        <textarea
          ref={textareaRef}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={4}
          placeholder="What happened? e.g. 'Round 3 of the Saturday tournament — Evan beat Sarah 4-0!'"
          className="w-full min-h-[6rem] p-2 rounded-md border bg-background text-sm
                     focus:outline-none focus:ring-2 focus:ring-blue-500/40 resize-y"
          disabled={submitting}
          aria-label="Note body"
        />
        {error && (
          <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
        )}
        <div className="flex items-center justify-between gap-2">
          <span
            className={
              "text-[10px] " +
              (overLimit
                ? "text-red-600 dark:text-red-400 font-medium"
                : "text-muted-foreground")
            }
          >
            {body.length} / {MAX_BODY_LEN}
            <span className="ml-2 opacity-60 hidden sm:inline">⌘+Enter to post</span>
          </span>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="ghost"
              onClick={reset}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleSubmit}
              disabled={!canSubmit}
            >
              {submitting ? "Posting…" : "Post note"}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
