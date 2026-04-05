"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchGameDetail } from "@/lib/api";
import { useChessNavigation } from "@/hooks/use-chess-navigation";
import { ChessBoard } from "@/components/game-detail/chess-board";
import { MoveControls } from "@/components/game-detail/move-controls";
import { MoveList } from "@/components/game-detail/move-list";
import { EvalChart } from "@/components/game-detail/eval-chart";
import { MoveQualitySummary } from "@/components/game-detail/move-quality-summary";
import { CoachingPanels } from "@/components/game-detail/coaching-panels";
import { CoachingButtons } from "@/components/game-detail/coaching-buttons";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { GameDetail } from "@/lib/types";

export default function GameDetailPage() {
  const params = useParams<{ player: string; id: string }>();
  const router = useRouter();
  const gameId = Number(params.id);
  const playerUsername = params.player;
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

  return <GameDetailView detail={detail} onUpdate={setDetail} playerUsername={playerUsername} />;
}

function GameDetailView({
  detail,
  onUpdate,
  playerUsername,
}: {
  detail: GameDetail;
  onUpdate: (d: GameDetail) => void;
  playerUsername: string;
}) {
  const router = useRouter();
  const { game, moves, coaching } = detail;
  const nav = useChessNavigation(game.pgn || "", game.player_color);

  // Build score string
  const scoreMap = { win: game.player_color === "white" ? "1-0" : "0-1", loss: game.player_color === "white" ? "0-1" : "1-0", draw: "½-½" };
  const score = scoreMap[game.result];

  const resultColors = { win: "text-green-500", loss: "text-red-500", draw: "text-yellow-500" };

  // Determine white and black players
  const isWhite = game.player_color === "white";
  const whiteName = isWhite ? (game.display_name || game.username) : (game.opponent_username || "?");
  const blackName = isWhite ? (game.opponent_username || "?") : (game.display_name || game.username);
  const whiteRating = isWhite ? game.player_rating : game.opponent_rating;
  const blackRating = isWhite ? game.opponent_rating : game.player_rating;

  return (
    <div>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => router.push(`/${playerUsername}/games`)}>
            &larr; Back to Games
          </Button>
        </div>
        <CoachingButtons
          gameId={game.id}
          onCoachingComplete={(d) => onUpdate(d)}
        />
      </div>

      {/* Matchup bar */}
      <Card className="mb-4">
        <CardContent className="py-3">
          <div className="flex items-center justify-center gap-4 text-center">
            <div className="flex items-center gap-2">
              <span className="text-lg">{"\u2654"}</span>
              <span className="font-semibold">{whiteName}</span>
              <span className="text-muted-foreground">({whiteRating || "?"})</span>
            </div>
            <span className={`text-xl font-bold ${resultColors[game.result]}`}>
              {score}
            </span>
            <div className="flex items-center gap-2">
              <span className="text-lg">{"\u265A"}</span>
              <span className="font-semibold">{blackName}</span>
              <span className="text-muted-foreground">({blackRating || "?"})</span>
            </div>
          </div>
          <div className="text-center text-xs text-muted-foreground mt-1">
            {game.time_class || "?"} &middot; {game.date_played || "?"}
            {game.platform && <> &middot; {game.platform === "lichess" ? "\u265E Lichess" : "\u265C Chess.com"}</>}
          </div>
        </CardContent>
      </Card>

      {/* Game status notices */}
      {moves.length === 0 && game.analysis_status === "complete" && (
        <Card className="mb-4 border-yellow-500/50 bg-yellow-500/5">
          <CardContent className="py-4 text-center">
            <p className="text-sm font-medium text-yellow-600 dark:text-yellow-400">
              ⚠ This game was abandoned or ended before meaningful moves were played.
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              No move analysis or coaching is available for this game.
            </p>
          </CardContent>
        </Card>
      )}
      {game.analysis_status === "pending" && (
        <Card className="mb-4 border-blue-500/50 bg-blue-500/5">
          <CardContent className="py-4 text-center">
            <p className="text-sm font-medium text-blue-600 dark:text-blue-400">
              ⏳ Analysis pending — run <code className="bg-muted px-1.5 py-0.5 rounded text-xs">python main.py analyze</code> to process this game.
            </p>
          </CardContent>
        </Card>
      )}
      {game.analysis_status === "error" && (
        <Card className="mb-4 border-red-500/50 bg-red-500/5">
          <CardContent className="py-4 text-center">
            <p className="text-sm font-medium text-red-500">
              ❌ Analysis failed for this game. Check server logs for details.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(280px,420px)_1fr] gap-6">
        {/* Left column: Board + moves */}
        <div className="space-y-4">
          <ChessBoard
            position={nav.currentFen}
            orientation={nav.boardOrientation}
            maxWidth={400}
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

        {/* Right column: Eval + Quality + Coaching */}
        <div className="space-y-4">
          {/* Evaluation Chart */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Evaluation</CardTitle>
            </CardHeader>
            <CardContent>
              <EvalChart moves={moves} playerColor={game.player_color} />
            </CardContent>
          </Card>

          {/* Move Quality Summary */}
          <MoveQualitySummary
            moves={moves}
            playerColor={game.player_color}
            playerName={game.display_name || game.username}
          />

          {/* Coaching Panels */}
          <CoachingPanels coaching={coaching} />
        </div>
      </div>
    </div>
  );
}
