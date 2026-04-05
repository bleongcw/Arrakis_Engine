"use client";

import { useState, useRef, useEffect, type ReactNode } from "react";
import { usePipeline } from "@/hooks/use-pipeline";
import { useSchedule } from "@/hooks/use-schedule";
import { usePlayerContext } from "@/app/providers";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const TASK_LABELS: Record<string, string> = {
  harvest: "Fetch New Games",
  analyze: "Run Analysis",
  patterns: "Update Insights",
  coach: "Generate Coaching Briefs",
  run_all: "Run All Steps",
};

function friendlyResult(result: Record<string, number>): string {
  const parts: string[] = [];
  if (result.new_games != null) {
    parts.push(`${result.new_games} new game${result.new_games !== 1 ? "s" : ""} fetched`);
  }
  if (result.games_analyzed != null) {
    parts.push(`${result.games_analyzed} game${result.games_analyzed !== 1 ? "s" : ""} analyzed`);
  }
  if (result.players_updated != null) {
    parts.push(`insights updated for ${result.players_updated} player${result.players_updated !== 1 ? "s" : ""}`);
  }
  if (result.coached != null) {
    parts.push(`${result.coached} game${result.coached !== 1 ? "s" : ""} coached`);
  }
  if (result.skipped != null && result.skipped > 0) {
    parts.push(`${result.skipped} skipped`);
  }
  if (result.errors && result.errors > 0) {
    parts.push(`${result.errors} error${result.errors !== 1 ? "s" : ""}`);
  }
  return parts.length > 0 ? parts.join(", ") : "Done!";
}

// ── Time helpers ─────────────────────────────────────────

function relativeTime(isoString: string | null): string {
  if (!isoString) return "";
  const diff = new Date(isoString).getTime() - Date.now();
  const absDiff = Math.abs(diff);
  const minutes = Math.round(absDiff / 60000);
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;

  if (diff > 0) {
    // Future
    if (hours > 0) return `in ${hours}h ${mins}m`;
    return `in ${mins}m`;
  } else {
    // Past
    if (hours > 0) return `${hours}h ${mins}m ago`;
    if (mins > 0) return `${mins}m ago`;
    return "just now";
  }
}

const INTERVAL_OPTIONS = [1, 3, 6, 12, 24];

// ── Tooltip component ────────────────────────────────────

function Tooltip({ children, text }: { children: ReactNode; text: string }) {
  const [show, setShow] = useState(false);
  const [position, setPosition] = useState<"top" | "bottom">("top");
  const triggerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (show && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      // If too close to top of viewport, show below
      setPosition(rect.top < 80 ? "bottom" : "top");
    }
  }, [show]);

  return (
    <div
      ref={triggerRef}
      className="relative inline-flex"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <div
          className={cn(
            "absolute left-1/2 -translate-x-1/2 z-50 px-3 py-2 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded-lg shadow-lg whitespace-normal text-center max-w-[220px] w-max pointer-events-none",
            position === "top" ? "bottom-full mb-2" : "top-full mt-2"
          )}
        >
          {text}
          <div
            className={cn(
              "absolute left-1/2 -translate-x-1/2 w-2 h-2 bg-gray-900 dark:bg-gray-700 rotate-45",
              position === "top" ? "top-full -mt-1" : "bottom-full -mb-1"
            )}
          />
        </div>
      )}
    </div>
  );
}

// ── Arrow between steps ──────────────────────────────────

function StepArrow() {
  return (
    <svg
      className="w-5 h-5 text-muted-foreground/50 shrink-0 hidden sm:block"
      viewBox="0 0 20 20"
      fill="currentColor"
    >
      <path
        fillRule="evenodd"
        d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z"
        clipRule="evenodd"
      />
    </svg>
  );
}

// ── Main component ───────────────────────────────────────

export function PipelineControlPanel() {
  const { state, dismissed, startHarvest, startAnalyze, startPatterns, startRunAll, startCoach, cancel, dismiss } =
    usePipeline();
  const { players } = usePlayerContext();
  const [selectedPlayer, setSelectedPlayer] = useState<string>("all");
  const [selectedProvider, setSelectedProvider] = useState<string>("openai");
  const [actionError, setActionError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  const isRunning = state.status === "running";
  const playerArg = selectedPlayer === "all" ? undefined : selectedPlayer;

  // Reset cancelling state when task finishes
  if (!isRunning && cancelling) {
    setCancelling(false);
  }

  const handleCancel = async () => {
    setCancelling(true);
    setActionError(null);
    try {
      await cancel();
    } catch {
      // Ignore — task may have finished between click and request
    }
  };

  const handleAction = async (action: () => Promise<void>) => {
    setActionError(null);
    try {
      await action();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Something went wrong.");
    }
  };

  // Progress bar percentage
  const progressPct =
    state.detail?.games_total && state.detail.games_total > 0
      ? Math.round(
          ((state.detail.games_processed ?? 0) / state.detail.games_total) * 100
        )
      : null;

  // Step indicator for run_all
  const stepText =
    state.task === "run_all" && state.detail?.total_steps
      ? `Step ${state.detail.current_step ?? "?"} of ${state.detail.total_steps}`
      : null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          Data Updates
          {isRunning && (
            <span className="inline-flex h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Pipeline steps row */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Step 1: Fetch */}
          <Tooltip text="Download the latest games from Chess.com and Lichess for the selected player(s).">
            <button
              disabled={isRunning}
              onClick={() => handleAction(() => startHarvest(playerArg))}
              className={cn(
                "px-3 py-2 rounded-md text-sm font-medium transition-colors",
                isRunning
                  ? "bg-muted text-muted-foreground cursor-not-allowed"
                  : "bg-emerald-600 text-white hover:bg-emerald-700"
              )}
            >
              Fetch New Games
            </button>
          </Tooltip>

          <StepArrow />

          {/* Step 2: Analyze */}
          <Tooltip text="Run Stockfish engine analysis on all unanalyzed games to evaluate every move.">
            <button
              disabled={isRunning}
              onClick={() => handleAction(() => startAnalyze())}
              className={cn(
                "px-3 py-2 rounded-md text-sm font-medium transition-colors",
                isRunning
                  ? "bg-muted text-muted-foreground cursor-not-allowed"
                  : "bg-violet-600 text-white hover:bg-violet-700"
              )}
            >
              Run Analysis
            </button>
          </Tooltip>

          <StepArrow />

          {/* Step 3: Insights */}
          <Tooltip text="Compute patterns, trends, and coaching insights from the analyzed games.">
            <button
              disabled={isRunning}
              onClick={() => handleAction(() => startPatterns(playerArg))}
              className={cn(
                "px-3 py-2 rounded-md text-sm font-medium transition-colors",
                isRunning
                  ? "bg-muted text-muted-foreground cursor-not-allowed"
                  : "bg-amber-600 text-white hover:bg-amber-700"
              )}
            >
              Update Insights
            </button>
          </Tooltip>

          <StepArrow />

          {/* Step 4: Coach */}
          <Tooltip text="Generate AI coaching briefs for all analyzed games that haven't been coached yet, using the selected AI provider.">
            <button
              disabled={isRunning}
              onClick={() => handleAction(() => startCoach(selectedProvider, playerArg))}
              className={cn(
                "px-3 py-2 rounded-md text-sm font-medium transition-colors",
                isRunning
                  ? "bg-muted text-muted-foreground cursor-not-allowed"
                  : "bg-rose-600 text-white hover:bg-rose-700"
              )}
            >
              Generate Coaching Briefs
            </button>
          </Tooltip>

          {/* Provider selector for coaching */}
          <select
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value)}
            disabled={isRunning}
            className="px-2 py-1.5 rounded-md border text-sm bg-background disabled:opacity-50"
          >
            <optgroup label="Cloud">
              <option value="claude">Claude</option>
              <option value="openai">ChatGPT</option>
              <option value="gemini">Gemini</option>
              <option value="grok">Grok</option>
              <option value="mistral">Mistral</option>
              <option value="deepseek">DeepSeek</option>
              <option value="qwen">Qwen</option>
            </optgroup>
            <optgroup label="Local">
              <option value="ollama">Ollama</option>
            </optgroup>
          </select>

          {/* Player selector */}
          <select
            value={selectedPlayer}
            onChange={(e) => setSelectedPlayer(e.target.value)}
            disabled={isRunning}
            className="ml-auto px-2 py-1.5 rounded-md border text-sm bg-background disabled:opacity-50"
          >
            <option value="all">All Players</option>
            {players.map((p) => (
              <option key={p.username} value={p.username}>
                {p.display_name || p.username}
              </option>
            ))}
          </select>
        </div>

        {/* Run All row */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">or</span>
          <Tooltip text="Run the full pipeline in one go: fetch new games, analyze them with Stockfish, then update all insights and patterns.">
            <button
              disabled={isRunning}
              onClick={() => handleAction(() => startRunAll(playerArg))}
              className={cn(
                "px-3 py-2 rounded-md text-sm font-medium transition-colors",
                isRunning
                  ? "bg-muted text-muted-foreground cursor-not-allowed"
                  : "bg-blue-600 text-white hover:bg-blue-700"
              )}
            >
              Run All Steps
            </button>
          </Tooltip>
        </div>

        {/* Status area */}
        {isRunning && (
          <div className="rounded-lg border bg-muted/50 p-4 space-y-2">
            <div className="flex items-center gap-2">
              <svg
                className="h-4 w-4 animate-spin text-blue-500"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              <span className="text-sm font-medium">
                {TASK_LABELS[state.task ?? ""] ?? "Working..."}
              </span>
              {stepText && (
                <span className="text-xs text-muted-foreground">({stepText})</span>
              )}
            </div>
            <p className="text-sm text-muted-foreground">{state.progress}</p>
            {/* Progress bar */}
            {progressPct != null ? (
              <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                <div
                  className="bg-blue-500 h-full rounded-full transition-all duration-500"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            ) : (
              <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                <div className="bg-blue-500/60 h-full w-1/3 rounded-full animate-pulse" />
              </div>
            )}
            {progressPct != null && (
              <p className="text-xs text-muted-foreground text-right">{progressPct}%</p>
            )}
            {/* Cancel button for coaching */}
            {state.task === "coach" && (
              <button
                disabled={cancelling}
                onClick={handleCancel}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-medium transition-colors self-start",
                  cancelling
                    ? "bg-red-400 text-white cursor-not-allowed"
                    : "bg-red-600 text-white hover:bg-red-700"
                )}
              >
                {cancelling ? "Cancelling..." : "Cancel"}
              </button>
            )}
          </div>
        )}

        {/* Complete banner */}
        {state.status === "complete" && !dismissed && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-emerald-600 dark:text-emerald-400">
                Done!
              </p>
              <p className="text-sm text-muted-foreground mt-0.5">
                {state.result ? friendlyResult(state.result) : "Task completed successfully."}
              </p>
            </div>
            <button
              onClick={dismiss}
              className="text-muted-foreground hover:text-foreground text-sm shrink-0"
              aria-label="Dismiss"
            >
              &times;
            </button>
          </div>
        )}

        {/* Error banner */}
        {(state.status === "error" || actionError) && !dismissed && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-amber-600 dark:text-amber-400">
                Something went wrong
              </p>
              <p className="text-sm text-muted-foreground mt-0.5">
                {actionError || state.error || "An unexpected error occurred."}
              </p>
            </div>
            <button
              onClick={() => {
                dismiss();
                setActionError(null);
              }}
              className="text-muted-foreground hover:text-foreground text-sm shrink-0"
              aria-label="Dismiss"
            >
              &times;
            </button>
          </div>
        )}

        {/* Automatic Updates section */}
        <AutomaticUpdates />
      </CardContent>
    </Card>
  );
}

// ── Automatic Updates sub-component ──────────────────────

function AutomaticUpdates() {
  const { state: sched, toggle, updateInterval } = useSchedule();
  const [schedError, setSchedError] = useState<string | null>(null);

  const handleToggle = async () => {
    setSchedError(null);
    try {
      await toggle(!sched.enabled);
    } catch (e: unknown) {
      setSchedError(e instanceof Error ? e.message : "Failed to toggle schedule.");
    }
  };

  const handleInterval = async (hours: number) => {
    setSchedError(null);
    try {
      await updateInterval(hours);
    } catch (e: unknown) {
      setSchedError(e instanceof Error ? e.message : "Failed to update interval.");
    }
  };

  return (
    <div className="border-t pt-4 space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm font-medium text-muted-foreground">
          Automatic Updates
        </span>

        {/* Toggle */}
        <button
          onClick={handleToggle}
          className={cn(
            "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none",
            sched.enabled ? "bg-blue-600" : "bg-muted"
          )}
          role="switch"
          aria-checked={sched.enabled}
        >
          <span
            className={cn(
              "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200",
              sched.enabled ? "translate-x-5" : "translate-x-0"
            )}
          />
        </button>

        {/* Interval selector */}
        <span className={cn("text-sm", !sched.enabled && "text-muted-foreground/50")}>
          Every
        </span>
        <select
          value={sched.interval_hours}
          onChange={(e) => handleInterval(Number(e.target.value))}
          disabled={!sched.enabled}
          className="px-2 py-1 rounded-md border text-sm bg-background disabled:opacity-50"
        >
          {INTERVAL_OPTIONS.map((h) => (
            <option key={h} value={h}>
              {h} {h === 1 ? "hour" : "hours"}
            </option>
          ))}
        </select>
      </div>

      {/* Schedule info */}
      {sched.enabled && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {sched.next_run_time && (
            <span>Next run: {relativeTime(sched.next_run_time)}</span>
          )}
          {sched.last_run_at && (
            <span>
              Last: {relativeTime(sched.last_run_at)}
              {sched.last_run_status === "success" && sched.last_run_message && (
                <span className="text-emerald-600 dark:text-emerald-400">
                  {" "}({sched.last_run_message})
                </span>
              )}
              {sched.last_run_status === "skipped" && (
                <span className="text-amber-600 dark:text-amber-400"> (skipped)</span>
              )}
              {sched.last_run_status === "error" && (
                <span className="text-red-600 dark:text-red-400"> (failed)</span>
              )}
            </span>
          )}
        </div>
      )}

      {schedError && (
        <p className="text-xs text-amber-600 dark:text-amber-400">{schedError}</p>
      )}
    </div>
  );
}
