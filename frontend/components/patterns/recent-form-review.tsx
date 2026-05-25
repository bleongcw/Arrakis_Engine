"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { triggerRecentFormReview, fetchPatterns } from "@/lib/api";
import { PROVIDERS } from "@/lib/providers";
import { parseTrendSummary } from "@/lib/summary";

/** v1.9.0: Recent Form Review — LLM narrative across the last N coached games.
 *
 * Distinct from <TrendSummary> (which is a stats aggregate over 30 days).
 * This card names specific games by date + opponent + result, identifies
 * cross-game through-lines, and gives forward guidance. Pairs the v1.7.0
 * coaching-history mechanism with the v1.8.0 trajectory snapshot to write
 * a coherent "last 10 games" review.
 */

function RecentFormReviewInfoModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div
        className="relative bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-2xl w-[380px] p-5 text-sm"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start mb-3">
          <h4 className="font-bold text-base text-zinc-900 dark:text-zinc-100">Recent Form Review</h4>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-xl leading-none -mt-1"
          >&times;</button>
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 text-xs mb-3">
          A coaching narrative across the player&apos;s last 10 coached games. Different from the
          stats-based Coaching Summary below — this one names specific games and identifies
          through-lines.
        </p>
        <ul className="text-xs space-y-1.5 text-zinc-600 dark:text-zinc-400">
          <li><strong>The arc</strong> — recent record and what kind of week it was</li>
          <li><strong>Standout games</strong> — 2–3 specific games by date and opponent</li>
          <li><strong>What&apos;s working / not</strong> — tied to measured trajectory</li>
          <li><strong>Forward guidance</strong> — one coaching mission for the next 10 games</li>
        </ul>
        <p className="text-zinc-500 dark:text-zinc-500 text-[10px] mt-3">
          Generated on demand. Click Regenerate after coaching new games.
        </p>
      </div>
    </div>,
    document.body,
  );
}

interface RecentFormReviewProps {
  review: string | null | undefined;
  updatedAt: string | null | undefined;
  player: string;
  onReviewGenerated: () => void;
}

export function RecentFormReview({
  review,
  updatedAt,
  player,
  onReviewGenerated,
}: RecentFormReviewProps) {
  const [generating, setGenerating] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState("openai");
  const [showInfo, setShowInfo] = useState(false);
  const previousReviewRef = useRef(review);

  const handleGenerate = useCallback(
    async (p: string) => {
      setSelectedProvider(p);
      setGenerating(true);
      const oldReview = previousReviewRef.current;
      try {
        await triggerRecentFormReview(player, p, 10);
        const poll = setInterval(async () => {
          try {
            const data = await fetchPatterns(player);
            if (data.recent_form_review && data.recent_form_review !== oldReview) {
              clearInterval(poll);
              previousReviewRef.current = data.recent_form_review;
              setGenerating(false);
              onReviewGenerated();
            }
          } catch {
            // Swallow polling errors — next tick will retry. Final timeout
            // below provides the escape hatch if the LLM is slow or fails.
          }
        }, 5000);
        // Safety timeout — gpt-5.5-pro reasoning can run 2–5 min on this prompt;
        // give it 8 min before giving up.
        setTimeout(() => {
          clearInterval(poll);
          setGenerating(false);
        }, 480000);
      } catch (err) {
        console.error("Failed to trigger recent form review:", err);
        setGenerating(false);
      }
    },
    [player, onReviewGenerated],
  );

  const paragraphs = parseTrendSummary(review);

  // Freshness stamp — show how old the review is so user knows when to refresh
  let freshnessStamp: string | null = null;
  if (updatedAt) {
    try {
      const updated = new Date(updatedAt);
      const ageMs = Date.now() - updated.getTime();
      const ageDays = Math.floor(ageMs / (1000 * 60 * 60 * 24));
      freshnessStamp = ageDays === 0
        ? "today"
        : ageDays === 1
        ? "yesterday"
        : `${ageDays} days ago`;
    } catch {
      // ignore
    }
  }

  const providerSelector = (
    <div className="flex items-center gap-2">
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
    </div>
  );

  return (
    <Card className="border-l-4 border-l-emerald-500">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2 flex-wrap">
          <span>📖 Recent Form Review</span>
          <span className="text-[10px] font-normal text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
            last 10 games
          </span>
          {freshnessStamp && (
            <span
              className="text-[10px] font-normal text-muted-foreground"
              title={`Last refreshed ${updatedAt}`}
            >
              · refreshed {freshnessStamp}
            </span>
          )}
          <button
            onClick={() => setShowInfo(true)}
            className="text-sm font-normal text-muted-foreground hover:text-foreground cursor-help select-none transition-colors ml-1"
            title="What is the Recent Form Review?"
          >&#9432;</button>
        </CardTitle>
      </CardHeader>
      {showInfo && <RecentFormReviewInfoModal onClose={() => setShowInfo(false)} />}
      <CardContent>
        {review ? (
          <div className="space-y-3">
            {paragraphs.map((paragraph, i) => (
              <p key={i} className="text-sm leading-relaxed">{paragraph}</p>
            ))}
            <div className="pt-2 flex items-center gap-2">
              {providerSelector}
              <Button
                variant="outline"
                size="sm"
                disabled={generating}
                onClick={() => handleGenerate(selectedProvider)}
              >
                {generating ? "Regenerating…" : "Regenerate"}
              </Button>
            </div>
            {generating && (
              <p className="text-xs text-muted-foreground animate-pulse">
                This may take 2–5 minutes for reasoning models…
              </p>
            )}
          </div>
        ) : (
          <div className="text-center py-6 space-y-3">
            <p className="text-sm text-muted-foreground">
              Generate an AI review across your last 10 coached games. Names specific games,
              identifies through-lines, and gives forward guidance.
            </p>
            <div className="flex justify-center items-center gap-2">
              {providerSelector}
              <Button
                size="sm"
                disabled={generating}
                onClick={() => handleGenerate(selectedProvider)}
              >
                {generating ? "Generating…" : "Generate Review"}
              </Button>
            </div>
            {generating && (
              <p className="text-xs text-muted-foreground animate-pulse">
                This may take 2–5 minutes for reasoning models…
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
