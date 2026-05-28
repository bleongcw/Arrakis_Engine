"use client";

import { useRouter, usePathname } from "next/navigation";
import { usePlayerContext } from "@/app/providers";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Reserved top-level routes that are NOT player slugs / usernames.
const RESERVED_ROUTES = new Set(["dashboard", "_not-found"]);

// v1.16.1: prefer slug for URLs (canonical), fall back to username
// for pre-v1.16.1 backend responses that don't include a slug yet.
function playerRouteId(p: { slug?: string; username: string }): string {
  return p.slug ?? p.username;
}

export function PlayerSelector() {
  const { players, currentPlayer, setCurrentPlayer } = usePlayerContext();
  const router = useRouter();
  const pathname = usePathname();

  const handlePlayerSwitch = (routeId: string) => {
    setCurrentPlayer(routeId);

    // Navigate to the same section but under the new player
    const segments = pathname.split("/").filter(Boolean);

    if (segments.length > 0 && !RESERVED_ROUTES.has(segments[0])) {
      // Currently on a player-scoped route: /<player>/games/123 → /<newPlayer>/games/123
      const subPath = segments.slice(1).join("/");
      router.push(`/${routeId}/${subPath}`);
    } else if (pathname === "/" || pathname === "/dashboard") {
      // On dashboard or home — navigate to the player's games
      router.push(`/${routeId}/games`);
    } else {
      // Fallback
      router.push(`/${routeId}/games`);
    }
  };

  return (
    <div className="flex gap-1.5 sm:gap-2">
      {players.map((p) => {
        const displayName = p.display_name || p.username;
        const shortName = displayName.split(" ")[0]; // First name only on mobile
        const routeId = playerRouteId(p);
        return (
          <Button
            key={routeId}
            variant={currentPlayer === routeId ? "default" : "outline"}
            size="sm"
            className={cn(
              "text-xs sm:text-sm font-medium transition-colors truncate max-w-[100px] sm:max-w-none",
              currentPlayer === routeId
                ? "bg-[#1e40af] text-white hover:bg-[#1e3a8a]"
                : "text-muted-foreground hover:text-foreground"
            )}
            aria-label={`Switch to ${displayName}`}
            onClick={() => handlePlayerSwitch(routeId)}
          >
            <span className="sm:hidden">{shortName}</span>
            <span className="hidden sm:inline">{displayName}</span>
          </Button>
        );
      })}
    </div>
  );
}
