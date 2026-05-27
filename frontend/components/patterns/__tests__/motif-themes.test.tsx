import { render, screen } from "@testing-library/react";
import { MotifThemes } from "@/components/patterns/motif-themes";
import type { MotifSummaryData } from "@/components/patterns/motif-themes";

/** v1.15.0: Tactical Themes card driven by stats.motif_summary. */

const FULL_DATA: MotifSummaryData = {
  period_days: 30,
  total_critical_moves: 12,
  top_missed: "fork",
  top_missed_count: 8,
  by_motif: [
    { motif: "fork", missed: 8, found: 3, miss_rate: 72.7 },
    { motif: "removing_defender", missed: 4, found: 1, miss_rate: 80.0 },
    { motif: "pin", missed: 2, found: 5, miss_rate: 28.6 },
    // Zero-count rows must be filtered out
    { motif: "skewer", missed: 0, found: 0, miss_rate: 0.0 },
    { motif: "trapped_piece", missed: 0, found: 0, miss_rate: 0.0 },
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
