"use client";

import { usePlayerContext } from "@/app/providers";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function PlayerSelector() {
  const { players, currentPlayer, setCurrentPlayer } = usePlayerContext();

  return (
    <div className="flex gap-2">
      {players.map((p) => (
        <Button
          key={p.username}
          variant={currentPlayer === p.username ? "default" : "outline"}
          size="sm"
          className={cn(
            "text-sm font-medium transition-colors",
            currentPlayer === p.username
              ? "bg-[#1e40af] text-white hover:bg-[#1e3a8a]"
              : "text-muted-foreground hover:text-foreground"
          )}
          onClick={() => setCurrentPlayer(p.username)}
        >
          {p.display_name || p.username}
        </Button>
      ))}
    </div>
  );
}
