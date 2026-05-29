import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { OpponentBlindSpots } from "../opponent-blind-spots";
import type { OpponentProfile } from "@/lib/types";

// Stub the API module so the component never makes real network calls.
vi.mock("@/lib/api", () => ({
  triggerHuntScan: vi.fn(),
  fetchPipelineStatus: vi.fn(),
}));

const baseProfile: OpponentProfile = {
  total_games: 10,
  results: { wins: 4, losses: 5, draws: 1, win_rate: 40 },
  weaknesses: { white: [], black: [] },
  strengths: { white: [], black: [] },
  meta: {
    cached: true,
    platform: "chess.com",
    username: "rival",
    fetched_at: null,
    accumulated_games: 10,
  } as OpponentProfile["meta"],
};

const SCANNED: OpponentProfile = {
  ...baseProfile,
  deep_scan: { analyzed_games: 8, total_cached: 10, last_analyzed_at: "x" },
  motif_summary: {
    period_days: null as unknown as number,
    total_critical_moves: 14,
    games_analyzed: 8,
    top_missed: "fork",
    top_missed_count: 6,
    by_motif: [
      {
        motif: "fork", missed: 6, found: 1, miss_rate: 85.7,
        missed_by_phase: { opening: 1, middlegame: 4, endgame: 1 },
        dominant_missed_phase: "middlegame",
      },
    ],
  } as OpponentProfile["motif_summary"],
};

describe("OpponentBlindSpots (v1.20.0)", () => {
  beforeEach(() => vi.clearAllMocks());

  const noop = () => {};

  it("renders the Deep Scan button + time warning when never scanned", () => {
    render(
      <OpponentBlindSpots
        opponent="rival"
        platform="chess.com"
        profile={baseProfile}
        onScanComplete={noop}
      />,
    );
    expect(
      screen.getByRole("button", { name: /Deep Scan \(Stockfish\)/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/takes several minutes/i)).toBeInTheDocument();
    expect(
      screen.getByText(/No deep scan yet/i),
    ).toBeInTheDocument();
  });

  it("renders the blind-spots card + headline after a scan", () => {
    render(
      <OpponentBlindSpots
        opponent="rival"
        platform="chess.com"
        profile={SCANNED}
        onScanComplete={noop}
      />,
    );
    // Deterministic headline mentions the top missed motif + miss rate.
    const headline = screen.getByTestId("blind-spots-headline");
    expect(headline.textContent).toMatch(/Bait/i);
    expect(headline.textContent).toContain("86%");
    // Re-scan affordance once games have been analyzed.
    expect(
      screen.getByRole("button", { name: /Re-scan/ }),
    ).toBeInTheDocument();
    // The shared MotifThemes card renders the fork row.
    expect(screen.getAllByText(/fork/i).length).toBeGreaterThanOrEqual(1);
  });

  it("does not render the headline when there are no analyzed games", () => {
    render(
      <OpponentBlindSpots
        opponent="rival"
        platform="chess.com"
        profile={baseProfile}
        onScanComplete={noop}
      />,
    );
    expect(screen.queryByTestId("blind-spots-headline")).not.toBeInTheDocument();
  });
});
