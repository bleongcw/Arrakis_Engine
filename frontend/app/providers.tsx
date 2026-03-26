"use client";

import { ThemeProvider } from "next-themes";
import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { Player } from "@/lib/types";
import { fetchPlayers } from "@/lib/api";

// Player context
interface PlayerContextType {
  players: Player[];
  currentPlayer: string | null;
  setCurrentPlayer: (username: string) => void;
  selectedPlayer: Player | null;
  loading: boolean;
}

const PlayerContext = createContext<PlayerContextType>({
  players: [],
  currentPlayer: null,
  setCurrentPlayer: () => {},
  selectedPlayer: null,
  loading: true,
});

export function usePlayerContext() {
  return useContext(PlayerContext);
}

function PlayerProvider({ children }: { children: ReactNode }) {
  const [players, setPlayers] = useState<Player[]>([]);
  const [currentPlayer, setCurrentPlayer] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPlayers()
      .then((data) => {
        setPlayers(data);
        if (data.length > 0 && !currentPlayer) {
          setCurrentPlayer(data[0].username);
        }
      })
      .catch((err) => {
        console.error("Failed to load players:", err);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, []);

  const selectedPlayer = players.find((p) => p.username === currentPlayer) || null;

  return (
    <PlayerContext.Provider
      value={{ players, currentPlayer, setCurrentPlayer, selectedPlayer, loading }}
    >
      {children}
    </PlayerContext.Provider>
  );
}

export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider attribute="data-theme" defaultTheme="dark" enableSystem={false}>
      <TooltipProvider>
        <PlayerProvider>{children}</PlayerProvider>
      </TooltipProvider>
    </ThemeProvider>
  );
}
