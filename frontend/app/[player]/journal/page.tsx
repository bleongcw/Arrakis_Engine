"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RatingProgressionChart } from "@/components/patterns/rating-progression-chart";
import { DayGroup } from "@/components/journal/day-group";
import { EntryCard } from "@/components/journal/entry-card";
import { AddNoteForm } from "@/components/journal/add-note-form";
import { usePlayerContext } from "@/app/providers";
import {
  fetchJournal,
  fetchGames,
  triggerRecentFormReview,
  type JournalEntry,
} from "@/lib/api";
import { PROVIDERS } from "@/lib/providers";
import { groupEntriesByDay } from "@/lib/journal-grouping";
import type { GameListItem } from "@/lib/types";

/** v1.10.0: Journal foundation — chronological diary of LLM coaching reviews.
 *  v1.11.0: redesigned as a threaded social-media-style feed.
 *
 * Page layout:
 *   - Header + Generate-Review action bar
 *   - Rating-progression timeline chart (reused from Patterns)
 *   - Threaded feed:
 *       Day-group sticky header   ─── Today / Yesterday / etc. ───
 *       │
 *       ● EntryCard (most-recent N expanded, older ones collapsed)
 *       │
 *       ● EntryCard
 *       …
 *
 * The vertical line through the feed is provided by each EntryCard's left
 * border (see entry-card.tsx). The continuous appearance comes from cards
 * stacking without margin between them. Each card has a colored TimelineNode
 * dot that visually sits on the line.
 */

/** How many of the most-recent entries default to expanded. Older ones
 *  collapse to a one-line preview to keep the feed dense as it grows. */
const EXPANDED_HEAD_COUNT = 3;

export default function JournalPage() {
  const { player } = useParams<{ player: string }>();
  const { loading: playerLoading } = usePlayerContext();
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [games, setGames] = useState<GameListItem[]>([]);
  const [platformCounts, setPlatformCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState("openai");
  // v1.11.0: tracks which entry was just freshly generated so EntryCard can
  // pulse + scroll-into-view. Cleared after one render cycle.
  const [pulseEntryId, setPulseEntryId] = useState<number | null>(null);
  // Number of entries before this run — used to detect when a new one arrives
  const entryCountRef = useRef(0);

  const loadJournal = useCallback(() => {
    if (!player) return;
    setLoading(true);
    Promise.all([fetchJournal(player), fetchGames(player)])
      .then(([j, g]) => {
        setEntries(j.entries || []);
        setPlatformCounts(j.platform_counts || {});
        setGames(g || []);
        entryCountRef.current = (j.entries || []).length;
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [player]);

  useEffect(() => {
    loadJournal();
  }, [loadJournal]);

  const handleGenerate = useCallback(
    async (p: string) => {
      if (!player) return;
      setSelectedProvider(p);
      setGenerating(true);
      const oldCount = entryCountRef.current;
      try {
        await triggerRecentFormReview(player, p, 10);
        const poll = setInterval(async () => {
          try {
            const j = await fetchJournal(player);
            if ((j.entries || []).length > oldCount) {
              clearInterval(poll);
              const newEntries = j.entries || [];
              setEntries(newEntries);
              setPlatformCounts(j.platform_counts || {});
              entryCountRef.current = newEntries.length;
              // The newest entry is at index 0 (server orders DESC by created_at)
              setPulseEntryId(newEntries[0]?.id ?? null);
              setGenerating(false);
            }
          } catch {
            // Polling errors swallowed; the safety timeout below ends the wait
          }
        }, 5000);
        // gpt-5.5-pro reasoning can take 2-5 min on this prompt
        setTimeout(() => {
          clearInterval(poll);
          setGenerating(false);
        }, 480000);
      } catch (err) {
        console.error("Failed to trigger journal review:", err);
        setGenerating(false);
      }
    },
    [player],
  );

  if (playerLoading || loading) {
    return <div className="h-96 rounded-lg bg-muted animate-pulse" />;
  }

  const providerSelector = (
    <select
      value={selectedProvider}
      onChange={(e) => setSelectedProvider(e.target.value)}
      disabled={generating}
      className="px-2 py-1.5 rounded-md border text-sm bg-background disabled:opacity-50"
    >
      <optgroup label="Cloud">
        {PROVIDERS.filter((p) => p.group === "cloud").map((p) => (
          <option key={p.slug} value={p.slug}>{p.name}</option>
        ))}
      </optgroup>
      <optgroup label="Local">
        {PROVIDERS.filter((p) => p.group === "local").map((p) => (
          <option key={p.slug} value={p.slug}>{p.name}</option>
        ))}
      </optgroup>
    </select>
  );

  // v1.11.0: group entries by day-bucket for the threaded feed
  const buckets = groupEntriesByDay(entries);

  return (
    <div className="space-y-6">
      {/* Header + action bar */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-semibold">📖 Journal</h1>
          <p className="text-sm text-muted-foreground">
            Chronological coaching diary. Each review is preserved — generate a
            new one whenever you want a fresh take on the last 10 games.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {providerSelector}
          <Button
            size="sm"
            disabled={generating}
            onClick={() => handleGenerate(selectedProvider)}
          >
            {generating ? "Generating…" : "Generate Review"}
          </Button>
          {/* v1.12.0: parent note action, equal weight to Generate Review.
              Toggles into an inline form on click. */}
          {player && (
            <AddNoteForm
              player={player}
              onCreated={(entry) => {
                // Same pattern as a freshly-generated review:
                // refetch the feed and pulse-highlight the new entry
                setPulseEntryId(entry.id);
                loadJournal();
              }}
            />
          )}
        </div>
      </div>
      {generating && (
        <p className="text-xs text-muted-foreground animate-pulse -mt-3">
          This may take 2–5 minutes for reasoning models. New entry will appear
          at the top when ready.
        </p>
      )}

      {/* Timeline — reuses the Patterns rating-progression chart. */}
      {games.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Rating timeline</CardTitle>
          </CardHeader>
          <CardContent>
            <RatingProgressionChart games={games} />
          </CardContent>
        </Card>
      )}

      {/* Threaded entry feed — empty state vs grouped feed */}
      {entries.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center space-y-3">
            <p className="text-sm text-muted-foreground">
              No journal entries yet. Generate your first review across the
              last 10 coached games — the coach will name specific games,
              identify through-lines, and give one forward mission.
            </p>
            <div className="flex justify-center items-center gap-2">
              {providerSelector}
              <Button
                size="sm"
                disabled={generating}
                onClick={() => handleGenerate(selectedProvider)}
              >
                {generating ? "Generating…" : "Generate Your First Review"}
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {buckets.map((bucket) => (
            <DayGroup
              key={bucket.label}
              label={bucket.label}
              count={bucket.entries.length}
            >
              {bucket.entries.map((e, indexInBucket) => {
                // Determine if this entry should default to expanded.
                // We expand the most-recent EXPANDED_HEAD_COUNT entries
                // ACROSS the feed (not per-bucket), so older entries collapse
                // to a preview even if they fall in a fresh bucket.
                const globalIndex = entries.indexOf(e);
                return (
                  <EntryCard
                    key={e.id}
                    entry={e}
                    player={player}
                    games={games}
                    defaultExpanded={globalIndex < EXPANDED_HEAD_COUNT}
                    pulseOnMount={e.id === pulseEntryId}
                    // v1.12.0: refetch feed after a note is edited/deleted
                    onChanged={loadJournal}
                  />
                );
              })}
            </DayGroup>
          ))}
        </div>
      )}

      {/* Footer hint — multi-platform chip filter is the v1.12.0 / v1.13.0 ask */}
      {Object.keys(platformCounts).length > 1 && (
        <p className="text-xs text-muted-foreground text-center pt-2">
          You have entries across {Object.keys(platformCounts).length} platforms
          ({Object.entries(platformCounts).map(([p, n]) => `${p}: ${n}`).join(", ")}).
          A platform filter is coming in a future release.
        </p>
      )}
    </div>
  );
}
