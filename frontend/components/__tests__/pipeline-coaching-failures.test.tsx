import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

/** v1.28.0: coaching failures used to be invisible — /api/status has always
 *  returned `coaching_error` and types.ts has always declared it, but nothing
 *  rendered it, so a game stranded at coaching_status='error' never surfaced
 *  anywhere in the UI. These lock the indicator in place, including the
 *  retryable-vs-exhausted distinction that tells the user whether to wait for
 *  the next run or press Coach Game themselves. */

const fetchStatus = vi.fn();

vi.mock("@/lib/api", () => ({
  fetchStatus: () => fetchStatus(),
}));

vi.mock("@/hooks/use-pipeline", () => ({
  usePipeline: () => ({
    state: { status: "idle", task: null, detail: null, result: null, error: null },
    dismissed: false,
    startHarvest: vi.fn(),
    startAnalyze: vi.fn(),
    startPatterns: vi.fn(),
    startRunAll: vi.fn(),
    startCoach: vi.fn(),
    cancel: vi.fn(),
    dismiss: vi.fn(),
  }),
}));

vi.mock("@/hooks/use-schedule", () => ({
  useSchedule: () => ({
    state: {
      enabled: false,
      interval_hours: 6,
      next_run_time: null,
      last_run_at: null,
      last_run_status: null,
      last_run_message: null,
    },
    toggle: vi.fn(),
    updateInterval: vi.fn(),
    refresh: vi.fn(),
  }),
}));

vi.mock("@/app/providers", () => ({
  usePlayerContext: () => ({ players: [], currentPlayer: "evanleong" }),
}));

import { PipelineControlPanel } from "@/components/pipeline-control-panel";

const status = (over: Record<string, number> = {}) => ({
  total_games: 10,
  analysis_pending: 0,
  analyzing: 0,
  analysis_complete: 10,
  analysis_error: 0,
  coaching_pending: 0,
  coaching_complete: 10,
  coaching_error: 0,
  coaching_error_exhausted: 0,
  ...over,
});

describe("PipelineControlPanel — coaching failures (v1.28.0)", () => {
  beforeEach(() => {
    fetchStatus.mockReset();
  });

  it("shows nothing when no game has failed", async () => {
    fetchStatus.mockResolvedValue(status());
    render(<PipelineControlPanel />);
    await waitFor(() => expect(fetchStatus).toHaveBeenCalled());
    expect(screen.queryByTestId("coaching-failures")).toBeNull();
  });

  it("reports retryable failures as self-healing", async () => {
    fetchStatus.mockResolvedValue(
      status({ coaching_error: 2, coaching_error_exhausted: 0 })
    );
    render(<PipelineControlPanel />);

    const box = await screen.findByTestId("coaching-failures");
    expect(box.textContent).toContain("2 games failed coaching");
    expect(box.textContent).toContain("retry automatically");
  });

  it("calls out exhausted failures as needing a manual retry", async () => {
    fetchStatus.mockResolvedValue(
      status({ coaching_error: 3, coaching_error_exhausted: 1 })
    );
    render(<PipelineControlPanel />);

    const box = await screen.findByTestId("coaching-failures");
    expect(box.textContent).toContain("3 games failed coaching");
    expect(box.textContent).toContain("Coach Game");
  });

  it("survives a failed status poll without breaking the panel", async () => {
    // The count is advisory — a status blip must never take out the whole
    // pipeline panel.
    fetchStatus.mockRejectedValue(new Error("network"));
    render(<PipelineControlPanel />);
    await waitFor(() => expect(fetchStatus).toHaveBeenCalled());
    expect(screen.queryByTestId("coaching-failures")).toBeNull();
    expect(screen.getByText("Data Updates")).toBeTruthy();
  });
});
