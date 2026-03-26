"use client";

import { Button } from "@/components/ui/button";
import { useCoaching } from "@/hooks/use-coaching";
import type { GameDetail } from "@/lib/types";

interface CoachingButtonsProps {
  gameId: number;
  onCoachingComplete: (detail: GameDetail) => void;
}

export function CoachingButtons({ gameId, onCoachingComplete }: CoachingButtonsProps) {
  const { isCoaching, status, startCoaching } = useCoaching(gameId);

  return (
    <div className="flex items-center gap-3">
      <Button
        size="sm"
        className="bg-[#7c3aed] hover:bg-[#6d28d9] text-white"
        disabled={isCoaching}
        onClick={() => startCoaching("claude", onCoachingComplete)}
      >
        {"\uD83D\uDFE3"} Coach with Claude
      </Button>
      <Button
        size="sm"
        className="bg-[#059669] hover:bg-[#047857] text-white"
        disabled={isCoaching}
        onClick={() => startCoaching("openai", onCoachingComplete)}
      >
        {"\uD83D\uDFE2"} Coach with ChatGPT
      </Button>
      {status && (
        <span className="text-xs text-muted-foreground">{status}</span>
      )}
    </div>
  );
}
