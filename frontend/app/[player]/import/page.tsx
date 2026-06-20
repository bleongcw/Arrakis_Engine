"use client";

/**
 * Import a PGN (v1.24.0). Paste/upload a game; it joins the player's games and
 * runs through the normal analyze → coach pipeline, appearing in /[player]/games
 * with full eval, coaching, and motif tags.
 */

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { importPgn, type ImportPgnResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ImportPgnPage() {
  const params = useParams<{ player: string }>();
  const router = useRouter();
  const player = params.player;

  const [pgn, setPgn] = useState("");
  const [color, setColor] = useState<"" | "white" | "black">("");
  const [result, setResult] = useState<"" | "win" | "loss" | "draw">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<ImportPgnResult | null>(null);

  async function handleImport() {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const data = await importPgn({
        player,
        pgn,
        player_color: color || undefined,
        result: result || undefined,
      });
      setDone(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto">
      <Card>
        <CardHeader>
          <CardTitle>Import a PGN</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Paste a game. It joins {player}&apos;s games and runs through the
            normal Stockfish + coaching pipeline.
          </p>

          <textarea
            value={pgn}
            onChange={(e) => setPgn(e.target.value)}
            placeholder={'[White "..."]\n[Black "..."]\n[Result "1-0"]\n\n1. e4 e5 ...'}
            rows={14}
            className="w-full font-mono text-xs p-3 rounded-md border bg-background"
          />

          <div className="flex flex-wrap items-center gap-4">
            <label className="text-sm flex items-center gap-2">
              Played as:
              <select
                value={color}
                onChange={(e) => setColor(e.target.value as typeof color)}
                className="px-2 py-1.5 rounded-md border text-sm bg-background"
              >
                <option value="">auto-detect</option>
                <option value="white">White</option>
                <option value="black">Black</option>
              </select>
            </label>

            <label className="text-sm flex items-center gap-2">
              Result:
              <select
                value={result}
                onChange={(e) => setResult(e.target.value as typeof result)}
                className="px-2 py-1.5 rounded-md border text-sm bg-background"
              >
                <option value="">from PGN</option>
                <option value="win">Win</option>
                <option value="loss">Loss</option>
                <option value="draw">Draw</option>
              </select>
            </label>

            <Button onClick={handleImport} disabled={busy || !pgn.trim()} size="sm">
              {busy ? "Importing…" : "Import game"}
            </Button>
          </div>

          <p className="text-xs text-muted-foreground">
            For an in-progress or unrecorded game (Result “*”), set the result
            explicitly — the engine still analyses the moves you have.
          </p>

          {error && <div className="text-sm text-red-500">{error}</div>}

          {done && (
            <div className="text-sm rounded-md bg-green-50 dark:bg-green-950/30 p-3">
              {done.created ? (
                <>
                  ✅ Imported as game #{done.game_id} ({done.result}, {done.moves}{" "}
                  moves, you played {done.player_color}). Analysis {done.analyze}.{" "}
                  <Button
                    variant="outline"
                    size="sm"
                    className="ml-2"
                    onClick={() => router.push(`/${player}/games/${done.game_id}`)}
                  >
                    View game
                  </Button>
                </>
              ) : (
                <>ℹ️ This game was already imported (game #{done.game_id}).</>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
