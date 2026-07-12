import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { TierBadge } from "./tier-badge";
import { PlatformLinkCard } from "./platform-link-card";
import type { Player } from "@/lib/types";

interface PlayerCardProps {
  player: Player;
}

export function PlayerCard({ player }: PlayerCardProps) {
  return (
    <Card className="mb-6">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <div>
          <h2 className="text-xl font-bold">
            {player.display_name || player.username}
          </h2>
          {player.age && (
            <p className="text-sm text-muted-foreground">
              {player.age} years old
            </p>
          )}
        </div>
        <TierBadge
          tier={player.tier}
          label={player.tier_label}
          icon={player.tier_icon}
        />
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <PlatformLinkCard
            platform="chesscom"
            url={player.chesscom_url}
            games={player.chesscom_games}
          />
          <PlatformLinkCard
            platform="lichess"
            url={player.lichess_url}
            games={player.lichess_games}
          />
          <PlatformLinkCard
            platform="fide"
            url={player.fide_url}
            rating={player.fide_rating_classical}
            subtitle={
              [
                player.fide_rating_rapid && `R ${player.fide_rating_rapid}`,
                player.fide_rating_blitz && `B ${player.fide_rating_blitz}`,
                player.fide_id && `ID: ${player.fide_id}`,
              ]
                .filter(Boolean)
                .join(" · ") || undefined
            }
          />
        </div>
      </CardContent>
    </Card>
  );
}
