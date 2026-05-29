import { render, screen } from "@testing-library/react";
import { MotifThemes } from "@/components/patterns/motif-themes";
import type { MotifSummaryData } from "@/components/patterns/motif-themes";

/** v1.15.0: Tactical Themes card driven by stats.motif_summary. */

const FULL_DATA: MotifSummaryData = {
  period_days: 30,
  total_critical_moves: 12,
  top_missed: "fork",
  top_missed_count: 8,
  // v1.16.0:
  top_missed_dominant_phase: "middlegame",
  by_motif: [
    {
      motif: "fork", missed: 8, found: 3, miss_rate: 72.7,
      // v1.16.0: fork concentrated in middlegame (6 of 8)
      missed_by_phase: { opening: 1, middlegame: 6, endgame: 1 },
      found_by_phase: { opening: 0, middlegame: 2, endgame: 1 },
      dominant_missed_phase: "middlegame",
    },
    {
      motif: "removing_defender", missed: 4, found: 1, miss_rate: 80.0,
      // v1.16.0: balanced across phases — no dominance
      missed_by_phase: { opening: 1, middlegame: 2, endgame: 1 },
      found_by_phase: { opening: 0, middlegame: 1, endgame: 0 },
      dominant_missed_phase: null,
    },
    {
      motif: "pin", missed: 2, found: 5, miss_rate: 28.6,
      // v1.16.0: total < 3 misses → no dominance
      missed_by_phase: { opening: 0, middlegame: 2, endgame: 0 },
      found_by_phase: { opening: 2, middlegame: 2, endgame: 1 },
      dominant_missed_phase: null,
    },
    // Zero-count rows must be filtered out
    {
      motif: "skewer", missed: 0, found: 0, miss_rate: 0.0,
      missed_by_phase: { opening: 0, middlegame: 0, endgame: 0 },
      found_by_phase: { opening: 0, middlegame: 0, endgame: 0 },
      dominant_missed_phase: null,
    },
    {
      motif: "trapped_piece", missed: 0, found: 0, miss_rate: 0.0,
      missed_by_phase: { opening: 0, middlegame: 0, endgame: 0 },
      found_by_phase: { opening: 0, middlegame: 0, endgame: 0 },
      dominant_missed_phase: null,
    },
  ],
};

describe("MotifThemes (v1.15.0 Patterns card)", () => {
  it("renders nothing when data is undefined (pre-v1.15.0 patterns row)", () => {
    const { container } = render(<MotifThemes data={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the empty-state copy when total_critical_moves is 0", () => {
    render(
      <MotifThemes
        data={{
          period_days: 30,
          total_critical_moves: 0,
          top_missed: null,
          top_missed_count: 0,
          by_motif: [],
        }}
      />,
    );
    expect(screen.getByText("Tactical Themes")).toBeInTheDocument();
    expect(
      screen.getByText(/No tactical themes detected yet/i),
    ).toBeInTheDocument();
    // The top-missed hero number must NOT render when count is 0
    expect(screen.queryByText("8")).not.toBeInTheDocument();
  });

  it("renders the top-missed hero number + motif label", () => {
    render(<MotifThemes data={FULL_DATA} />);
    // Hero number — appears multiple times in the doc (hero + row stat
    // line). Just confirm "8" shows up at all.
    const eights = screen.getAllByText(/^8$/);
    expect(eights.length).toBeGreaterThanOrEqual(1);
    // Hero label (motif name appears in hero + in row — getAllByText)
    const forkMatches = screen.getAllByText(/fork/i);
    expect(forkMatches.length).toBeGreaterThanOrEqual(1);
  });

  it("renders one row per non-zero motif, with emoji + label", () => {
    render(<MotifThemes data={FULL_DATA} />);
    // Three non-zero motifs in FULL_DATA → three rendered rows
    expect(screen.getAllByText(/🍴 fork/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/🛡 removing defender/)).toBeInTheDocument();
    expect(screen.getByText(/📌 pin/)).toBeInTheDocument();
    // Zero-count motifs MUST be filtered out
    expect(screen.queryByText(/🗡 skewer/)).not.toBeInTheDocument();
    expect(screen.queryByText(/🪤 trapped piece/)).not.toBeInTheDocument();
  });

  it("displays per-row miss-rate + counts", () => {
    render(<MotifThemes data={FULL_DATA} />);
    // "8 found · 4 missed · 80% miss rate" or similar — assert the
    // numbers + 'miss rate' label show up somewhere
    expect(screen.getByText(/8 missed/)).toBeInTheDocument();
    expect(screen.getByText(/4 missed/)).toBeInTheDocument();
    expect(screen.getByText(/80% miss rate/)).toBeInTheDocument();
  });

  it("renders rows sorted by missed-desc", () => {
    render(<MotifThemes data={FULL_DATA} />);
    // Each row has a label like "🍴 fork" — read them in document order
    // to confirm fork (8) > removing_defender (4) > pin (2).
    const labels = screen.getAllByText(
      /(🍴 fork|🛡 removing defender|📌 pin)/,
    );
    // The header hero also reads "🍴 fork" so labels[0] is the hero.
    // The row labels start at the next match. Either way, fork must
    // appear before removing_defender, which must appear before pin.
    const text = labels.map((el) => el.textContent || "").join(" || ");
    const forkIdx = text.indexOf("🍴 fork");
    const rdIdx = text.indexOf("🛡 removing defender");
    const pinIdx = text.indexOf("📌 pin");
    expect(forkIdx).toBeLessThan(rdIdx);
    expect(rdIdx).toBeLessThan(pinIdx);
  });
});

// ─── v1.16.0: phase × motif breakdown line ───────────────────────────

describe("MotifThemes — v1.16.0 phase breakdown", () => {
  it("renders the phase breakdown line under each non-zero motif row", () => {
    render(<MotifThemes data={FULL_DATA} />);
    // fork row has phase counts {opening 1, middlegame 6, endgame 1}
    const forkLine = screen.getByTestId("motif-phase-line-fork");
    expect(forkLine).toBeInTheDocument();
    expect(forkLine.textContent).toContain("Opening 1");
    expect(forkLine.textContent).toContain("Middlegame 6");
    expect(forkLine.textContent).toContain("Endgame 1");
  });

  it("highlights the dominant phase span for motifs that have one", () => {
    render(<MotifThemes data={FULL_DATA} />);
    // fork's dominant phase is middlegame → rendered with the
    // motif-phase-dominant-fork test id and 🎯 prefix
    const dominantSpan = screen.getByTestId("motif-phase-dominant-fork");
    expect(dominantSpan).toBeInTheDocument();
    expect(dominantSpan.textContent).toContain("Middlegame");
    expect(dominantSpan.textContent).toContain("🎯");
  });

  it("does not highlight any phase for balanced or low-count motifs", () => {
    render(<MotifThemes data={FULL_DATA} />);
    // removing_defender has missed_by_phase {1,2,1} → no dominance
    expect(
      screen.queryByTestId("motif-phase-dominant-removing_defender"),
    ).not.toBeInTheDocument();
    // pin's total missed is 2 (<3 signal threshold) → no dominance
    expect(
      screen.queryByTestId("motif-phase-dominant-pin"),
    ).not.toBeInTheDocument();
    // But their breakdown lines still render with the counts
    expect(
      screen.getByTestId("motif-phase-line-removing_defender"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("motif-phase-line-pin")).toBeInTheDocument();
  });

  it("does not render the phase line when missed_by_phase is missing (pre-v1.16.0 row)", () => {
    // Synthesize a pre-v1.16.0-shaped row: no phase fields present
    const preV16Data: MotifSummaryData = {
      period_days: 30,
      total_critical_moves: 5,
      top_missed: "fork",
      top_missed_count: 5,
      by_motif: [
        // No missed_by_phase / found_by_phase / dominant_missed_phase
        { motif: "fork", missed: 5, found: 0, miss_rate: 100.0 },
      ],
    };
    render(<MotifThemes data={preV16Data} />);
    // Row itself still renders
    const forkMatches = screen.getAllByText(/fork/i);
    expect(forkMatches.length).toBeGreaterThanOrEqual(1);
    // But no phase breakdown line
    expect(
      screen.queryByTestId("motif-phase-line-fork"),
    ).not.toBeInTheDocument();
  });

  // v1.19.0: recurring-weakness escalation badge.
  it("renders an escalation badge with tier + N of M games + streak", () => {
    const data: MotifSummaryData = {
      period_days: 30,
      total_critical_moves: 30,
      games_with_motif_data: 9,
      top_missed: "fork",
      top_missed_count: 12,
      by_motif: [
        {
          motif: "fork", missed: 12, found: 2, miss_rate: 85.7,
          missed_by_phase: { opening: 1, middlegame: 9, endgame: 2 },
          found_by_phase: { opening: 0, middlegame: 1, endgame: 1 },
          dominant_missed_phase: "middlegame",
          missed_games: 9, streak: 3, escalation: "priority",
        },
      ],
      escalated_weaknesses: [
        {
          motif: "fork", escalation: "priority",
          missed_games: 9, streak: 3, dominant_missed_phase: "middlegame",
        },
      ],
    };
    render(<MotifThemes data={data} />);
    const badge = screen.getByTestId("motif-escalation-fork");
    expect(badge).toBeInTheDocument();
    expect(badge.textContent).toContain("missed in 9 of 9 games");
    expect(badge.textContent).toContain("3 in a row");
  });

  it("omits the streak suffix when streak < 2", () => {
    const data: MotifSummaryData = {
      period_days: 30,
      total_critical_moves: 20,
      games_with_motif_data: 10,
      top_missed: "pin",
      top_missed_count: 5,
      by_motif: [
        {
          motif: "pin", missed: 5, found: 1, miss_rate: 83.3,
          missed_by_phase: { opening: 1, middlegame: 3, endgame: 1 },
          found_by_phase: { opening: 0, middlegame: 1, endgame: 0 },
          dominant_missed_phase: null,
          missed_games: 5, streak: 0, escalation: "focus",
        },
      ],
    };
    render(<MotifThemes data={data} />);
    const badge = screen.getByTestId("motif-escalation-pin");
    expect(badge.textContent).toContain("missed in 5 of 10 games");
    expect(badge.textContent).not.toContain("in a row");
  });

  it("renders no escalation badge when escalation is none or absent", () => {
    const data: MotifSummaryData = {
      period_days: 30,
      total_critical_moves: 10,
      games_with_motif_data: 6,
      top_missed: "fork",
      top_missed_count: 2,
      by_motif: [
        {
          motif: "fork", missed: 2, found: 3, miss_rate: 40.0,
          missed_by_phase: { opening: 1, middlegame: 1, endgame: 0 },
          found_by_phase: { opening: 1, middlegame: 1, endgame: 1 },
          dominant_missed_phase: null,
          missed_games: 2, streak: 0, escalation: "none",
        },
        // No escalation field at all (pre-v1.19.0 row)
        { motif: "pin", missed: 1, found: 4, miss_rate: 20.0 },
      ],
    };
    render(<MotifThemes data={data} />);
    expect(
      screen.queryByTestId("motif-escalation-fork"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("motif-escalation-pin"),
    ).not.toBeInTheDocument();
  });
});
