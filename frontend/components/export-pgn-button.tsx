"use client";

/**
 * Export one or more games as a PGN file (v1.24.0). Reused on the game-detail
 * page (a single id) and the games list (selected / filtered ids). The
 * "annotated" toggle bakes in Stockfish evals + move-classification NAGs.
 */

import { useState } from "react";
import { exportGamesToFile } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function ExportPgnButton({
  gameIds,
  label = "Export PGN",
}: {
  gameIds: number[];
  label?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [annotated, setAnnotated] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function go() {
    if (gameIds.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      await exportGamesToFile(gameIds, annotated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed.");
    } finally {
      setBusy(false);
    }
  }

  const count = gameIds.length;
  return (
    <div className="flex items-center gap-2">
      <label className="text-xs flex items-center gap-1 text-muted-foreground">
        <input
          type="checkbox"
          checked={annotated}
          onChange={(e) => setAnnotated(e.target.checked)}
          className="h-3.5 w-3.5 accent-blue-600"
        />
        annotated
      </label>
      <Button size="sm" variant="outline" disabled={busy || count === 0} onClick={go}>
        {busy ? "Exporting…" : `${label}${count > 1 ? ` (${count})` : ""}`}
      </Button>
      {error && <span className="text-xs text-red-500">{error}</span>}
    </div>
  );
}
