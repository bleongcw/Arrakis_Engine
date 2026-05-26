"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RatingProgressionChart } from "@/components/patterns/rating-progression-chart";
import { usePlayerContext } from "@/app/providers";
import {
  fetchJournal,
  fetchGames,
  triggerRecentFormReview,
  type JournalEntry,
} from "@/lib/api";
import { PROVIDERS } from "@/lib/providers";
import { parseTrendSummary } from "@/lib/summary";
import type { GameListItem } from "@/lib/types";

/** v1.10.0: Journal page — chronological diary of LLM coaching reviews.
 *
 * - Top: rating-progression timeline (reuses the Patterns chart).
 * - Below: entry feed, newest first. Each entry shows the 4-paragraph
 *   review, the platform it covers, the model that wrote it, and clickable
 *   referenced-game pills that jump to that game's detail page.
 * - Action bar: provider selector + "Generate Review" button creates a new
 *   entry (does NOT replace the previous one — entries accumulate).
 *
 * Forward-compat for v1.10.1 / v1.11.0:
 * - `journal_entries.platform` is already populated per-row. v1.10.1 will add
 *   a chip-row platform filter at the top; the backend already supports it.
 * - `journal_entries.kind` distinguishes review vs note vs tournament_game.
 *   v1.10.1 adds parent notes; v1.11.0 adds tournament games via photo OCR.
 */
export default function JournalPage() {
  const { player } = useParams<{ player: string }>();
  const { loading: playerLoading } = usePlayerContext();
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [games, setGames] = useState<GameListItem[]>([]);
  const [platformCounts, setPlatformCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState("openai");
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
        // Poll for the new entry to land in the journal
        const poll = setInterval(async () => {
          try {
            const j = await fetchJournal(player);
            if ((j.entries || []).length > oldCount) {
              clearInterval(poll);
              setEntries(j.entries);
              setPlatformCounts(j.platform_counts || {});
              entryCountRef.current = j.entries.length;
              setGenerating(false);
            }
          } catch {
            // swallow polling errors — the safety timeout below ends the wait
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
        <div className="flex items-center gap-2">
          {providerSelector}
          <Button
            size="sm"
            disabled={generating}
            onClick={() => handleGenerate(selectedProvider)}
          >
            {generating ? "Generating…" : "Generate Review"}
          </Button>
        </div>
      </div>
      {generating && (
        <p className="text-xs text-muted-foreground animate-pulse -mt-3">
          This may take 2–5 minutes for reasoning models. New entry will appear
          at the top when ready.
        </p>
      )}

      {/* Timeline — reuses the Patterns rating-progression chart. The chart
          owns its own platform / time-class controls (v1.7.2 / v1.7.3).
          v1.10.1 will add an annotation-dots overlay so journal entries
          appear as markers on the rating line. */}
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

      {/* Entry feed */}
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
        <div className="space-y-4">
          {entries.map((e) => (
            <EntryCard key={e.id} entry={e} player={player} games={games} />
          ))}
        </div>
      )}

      {/* Footer hint for v1.10.1+ */}
      {Object.keys(platformCounts).length > 1 && (
        <p className="text-xs text-muted-foreground text-center pt-2">
          You have entries across {Object.keys(platformCounts).length} platforms
          ({Object.entries(platformCounts).map(([p, n]) => `${p}: ${n}`).join(", ")}).
          A platform filter is coming in v1.10.1.
        </p>
      )}
    </div>
  );
}

function EntryCard({
  entry,
  player,
  games,
}: {
  entry: JournalEntry;
  player: string;
  games: GameListItem[];
}) {
  const paragraphs = parseTrendSummary(entry.body || "");

  // Format created_at as a friendly date + relative age
  const created = new Date(entry.created_at);
  const dateStr = created.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
  const ageMs = Date.now() - created.getTime();
  const ageDays = Math.floor(ageMs / (1000 * 60 * 60 * 24));
  const relative = ageDays === 0 ? "today" : ageDays === 1 ? "yesterday" : `${ageDays} days ago`;

  // Resolve referenced game IDs → list items so we can render pills with links
  const refGames = (entry.refs || [])
    .map((id) => games.find((g) => g.id === id))
    .filter((g): g is GameListItem => Boolean(g));

  const kindIcon = entry.kind === "review" ? "📖" : entry.kind === "note" ? "📝" : "🏆";
  const kindLabel = entry.kind === "review"
    ? "Review"
    : entry.kind === "note"
    ? "Note"
    : entry.kind.replace(/_/g, " ");

  return (
    <Card className="border-l-4 border-l-emerald-500">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2 flex-wrap">
          <span>{kindIcon} {kindLabel}</span>
          <span className="text-xs font-normal text-muted-foreground">
            · {dateStr} ({relative})
          </span>
          <span className="text-[10px] font-normal px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
            {entry.platform}
          </span>
          {entry.provider && (
            <span className="text-[10px] font-normal px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
              {entry.provider.split(":")[1] || entry.provider}
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {paragraphs.map((p, i) => (
            <p key={i} className="text-sm leading-relaxed whitespace-pre-wrap">{p}</p>
          ))}
          {refGames.length > 0 && (
            <div className="pt-2 flex items-center gap-1.5 flex-wrap">
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
      </CardContent>
    </Card>
  );
}
