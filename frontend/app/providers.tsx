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

// Reserved top-level routes that are NOT player slugs.
const RESERVED_ROUTES = new Set(["dashboard", "settings", "_not-found"]);

// v1.16.4: slug-only matching. The chess.com username is harvester-
// only since v1.16.4 — old URLs that contained the chess.com handle
// no longer resolve (the v1.16.1 backward-compat path was dropped
// once the slug feature stabilised). The frontend has been emitting
// slug-only URLs since v1.16.1, so the practical impact is just
// stale browser bookmarks.
//
// The `?? p.username` fallback is retained ONLY as a defensive
// guard against a pre-v1.16.1 API response that doesn't include
// `slug`. With the v1.16.1+ backend running, every Player row
// always has a slug.
function matchesPlayer(p: Player, urlSegment: string): boolean {
  return (p.slug ?? p.username) === urlSegment;
}

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
