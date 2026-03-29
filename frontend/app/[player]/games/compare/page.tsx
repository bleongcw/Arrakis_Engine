"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { fetchGameDetail } from "@/lib/api";
import { useChessNavigation } from "@/hooks/use-chess-navigation";
import { ChessBoard } from "@/components/game-detail/chess-board";
import { MoveControls } from "@/components/game-detail/move-controls";
import { EvalChart } from "@/components/game-detail/eval-chart";
import { MoveQualitySummary } from "@/components/game-detail/move-quality-summary";
import { ComparisonSummary } from "@/components/game-detail/comparison-summary";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { GameDetail } from "@/lib/types";

export default function ComparePage() {
  const params = useParams<{ player: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const player = params.player;

  const gamesParam = searchParams.get("games") || "";
  const [id1, id2] = gamesParam.split(",").map(Number);

  const [game1, setGame1] = useState<GameDetail | null>(null);
  const [game2, setGame2] = useState<GameDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id1 || !id2 || isNaN(id1) || isNaN(id2)) {
      setError("Please select two games to compare.");
      setLoading(false);
      return;
    }
    setLoading(true);
    Promise.all([fetchGameDetail(id1), fetchGameDetail(id2)])
      .then(([d1, d2]) => {
        setGame1(d1);
        setGame2(d2);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id1, id2]);

  if (loading) {
    return <div className="h-96 rounded-lg bg-muted animate-pulse" />;
  }

  if (error || !game1 || !game2) {
    return (
      <div className="text-center py-20">
        <p className="text-muted-foreground">{error || "Failed to load games."}</p>
        <Button
          variant="outline"
          size="sm"
          className="mt-4"
          onClick={() => router.push(`/${player}/games`)}
        >
          &larr; Back to Games
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="sm"
          onClick={() => router.push(`/${player}/games`)}
        >
          &larr; Back to Games
        </Button>
        <h2 className="text-lg font-bold">Game Comparison</h2>
      </div>

      {/* Comparison Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <ComparisonSummary game1={game1} game2={game2} />
        </CardContent>
      </Card>

      {/* Side-by-side game views */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <GameColumn detail={game1} label="Game 1" player={player} />
        <GameColumn detail={game2} label="Game 2" player={player} />
      </div>
    </div>
  );
}

function GameColumn({
  detail,
  label,
  player,
}: {
  detail: GameDetail;
  label: string;
  player: string;
}) {
  const { game, moves } = detail;
  const nav = useChessNavigation(game.pgn || "", game.player_color);

  const isWhite = game.player_color === "white";
  const whiteName = isWhite
    ? (game.display_name || game.username)
    : (game.opponent_username || "?");
  const blackName = isWhite
    ? (game.opponent_username || "?")
    : (game.display_name || game.username);
  const whiteRating = isWhite ? game.player_rating : game.opponent_rating;
  const blackRating = isWhite ? game.opponent_rating : game.player_rating;

  const resultColors: Record<string, string> = {
    win: "text-green-500",
    loss: "text-red-500",
    draw: "text-yellow-500",
  };
  const scoreMap: Record<string, string> = {
    win: isWhite ? "1-0" : "0-1",
    loss: isWhite ? "0-1" : "1-0",
    draw: "\u00BD-\u00BD",
  };

  return (
    <div className="space-y-4">
      {/* Matchup bar */}
      <Card>
        <CardContent className="py-3">
          <div className="flex items-center justify-center gap-3 text-center text-sm">
            <div className="flex items-center gap-1">
              <span>{"\u2654"}</span>
              <span className="font-medium">{whiteName}</span>
              <span className="text-muted-foreground text-xs">({whiteRating || "?"})</span>
            </div>
            <span className={`font-bold ${resultColors[game.result]}`}>
              {scoreMap[game.result]}
            </span>
            <div className="flex items-center gap-1">
              <span>{"\u265A"}</span>
              <span className="font-medium">{blackName}</span>
              <span className="text-muted-foreground text-xs">({blackRating || "?"})</span>
            </div>
          </div>
          <div className="text-center text-xs text-muted-foreground mt-1">
            {game.time_class || "?"} &middot; {game.date_played || "?"}
          </div>
        </CardContent>
      </Card>

      {/* Board + controls */}
      <div className="flex flex-col items-center">
        <ChessBoard
          position={nav.currentFen}
          orientation={game.player_color}
          maxWidth={320}
        />
        <div className="mt-2">
          <MoveControls
            onStart={nav.goToStart}
            onBack={nav.goBack}
            onForward={nav.goForward}
            onEnd={nav.goToEnd}
          />
        </div>
      </div>

      {/* Eval chart */}
      {moves.length > 0 && (
        <Card>
          <CardContent className="pt-4">
            <EvalChart moves={moves} playerColor={game.player_color} />
          </CardContent>
        </Card>
      )}

      {/* Move quality summary */}
      {moves.length > 0 && (
        <Card>
          <CardContent className="pt-4">
            <MoveQualitySummary
              moves={moves}
              playerColor={game.player_color}
              playerName={game.display_name || game.username || "Player"}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
