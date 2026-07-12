"use client";

/**
 * Import a PGN (v1.24.0). Paste/upload a game; it joins the player's games and
 * runs through the normal analyze → coach pipeline, appearing in /[player]/games
 * with full eval, coaching, and motif tags.
 *
 * v1.25.0: "Competition" mode imports over-the-board tournament PGNs (not on
 * chess.com / lichess). A multi-game file imports every game at once; color is
 * auto-detected from the player's name and the chosen game type sets time_class.
 */

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { importPgn, type ImportPgnResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type GameType = "classical" | "rapid" | "blitz";

export default function ImportPgnPage() {
  const params = useParams<{ player: string }>();
  const router = useRouter();
  const player = params.player;

  const [pgn, setPgn] = useState("");
  const [color, setColor] = useState<"" | "white" | "black">("");
  const [result, setResult] = useState<"" | "win" | "loss" | "draw">("");
  const [competition, setCompetition] = useState(false);
  const [gameType, setGameType] = useState<GameType>("classical");
  const [fileName, setFileName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<ImportPgnResult | null>(null);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setPgn(await file.text());
    setFileName(file.name);
  }

  async function handleImport() {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const data = await importPgn({
        player,
        pgn,
        ...(competition
          ? { platform: "competition", time_class: gameType }
          : {
              player_color: color || undefined,
              result: result || undefined,
            }),
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
            Paste or upload a game. It joins {player}&apos;s games and runs
            through the normal Stockfish + coaching pipeline.
          </p>

          <label className="flex items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              checked={competition}
              onChange={(e) => setCompetition(e.target.checked)}
              className="h-4 w-4"
            />
            🏆 Over-the-board / competition game
          </label>
          {competition && (
            <p className="text-xs text-muted-foreground -mt-2">
              Color is auto-detected from your name and the result is read from
              each game. A multi-game file (a whole tournament) imports every
              game at once.
            </p>
          )}

          <textarea
            value={pgn}
            onChange={(e) => setPgn(e.target.value)}
            placeholder={'[White "..."]\n[Black "..."]\n[Result "1-0"]\n\n1. e4 e5 ...'}
            rows={14}
            className="w-full font-mono text-xs p-3 rounded-md border bg-background"
          />

          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm inline-flex items-center gap-2 cursor-pointer rounded-md border px-3 py-1.5 bg-background hover:bg-accent">
              Upload .pgn
              <input
                type="file"
                accept=".pgn,.txt"
                onChange={handleFile}
                className="hidden"
              />
            </label>
            {fileName && (
              <span className="text-xs text-muted-foreground">{fileName}</span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-4">
            {competition ? (
              <label className="text-sm flex items-center gap-2">
                Game type:
                <select
                  value={gameType}
                  onChange={(e) => setGameType(e.target.value as GameType)}
                  className="px-2 py-1.5 rounded-md border text-sm bg-background"
                >
                  <option value="classical">Classical</option>
                  <option value="rapid">Rapid</option>
                  <option value="blitz">Blitz</option>
                </select>
              </label>
            ) : (
              <>
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
              </>
            )}

            <Button onClick={handleImport} disabled={busy || !pgn.trim()} size="sm">
              {busy ? "Importing…" : competition ? "Import games" : "Import game"}
            </Button>
          </div>

          {!competition && (
            <p className="text-xs text-muted-foreground">
              For an in-progress or unrecorded game (Result “*”), set the result
              explicitly — the engine still analyses the moves you have.
            </p>
          )}

          {error && <div className="text-sm text-red-500">{error}</div>}

          {done && <ImportSummary done={done} player={player} router={router} />}
        </CardContent>
      </Card>
    </div>
  );
}

function ImportSummary({
  done,
  player,
  router,
}: {
  done: ImportPgnResult;
  player: string;
  router: ReturnType<typeof useRouter>;
}) {
  const created = done.created_count ?? (done.created ? 1 : 0);
  const existing = done.existing_count ?? (done.created ? 0 : 1);
  const skipped = done.skipped ?? [];

  return (
    <div className="text-sm rounded-md bg-green-50 dark:bg-green-950/30 p-3 space-y-2">
      {created > 0 ? (
        <div>
          ✅ Imported {created} game{created === 1 ? "" : "s"}
          {existing > 0 && <> ({existing} already present)</>}. Analysis{" "}
          {done.analyze}.
        </div>
      ) : (
        <div>ℹ️ These games were already imported.</div>
      )}

      {skipped.length > 0 && (
        <ul className="text-xs text-amber-600 dark:text-amber-400 list-disc pl-5">
          {skipped.map((s, i) => (
            <li key={i}>Skipped — {s}</li>
          ))}
        </ul>
      )}

      {created === 1 && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => router.push(`/${player}/games/${done.game_id}`)}
        >
          View game
        </Button>
      )}
      {created > 1 && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => router.push(`/${player}/games`)}
        >
          View games
        </Button>
      )}
    </div>
  );
}
