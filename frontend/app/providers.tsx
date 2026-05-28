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
  refreshPlayers: () => Promise<void>;
}

const PlayerContext = createContext<PlayerContextType>({
  players: [],
  currentPlayer: null,
  setCurrentPlayer: () => {},
  selectedPlayer: null,
  loading: true,
  refreshPlayers: async () => {},
});

export function usePlayerContext() {
  return useContext(PlayerContext);
}

// Reserved top-level routes that are NOT player slugs (or legacy usernames).
const RESERVED_ROUTES = new Set(["dashboard", "settings", "_not-found"]);

// v1.16.1: match a URL segment against a Player. Slug is the canonical
// identifier; username is accepted as a legacy fallback so old bookmarks
// don't 404 after the rename.
function matchesPlayer(p: Player, urlSegment: string): boolean {
  return (p.slug ?? p.username) === urlSegment || p.username === urlSegment;
}

// v1.16.1: canonical identifier to use for new URLs / state keys —
// always slug when available, falls back to username for pre-v1.16.1
// backend responses.
function canonicalId(p: Player): string {
  return p.slug ?? p.username;
}

function PlayerProvider({ children }: { children: ReactNode }) {
  const [players, setPlayers] = useState<Player[]>([]);
  const [currentPlayer, setCurrentPlayer] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const pathname = usePathname();

  // Extract player from URL: /<slug-or-legacy-username>/games → "..."
  const segments = pathname.split("/").filter(Boolean);
  const urlPlayer = segments.length > 0 && !RESERVED_ROUTES.has(segments[0])
    ? segments[0]
    : null;

  const refreshPlayers = async () => {
    try {
      const data = await fetchPlayers();
      setPlayers(data);
      if (data.length > 0 && !data.some((p) => canonicalId(p) === currentPlayer)) {
        setCurrentPlayer(canonicalId(data[0]));
      }
    } catch (err) {
      console.error("Failed to refresh players:", err);
    }
  };

  useEffect(() => {
    fetchPlayers()
      .then((data) => {
        setPlayers(data);
        // Sync currentPlayer from URL if valid (slug OR legacy username),
        // otherwise default to first player's canonical slug.
        if (urlPlayer) {
          const matched = data.find((p) => matchesPlayer(p, urlPlayer));
          if (matched) {
            setCurrentPlayer(canonicalId(matched));
            return;
          }
        }
        if (data.length > 0 && !currentPlayer) {
          setCurrentPlayer(canonicalId(data[0]));
        }
      })
      .catch((err) => {
        console.error("Failed to load players:", err);
      })
      .finally(() => setLoading(false));
  }, []);

  // Keep context in sync when URL changes
  useEffect(() => {
    if (urlPlayer) {
      const matched = players.find((p) => matchesPlayer(p, urlPlayer));
      if (matched) {
        setCurrentPlayer(canonicalId(matched));
      }
    }
  }, [urlPlayer, players]);

  const selectedPlayer =
    players.find((p) => canonicalId(p) === currentPlayer) || null;

  return (
    <PlayerContext.Provider
      value={{ players, currentPlayer, setCurrentPlayer, selectedPlayer, loading, refreshPlayers }}
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
