"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { GameCoaching } from "@/lib/types";
import { parseSectionedFeedback } from "@/lib/feedback-sections";
import { MOTIF_LABELS } from "@/lib/motifs";

interface CoachingPanelsProps {
  coaching: GameCoaching | null;
}

/** Extract readable text from a value that may be plain text or JSON. */
function toText(value: string | null | undefined, fallback = "\u2014"): string {
  if (!value) return fallback;
  const trimmed = value.trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return trimmed;
  try {
    const parsed = JSON.parse(trimmed);
    if (typeof parsed === "string") return parsed;
    if (Array.isArray(parsed)) return parsed.filter((v) => typeof v === "string").join("\n\n");
    if (parsed.paragraphs && Array.isArray(parsed.paragraphs)) return parsed.paragraphs.join("\n\n");
    if (parsed.text) return String(parsed.text);
    // Flatten all string values from the object
    const strings = Object.values(parsed).flatMap((v) =>
      Array.isArray(v) ? v.filter((s) => typeof s === "string") : typeof v === "string" ? [v] : []
    );
    return strings.length > 0 ? strings.join("\n\n") : trimmed;
  } catch {
    return trimmed;
  }
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

  // v1.6.0: coaching meta \u2014 shows how many recent games the LLM had in
  // its context window when generating this brief. Helps the user verify
  // history-injection is actually working as configured.
  const historyCount = coaching.meta?.history_games_injected;
  const historyStamp = typeof historyCount === "number" && historyCount > 0
    ? `${historyCount} recent game${historyCount === 1 ? "" : "s"} in context`
    : null;

  // v1.8.0: trajectory injection stamp \u2014 shows whether the per-player
  // 30-day trajectory block reached the LLM, and how stale it was at
  // coaching time. Silent (no stamp) when trajectory wasn't injected
  // (player has no patterns yet, or disabled via config / CLI flag).
  const trajectoryInjected = coaching.meta?.trajectory_injected;
  const trajectoryAge = coaching.meta?.trajectory_age_days;
  const trajectoryWeakest = coaching.meta?.trajectory_weakest_phase;
  const trajectoryTrend = coaching.meta?.trajectory_trend_direction;
  const trajectoryStamp = trajectoryInjected
    ? `30-day trajectory${typeof trajectoryAge === "number" ? ` (${trajectoryAge}d old)` : ""}`
    : null;
  const trajectoryTooltip = trajectoryInjected
    ? `The coach had access to the player's measured 30-day trajectory${
        trajectoryWeakest ? ` (weakest phase: ${trajectoryWeakest}` : ""
      }${
        trajectoryTrend ? `; trend: ${trajectoryTrend})` : trajectoryWeakest ? ")" : ""
      } when writing this brief.${
        typeof trajectoryAge === "number" && trajectoryAge > 7
          ? ` This snapshot is ${trajectoryAge} days old \u2014 re-run \`python main.py patterns\` to refresh.`
          : ""
      }`
    : "";

  return (
    <div className="space-y-4">
      {/* Game Story */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2 flex-wrap">
            Game Story
            {model && (
              <span
                className="text-xs px-2 py-0.5 rounded text-white"
                style={{ backgroundColor: badgeColor }}
              >
                {badgeIcon} {model}
              </span>
            )}
            {historyStamp && (
              <span
                className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-normal"
                title={`The coach had access to the lessons from ${historyCount} previous coached games when writing this brief, so the advice should build on (not repeat) earlier coaching.`}
              >
                📚 {historyStamp}
              </span>
            )}
            {trajectoryStamp && (
              <span
                className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-normal"
                title={trajectoryTooltip}
              >
                📊 {trajectoryStamp}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm leading-relaxed whitespace-pre-wrap">
            {toText(coaching.narrative, "Not available")}
          </div>
        </CardContent>
      </Card>

      {/* Key Lesson */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Key Lesson</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm">{toText(coaching.key_lesson)}</p>
        </CardContent>
      </Card>

      {/* Practice Focus */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Practice Focus</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm">{toText(coaching.practical_focus)}</p>
        </CardContent>
      </Card>

      {/* Player Feedback — v1.13.0+ phase-structured 5-section render.
          Legacy pre-v1.13.0 entries (no `## ` headings) fall back to a
          single section with empty heading and the full body as one
          block, matching the pre-v1.13.0 look exactly.
          v1.13.2+: a ⚠ badge appears in the header when the LLM produced
          non-compliant output (older or non-reasoning models often skip
          the strict format spec). */}
      {coaching.player_feedback && (
        <Card className="border-l-4 border-l-green-500">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-green-500 flex items-center gap-2 flex-wrap">
              <span>Feedback to the Player</span>
              {coaching.meta?.feedback_structure_compliant === false && (
                <span
                  className="text-[10px] font-normal px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200"
                  title={
                    `This brief was produced as freeform text instead of the ` +
                    `v1.13.0 phase-structured format. The model "` +
                    (coaching.meta?.model || "unknown") +
                    `" didn't follow the 5-section spec` +
                    (coaching.meta?.feedback_missing_headings?.length
                      ? ` (missing: ${coaching.meta.feedback_missing_headings.join(", ")})`
                      : "") +
                    `. Re-coach with a newer reasoning model (claude-opus-4-7 or ` +
                    `gpt-5.5-pro-2026-04-23) to get the structured layout.`
                  }
                >
                  ⚠ unstructured
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {parseSectionedFeedback(coaching.player_feedback).map((section, i) => (
              <section key={i} className="mb-4 last:mb-0">
                {section.heading && (
                  <h4 className="text-sm font-semibold mb-2 text-green-600 dark:text-green-400">
                    {section.heading}
                  </h4>
                )}
                {section.body.map((p, j) => (
                  <p
                    key={j}
                    className="text-sm leading-relaxed whitespace-pre-wrap mb-2 last:mb-0"
                  >
                    {p}
                  </p>
                ))}
              </section>
            ))}
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
              <p className="text-sm mb-2">{toText(coaching.opening_analysis.opening_summary)}</p>
            )}
            {coaching.opening_analysis.opening_tip && (
              <p className="text-sm text-muted-foreground italic">
                Tip: {toText(coaching.opening_analysis.opening_tip)}
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
                {/* v1.14.0: tactical motif badges. Silent (no row) when both
                    motifs_found and motifs_missed are empty — covers pre-v1.14.0
                    entries + critical moves where no motifs were detected. */}
                <MotifBadgeRow
                  found={m.motifs_found}
                  missed={m.motifs_missed}
                />
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
            {toText(coaching.coach_notes)}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// v1.14.0: tactical motif badges for a single Critical Moment.
// Emoji + label per motif identifier; emerald chips for "found" (what
// the best move did), amber chips for "missed" (themes the player
// didn't take). Silent row when both arrays are empty/missing — keeps
// pre-v1.14.0 entries visually unchanged.
//
// v1.15.0: MOTIF_LABELS lifted to `@/lib/motifs` so the Patterns-page
// MotifThemes card shares the same icon + label map.

function MotifBadgeRow({
  found,
  missed,
}: {
  found?: string[];
  missed?: string[];
}) {
  const hasFound = found && found.length > 0;
  const hasMissed = missed && missed.length > 0;
  if (!hasFound && !hasMissed) return null;
  const renderBadge = (
    motif: string,
    variant: "found" | "missed",
    idx: number,
  ) => {
    const meta = MOTIF_LABELS[motif] ?? { icon: "•", label: motif };
    const cls =
      variant === "found"
        ? "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200"
        : "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200";
    return (
      <span
        key={`${variant}-${idx}-${motif}`}
        className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${cls}`}
        title={
          variant === "found"
            ? `The best move executed: ${meta.label}`
            : `The played move missed this theme: ${meta.label}`
        }
      >
        {meta.icon} {meta.label}
      </span>
    );
  };
  return (
    <div className="mt-2 flex items-center gap-1.5 flex-wrap">
      {hasMissed && (
        <>
          <span className="text-[10px] text-muted-foreground">missed:</span>
          {missed!.map((m, i) => renderBadge(m, "missed", i))}
        </>
      )}
      {hasFound && (
        <>
          <span className="text-[10px] text-muted-foreground">
            {hasMissed ? "· found:" : "found:"}
          </span>
          {found!.map((m, i) => renderBadge(m, "found", i))}
        </>
      )}
    </div>
  );
}
