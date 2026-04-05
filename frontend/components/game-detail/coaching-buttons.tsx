"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useCoaching } from "@/hooks/use-coaching";
import { PROVIDERS } from "@/lib/providers";
import type { GameDetail } from "@/lib/types";

interface CoachingButtonsProps {
  gameId: number;
  onCoachingComplete: (detail: GameDetail) => void;
}

export function CoachingButtons({ gameId, onCoachingComplete }: CoachingButtonsProps) {
  const { isCoaching, status, startCoaching } = useCoaching(gameId);
  const [selectedProvider, setSelectedProvider] = useState("openai");

  const providerMeta = PROVIDERS.find(p => p.slug === selectedProvider) ?? PROVIDERS[0];

  return (
    <div className="flex items-center gap-3">
      <select
        value={selectedProvider}
        onChange={(e) => setSelectedProvider(e.target.value)}
        disabled={isCoaching}
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
      <Button
        size="sm"
        style={{ backgroundColor: providerMeta.color }}
        className="text-white hover:opacity-90"
        disabled={isCoaching}
        onClick={() => startCoaching(selectedProvider, onCoachingComplete)}
      >
        Coach Game
      </Button>
      {status && (
        <span className="text-xs text-muted-foreground">{status}</span>
      )}
    </div>
  );
}
