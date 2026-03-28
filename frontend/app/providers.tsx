"use client";

import { ThemeProvider } from "next-themes";
import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import { usePathname } from "next/navigation";
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

// Reserved top-level routes that are NOT player usernames
const RESERVED_ROUTES = new Set(["dashboard", "_not-found"]);

function PlayerProvider({ children }: { children: ReactNode }) {
  const [players, setPlayers] = useState<Player[]>([]);
  const [currentPlayer, setCurrentPlayer] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const pathname = usePathname();

  // Extract player from URL: /<player>/games → "player"
  const segments = pathname.split("/").filter(Boolean);
  const urlPlayer = segments.length > 0 && !RESERVED_ROUTES.has(segments[0])
    ? segments[0]
    : null;

  useEffect(() => {
    fetchPlayers()
      .then((data) => {
        setPlayers(data);
        // Sync currentPlayer from URL if valid, otherwise default to first player
        if (urlPlayer && data.some((p) => p.username === urlPlayer)) {
          setCurrentPlayer(urlPlayer);
        } else if (data.length > 0 && !currentPlayer) {
          setCurrentPlayer(data[0].username);
        }
      })
      .catch((err) => {
        console.error("Failed to load players:", err);
      })
      .finally(() => setLoading(false));
  }, []);

  // Keep context in sync when URL changes
  useEffect(() => {
    if (urlPlayer && players.some((p) => p.username === urlPlayer)) {
      setCurrentPlayer(urlPlayer);
    }
  }, [urlPlayer, players]);

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
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      <TooltipProvider>
        <PlayerProvider>{children}</PlayerProvider>
      </TooltipProvider>
    </ThemeProvider>
  );
}
