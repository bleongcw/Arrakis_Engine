"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { GameCoaching } from "@/lib/types";

interface CoachingPanelsProps {
  coaching: GameCoaching | null;
}

export function CoachingPanels({ coaching }: CoachingPanelsProps) {
  if (!coaching) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          Run coaching analysis to see insights.
        </CardContent>
      </Card>
    );
  }

  const providerStr = coaching.provider || "";
  const [prov, model] = providerStr.includes(":")
    ? providerStr.split(":", 2)
    : [providerStr, ""];
  const badgeColor = prov === "claude" ? "#7c3aed" : "#059669";
  const badgeIcon = prov === "claude" ? "\uD83D\uDFE3" : "\uD83D\uDFE2";

  return (
    <div className="space-y-4">
      {/* Game Story */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            Game Story
            {model && (
              <span
                className="text-xs px-2 py-0.5 rounded text-white"
                style={{ backgroundColor: badgeColor }}
              >
                {badgeIcon} {model}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm leading-relaxed whitespace-pre-wrap">
            {coaching.narrative || "Not available"}
          </div>
        </CardContent>
      </Card>

      {/* Key Lesson */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Key Lesson</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm">{coaching.key_lesson || "\u2014"}</p>
        </CardContent>
      </Card>

      {/* Practice Focus */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Practice Focus</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm">{coaching.practical_focus || "\u2014"}</p>
        </CardContent>
      </Card>

      {/* Player Feedback */}
      {coaching.player_feedback && (
        <Card className="border-l-4 border-l-green-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-green-500">
              Feedback to the Player
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm leading-relaxed whitespace-pre-wrap">
              {coaching.player_feedback}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Opening Analysis */}
      {coaching.opening_analysis && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Opening Analysis</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div className="bg-muted p-3 rounded">
                <div className="text-xs text-muted-foreground uppercase">Opening</div>
                <div className="font-semibold">
                  {coaching.opening_analysis.opening_name || "Unknown"}
                </div>
              </div>
              <div className="bg-muted p-3 rounded">
                <div className="text-xs text-muted-foreground uppercase">Quality</div>
                <div
                  className="font-semibold uppercase"
                  style={{
                    color:
                      coaching.opening_analysis.opening_quality === "good"
                        ? "#22c55e"
                        : coaching.opening_analysis.opening_quality === "poor"
                        ? "#ef4444"
                        : "#eab308",
                  }}
                >
                  {coaching.opening_analysis.opening_quality || "?"}
                </div>
              </div>
            </div>
            {coaching.opening_analysis.opening_summary && (
              <p className="text-sm mb-2">{coaching.opening_analysis.opening_summary}</p>
            )}
            {coaching.opening_analysis.opening_tip && (
              <p className="text-sm text-muted-foreground italic">
                Tip: {coaching.opening_analysis.opening_tip}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Critical Moments */}
      {coaching.critical_moments && coaching.critical_moments.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Critical Moments</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {coaching.critical_moments.map((m, i) => (
              <div key={i} className="bg-muted p-3 rounded text-sm">
                <div className="font-semibold mb-1">
                  Move {m.move_number} ({m.side}): {m.move_played}
                </div>
                <div className="text-yellow-500">{m.what_happened}</div>
                <div className="text-green-500">Better: {m.what_was_better}</div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Coach Notes */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Coach Notes</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
            {coaching.coach_notes || "\u2014"}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
