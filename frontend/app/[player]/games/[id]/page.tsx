"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchGameDetail, updateGameRatings, updateGameClassification } from "@/lib/api";
import { platformMeta } from "@/lib/platforms";
import { useChessNavigation } from "@/hooks/use-chess-navigation";
import { ChessBoard } from "@/components/game-detail/chess-board";
import { MoveControls } from "@/components/game-detail/move-controls";
import { MoveList } from "@/components/game-detail/move-list";
import { EvalChart } from "@/components/game-detail/eval-chart";
import { MoveQualitySummary } from "@/components/game-detail/move-quality-summary";
import { CoachingPanels } from "@/components/game-detail/coaching-panels";
import { CoachingButtons } from "@/components/game-detail/coaching-buttons";
import { ExportPgnButton } from "@/components/export-pgn-button";
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

  // Inline ratings editor (v1.25.1): OTB PGNs carry no Elo, so ratings are
  // entered by hand. Inputs are positional (white/black); mapped back to
  // player/opponent by color on save.
  const [editingRatings, setEditingRatings] = useState(false);
  const [whiteInput, setWhiteInput] = useState("");
  const [blackInput, setBlackInput] = useState("");
  const [savingRatings, setSavingRatings] = useState(false);
  const [ratingsError, setRatingsError] = useState<string | null>(null);

  function openRatingsEditor() {
    setWhiteInput(whiteRating != null ? String(whiteRating) : "");
    setBlackInput(blackRating != null ? String(blackRating) : "");
    setRatingsError(null);
    setEditingRatings(true);
  }

  async function saveRatings() {
    setSavingRatings(true);
    setRatingsError(null);
    try {
      const toNum = (s: string) => (s.trim() === "" ? null : Number(s));
      const w = toNum(whiteInput);
      const b = toNum(blackInput);
      const data = await updateGameRatings(game.id, {
        player_rating: isWhite ? w : b,
        opponent_rating: isWhite ? b : w,
      });
      onUpdate({
        ...detail,
        game: {
          ...game,
          player_rating: data.player_rating,
          opponent_rating: data.opponent_rating,
        },
      });
      setEditingRatings(false);
    } catch (e) {
      setRatingsError(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setSavingRatings(false);
    }
  }

  // Inline classification editor (v1.26.2): reclassify a game's category
  // (platform) and game type (time_class) — e.g. an OTB game imported through
  // the generic path can be marked as a Competition (which also strips the
  // competition name/venue from the stored PGN).
  const [editingType, setEditingType] = useState(false);
  const [platformInput, setPlatformInput] = useState("");
  const [timeClassInput, setTimeClassInput] = useState("");
  const [dateInput, setDateInput] = useState("");
  const [savingType, setSavingType] = useState(false);
  const [typeError, setTypeError] = useState<string | null>(null);

  function openTypeEditor() {
    setPlatformInput(game.platform || "chess.com");
    setTimeClassInput(game.time_class ?? "");
    // date_played is stored as "YYYY-MM-DD HH:MM:SS"; the datetime-local input
    // wants "YYYY-MM-DDTHH:MM".
    setDateInput(
      game.date_played ? game.date_played.replace(" ", "T").slice(0, 16) : ""
    );
    setTypeError(null);
    setEditingType(true);
  }

  async function saveType() {
    setSavingType(true);
    setTypeError(null);
    try {
      const data = await updateGameClassification(game.id, {
        platform: platformInput,
        time_class: timeClassInput || null,
        date_played: dateInput || null,
      });
      onUpdate({
        ...detail,
        game: {
          ...game,
          platform: data.platform as typeof game.platform,
          time_class: data.time_class,
          date_played: data.date_played,
        },
      });
      setEditingType(false);
    } catch (e) {
      setTypeError(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setSavingType(false);
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => router.push(`/${playerUsername}/games`)}>
            &larr; Back to Games
          </Button>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <ExportPgnButton gameIds={[game.id]} />
          <CoachingButtons
            gameId={game.id}
            onCoachingComplete={(d) => onUpdate(d)}
          />
        </div>
      </div>

      {/* Matchup bar */}
      <Card className="mb-4">
        <CardContent className="py-3">
          <div className="flex items-center justify-center gap-4 text-center">
            <div className="flex items-center gap-2">
              <span className="text-lg">{"\u2654"}</span>
              <span className="font-semibold">{whiteName}</span>
              {editingRatings ? (
                <input
                  type="number"
                  value={whiteInput}
                  onChange={(e) => setWhiteInput(e.target.value)}
                  placeholder="unrated"
                  aria-label={`${whiteName} rating`}
                  className="w-24 px-1.5 py-0.5 rounded border text-sm bg-background"
                />
              ) : (
                <span className="text-muted-foreground">({whiteRating || "?"})</span>
              )}
            </div>
            <span className={`text-xl font-bold ${resultColors[game.result]}`}>
              {score}
            </span>
            <div className="flex items-center gap-2">
              <span className="text-lg">{"\u265A"}</span>
              <span className="font-semibold">{blackName}</span>
              {editingRatings ? (
                <input
                  type="number"
                  value={blackInput}
                  onChange={(e) => setBlackInput(e.target.value)}
                  placeholder="unrated"
                  aria-label={`${blackName} rating`}
                  className="w-24 px-1.5 py-0.5 rounded border text-sm bg-background"
                />
              ) : (
                <span className="text-muted-foreground">({blackRating || "?"})</span>
              )}
            </div>
          </div>
          <div className="text-center text-xs text-muted-foreground mt-1">
            {game.time_class || "?"} &middot; {game.date_played || "?"}
            {game.platform && (
              <> &middot; {platformMeta(game.platform).icon} {platformMeta(game.platform).label}</>
            )}
          </div>
          {editingType && (
            <div className="flex flex-wrap items-center justify-center gap-2 mt-2">
              <label className="text-xs flex items-center gap-1">
                Category:
                <select
                  value={platformInput}
                  onChange={(e) => setPlatformInput(e.target.value)}
                  className="px-2 py-1 rounded border text-xs bg-background"
                >
                  <option value="chess.com">Chess.com</option>
                  <option value="lichess">Lichess</option>
                  <option value="competition">Competition</option>
                </select>
              </label>
              <label className="text-xs flex items-center gap-1">
                Type:
                <select
                  value={timeClassInput}
                  onChange={(e) => setTimeClassInput(e.target.value)}
                  className="px-2 py-1 rounded border text-xs bg-background"
                >
                  <option value="">unset</option>
                  <option value="classical">Classical</option>
                  <option value="rapid">Rapid</option>
                  <option value="blitz">Blitz</option>
                  <option value="bullet">Bullet</option>
                  <option value="daily">Daily</option>
                </select>
              </label>
              <label className="text-xs flex items-center gap-1">
                Date:
                <input
                  type="datetime-local"
                  value={dateInput}
                  onChange={(e) => setDateInput(e.target.value)}
                  className="px-2 py-1 rounded border text-xs bg-background"
                />
              </label>
              <Button size="sm" variant="outline" onClick={saveType} disabled={savingType}>
                {savingType ? "Saving\u2026" : "Save"}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setEditingType(false)}
                disabled={savingType}
              >
                Cancel
              </Button>
            </div>
          )}
          <div className="flex items-center justify-center gap-2 mt-2">
            {editingRatings ? (
              <>
                <Button size="sm" variant="outline" onClick={saveRatings} disabled={savingRatings}>
                  {savingRatings ? "Saving\u2026" : "Save ratings"}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setEditingRatings(false)}
                  disabled={savingRatings}
                >
                  Cancel
                </Button>
              </>
            ) : !editingType ? (
              <>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 text-xs text-muted-foreground"
                  onClick={openRatingsEditor}
                >
                  Edit ratings
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 text-xs text-muted-foreground"
                  onClick={openTypeEditor}
                >
                  Edit details
                </Button>
              </>
            ) : null}
          </div>
          {ratingsError && (
            <div className="text-center text-xs text-red-500 mt-1">{ratingsError}</div>
          )}
          {typeError && (
            <div className="text-center text-xs text-red-500 mt-1">{typeError}</div>
          )}
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
