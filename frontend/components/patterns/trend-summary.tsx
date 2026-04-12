"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { triggerTrendSummary, fetchPatterns } from "@/lib/api";
import { PROVIDERS } from "@/lib/providers";

function CoachingSummaryInfoModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div className="relative bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-2xl w-[340px] p-5 text-sm" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-3">
          <h4 className="font-bold text-base text-zinc-900 dark:text-zinc-100">Coaching Summary</h4>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 text-xl leading-none -mt-1">&times;</button>
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 text-xs mb-3">
          An AI coach analyzes all your pattern data and writes a personalized summary.
        </p>
        <ul className="text-xs space-y-1.5 text-zinc-600 dark:text-zinc-400">
          <li><strong>Accuracy &amp; ACPL</strong> — How precise your moves are overall</li>
          <li><strong>Openings</strong> — Which openings you play and how well</li>
          <li><strong>Time management</strong> — Whether you rush or use time well</li>
          <li><strong>Blunder patterns</strong> — When and where mistakes happen</li>
        </ul>
        <p className="text-zinc-500 dark:text-zinc-500 text-[10px] mt-3">
          The summary highlights strengths, weaknesses, and what to work on next.
        </p>
      </div>
    </div>,
    document.body
  );
}

interface TrendSummaryProps {
  summary: string | null | undefined;
  player: string;
  onSummaryGenerated: () => void;
}

export function TrendSummary({ summary, player, onSummaryGenerated }: TrendSummaryProps) {
  const [generating, setGenerating] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState("openai");
  const [showInfo, setShowInfo] = useState(false);
  const previousSummaryRef = useRef(summary);

  const handleGenerate = useCallback(async (p: string) => {
    setSelectedProvider(p);
    setGenerating(true);
    const oldSummary = previousSummaryRef.current;
    try {
      await triggerTrendSummary(player, p);
      const poll = setInterval(async () => {
        try {
          const data = await fetchPatterns(player);
          if (data.trend_summary && data.trend_summary !== oldSummary) {
            clearInterval(poll);
            previousSummaryRef.current = data.trend_summary;
            setGenerating(false);
            onSummaryGenerated();
          }
        } catch {}
      }, 5000);
      setTimeout(() => {
        clearInterval(poll);
        setGenerating(false);
      }, 300000);
    } catch (err) {
      console.error("Failed to trigger trend summary:", err);
      setGenerating(false);
    }
  }, [player, onSummaryGenerated]);

  // Parse summary: handle both plain text and JSON {"paragraphs": [...]} format
  const paragraphs: string[] = (() => {
    if (!summary) return [];
    const trimmed = summary.trim();
    if (trimmed.startsWith("{")) {
      try {
        const parsed = JSON.parse(trimmed);
        if (Array.isArray(parsed.paragraphs)) return parsed.paragraphs;
        if (typeof parsed === "object") return Object.values(parsed).flat().filter((v): v is string => typeof v === "string");
      } catch {}
    }
    return trimmed.split("\n\n").filter(Boolean);
  })();

  const providerSelector = (
    <div className="flex items-center gap-2">
      <select
        value={selectedProvider}
        onChange={(e) => setSelectedProvider(e.target.value)}
        disabled={generating}
        className="px-2 py-1.5 rounded-md border text-sm bg-background disabled:opacity-50"
      >
        <optgroup label="Cloud">
          {PROVIDERS.filter(p => p.group === "cloud").map(p => (
            <option key={p.slug} value={p.slug}>{p.name}</option>
          ))}
        </optgroup>
        <optgroup label="Local">
          {PROVIDERS.filter(p => p.group === "local").map(p => (
            <option key={p.slug} value={p.slug}>{p.name}</option>
          ))}
        </optgroup>
      </select>
    </div>
  );

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <span>Coaching Summary</span>
          {summary && (
            <span className="text-xs font-normal text-muted-foreground">AI-generated</span>
          )}
          <button
            onClick={() => setShowInfo(true)}
            className="text-sm font-normal text-muted-foreground hover:text-foreground cursor-help select-none transition-colors"
            title="What is coaching summary?"
          >&#9432;</button>
        </CardTitle>
      </CardHeader>
      {showInfo && <CoachingSummaryInfoModal onClose={() => setShowInfo(false)} />}
      <CardContent>
        {summary ? (
          <div className="space-y-3">
            {paragraphs.map((paragraph, i) => (
              <p key={i} className="text-sm leading-relaxed">{paragraph}</p>
            ))}
            <div className="pt-2 flex items-center gap-2">
              {providerSelector}
              <Button
                variant="outline" size="sm"
                disabled={generating}
                onClick={() => handleGenerate(selectedProvider)}
              >
                {generating ? "Regenerating..." : "Regenerate"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="text-center py-6 space-y-3">
            <p className="text-sm text-muted-foreground">
              Generate an AI coaching summary of your cross-game patterns and trends.
            </p>
            <div className="flex justify-center items-center gap-2">
              {providerSelector}
              <Button
                size="sm"
                disabled={generating}
                onClick={() => handleGenerate(selectedProvider)}
              >
                {generating ? "Generating..." : "Generate"}
              </Button>
            </div>
            {generating && (
              <p className="text-xs text-muted-foreground animate-pulse">
                This may take 30-60 seconds...
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
