"use client";

import { useRouter, usePathname } from "next/navigation";
import { usePlayerContext } from "@/app/providers";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Reserved top-level routes that are NOT player usernames
const RESERVED_ROUTES = new Set(["dashboard", "_not-found"]);

export function PlayerSelector() {
  const { players, currentPlayer, setCurrentPlayer } = usePlayerContext();
  const router = useRouter();
  const pathname = usePathname();

  const handlePlayerSwitch = (username: string) => {
    setCurrentPlayer(username);

    // Navigate to the same section but under the new player
    const segments = pathname.split("/").filter(Boolean);

    if (segments.length > 0 && !RESERVED_ROUTES.has(segments[0])) {
      // Currently on a player-scoped route: /<player>/games/123 → /<newPlayer>/games/123
      const subPath = segments.slice(1).join("/");
      router.push(`/${username}/${subPath}`);
    } else if (pathname === "/" || pathname === "/dashboard") {
      // On dashboard or home — navigate to the player's games
      router.push(`/${username}/games`);
    } else {
      // Fallback
      router.push(`/${username}/games`);
    }
  };

  return (
    <div className="flex gap-1.5 sm:gap-2">
      {players.map((p) => {
        const displayName = p.display_name || p.username;
        const shortName = displayName.split(" ")[0]; // First name only on mobile
        return (
          <Button
            key={p.username}
            variant={currentPlayer === p.username ? "default" : "outline"}
            size="sm"
            className={cn(
              "text-xs sm:text-sm font-medium transition-colors truncate max-w-[100px] sm:max-w-none",
              currentPlayer === p.username
                ? "bg-[#1e40af] text-white hover:bg-[#1e3a8a]"
                : "text-muted-foreground hover:text-foreground"
            )}
            onClick={() => handlePlayerSwitch(p.username)}
          >
            <span className="sm:hidden">{shortName}</span>
            <span className="hidden sm:inline">{displayName}</span>
          </Button>
        );
      })}
    </div>
  );
}
