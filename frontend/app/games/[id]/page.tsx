"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchGameDetail } from "@/lib/api";
import { useChessNavigation } from "@/hooks/use-chess-navigation";
import { ChessBoard } from "@/components/game-detail/chess-board";
import { MoveControls } from "@/components/game-detail/move-controls";
import { MoveList } from "@/components/game-detail/move-list";
import { EvalChart } from "@/components/game-detail/eval-chart";
import { CoachingPanels } from "@/components/game-detail/coaching-panels";
import { CoachingButtons } from "@/components/game-detail/coaching-buttons";
import { TierBadge } from "@/components/tier-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { GameDetail } from "@/lib/types";

export default function GameDetailPage() {
  const params = useParams();
  const router = useRouter();
  const gameId = Number(params.id);
  const [detail, setDetail] = useState<GameDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchGameDetail(gameId)
      .then(setDetail)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [gameId]);

  if (loading || !detail) {
    return <div className="h-96 rounded-lg bg-muted animate-pulse" />;
  }

  return <GameDetailView detail={detail} onUpdate={setDetail} />;
}

function GameDetailView({
  detail,
  onUpdate,
}: {
  detail: GameDetail;
  onUpdate: (d: GameDetail) => void;
}) {
  const router = useRouter();
  const { game, moves, coaching } = detail;

  const nav = useChessNavigation(game.pgn || "", game.player_color);

  const resultColors = {
    win: "text-green-500",
    loss: "text-red-500",
    draw: "text-yellow-500",
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => router.push("/games")}>
            &larr; Back to Games
          </Button>
          {game.tier && (
            <TierBadge tier={game.tier} label={game.tier_label} icon={game.tier_icon} />
          )}
        </div>
        <CoachingButtons
          gameId={game.id}
          onCoachingComplete={(d) => onUpdate(d)}
        />
      </div>

      {/* Matchup bar */}
      <Card className="mb-4">
        <CardContent className="py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">{game.player_color === "white" ? "\u2654" : "\u265A"}</span>
            <span className="font-semibold">
              {game.display_name || game.username}
            </span>
            <span className="text-muted-foreground">({game.player_rating || "?"})</span>
          </div>
          <span className={`text-lg font-bold ${resultColors[game.result]}`}>
            {game.result.toUpperCase()}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">({game.opponent_rating || "?"})</span>
            <span className="font-semibold">{game.opponent_username || "?"}</span>
            <span className="text-lg">{game.player_color === "white" ? "\u265A" : "\u2654"}</span>
          </div>
        </CardContent>
      </Card>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-6">
        {/* Left column: Board + moves */}
        <div className="space-y-4">
          <ChessBoard
            position={nav.currentFen}
            orientation={nav.boardOrientation}
            boardWidth={400}
          />
          <MoveControls
            onStart={nav.goToStart}
            onBack={nav.goBack}
            onForward={nav.goForward}
            onEnd={nav.goToEnd}
          />
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Moves</CardTitle>
            </CardHeader>
            <CardContent>
              <MoveList
                moves={moves}
                playerColor={game.player_color}
                currentMoveIndex={nav.moveIndex}
                onMoveClick={nav.goToMove}
              />
            </CardContent>
          </Card>
        </div>

        {/* Right column: Charts + coaching */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Evaluation</CardTitle>
            </CardHeader>
            <CardContent>
              <EvalChart moves={moves} playerColor={game.player_color} />
            </CardContent>
          </Card>

          <CoachingPanels coaching={coaching} />
        </div>
      </div>
    </div>
  );
}
