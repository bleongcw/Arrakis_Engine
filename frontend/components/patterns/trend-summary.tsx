"use client";

import { useState, useCallback, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { triggerTrendSummary, fetchPatterns } from "@/lib/api";

interface TrendSummaryProps {
  summary: string | null | undefined;
  player: string;
  onSummaryGenerated: () => void;
}

export function TrendSummary({ summary, player, onSummaryGenerated }: TrendSummaryProps) {
  const [generating, setGenerating] = useState(false);
  const [provider, setProvider] = useState<"claude" | "openai">("claude");
  const previousSummaryRef = useRef(summary);

  const handleGenerate = useCallback(async (p: "claude" | "openai") => {
    setProvider(p);
    setGenerating(true);
    // Capture the current summary so we can detect when it changes
    const oldSummary = previousSummaryRef.current;
    try {
      await triggerTrendSummary(player, p);
      // Poll for completion — detect when summary changes from the old value
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
      // Stop polling after 5 minutes
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

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <span>Coaching Summary</span>
          {summary && (
            <span className="text-xs font-normal text-muted-foreground">AI-generated</span>
          )}
          <span
            title="An AI coach analyzes all your pattern data (accuracy, openings, time management, blunders) and writes a personalized summary of strengths, weaknesses, and what to work on next."
            className="text-sm font-normal text-muted-foreground hover:text-foreground cursor-help select-none transition-colors"
          >&#9432;</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {summary ? (
          <div className="space-y-3">
            {paragraphs.map((paragraph, i) => (
              <p key={i} className="text-sm leading-relaxed">{paragraph}</p>
            ))}
            <div className="pt-2 flex gap-2">
              <Button
                variant="outline" size="sm"
                disabled={generating}
                onClick={() => handleGenerate("claude")}
              >
                {generating && provider === "claude" ? "Regenerating..." : "Regenerate with Claude"}
              </Button>
              <Button
                variant="outline" size="sm"
                disabled={generating}
                onClick={() => handleGenerate("openai")}
              >
                {generating && provider === "openai" ? "Regenerating..." : "Regenerate with ChatGPT"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="text-center py-6 space-y-3">
            <p className="text-sm text-muted-foreground">
              Generate an AI coaching summary of your cross-game patterns and trends.
            </p>
            <div className="flex justify-center gap-2">
              <Button
                size="sm"
                disabled={generating}
                className="bg-purple-600 hover:bg-purple-700 text-white"
                onClick={() => handleGenerate("claude")}
              >
                {generating && provider === "claude" ? "Generating..." : "Generate with Claude"}
              </Button>
              <Button
                size="sm"
                disabled={generating}
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
                onClick={() => handleGenerate("openai")}
              >
                {generating && provider === "openai" ? "Generating..." : "Generate with ChatGPT"}
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
