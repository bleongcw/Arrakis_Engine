import { render, screen } from "@testing-library/react";

// v1.15.3: render tests for the TrendSummary card on the Patterns page.
//
// Catches the regression class Bernard worried about — "the summary
// silently stops rendering the motif citation paragraph after a
// future refactor." The component just maps parseTrendSummary output
// to <p> tags, so the at-risk seam is the rendering itself, not the
// parser (which has its own exhaustive coverage in summary.test.ts).
//
// We mock @/lib/api so triggerTrendSummary / fetchPatterns don't
// touch the network during render — render-only tests, no click
// interactions exercised here.

vi.mock("@/lib/api", () => ({
  triggerTrendSummary: vi.fn().mockResolvedValue({ ok: true }),
  fetchPatterns: vi.fn().mockResolvedValue({ trend_summary: null }),
}));

import { TrendSummary } from "@/components/patterns/trend-summary";

const SUMMARY_WITH_MOTIF =
  "Evan Leong, you are making solid progress over 50 games.\n\n" +
  "Your biggest area to improve is the middlegame, where your ACPL " +
  "rises to 68.1. The clearest pattern is hanging pieces: you missed " +
  "that theme 13 times and found it only 2 times in the last 30 days.\n\n" +
  "Here are 3 practice steps for you: First, do 10 minutes of hanging " +
  "piece puzzles every day. Second, play 2 slower games each week. " +
  "Third, build a small repertoire.\n\n" +
  "Keep going, Evan Leong. Every missed tactic is a clue, not a failure.";

const NOOP = () => {};

describe("TrendSummary (v1.15.3 motif-citation rendering)", () => {
  it("renders the motif citation paragraph in the DOM", () => {
    render(
      <TrendSummary
        summary={SUMMARY_WITH_MOTIF}
        player="evanleongxinyu"
        onSummaryGenerated={NOOP}
      />,
    );
    // The motif-citation paragraph must reach the DOM as a <p> tag.
    // This is the regression lock that would have warned us if the
    // parser had stripped the motif name during a future refactor.
    expect(screen.getByText(/hanging pieces/i)).toBeInTheDocument();
    // And the specific instance count from the prompt
    expect(screen.getByText(/13 times/i)).toBeInTheDocument();
    // The practice-step recommendation lands as its own paragraph
    expect(screen.getByText(/hanging piece puzzles/i)).toBeInTheDocument();
  });

  it("splits the summary into multiple paragraphs (one <p> per block)", () => {
    const { container } = render(
      <TrendSummary
        summary={SUMMARY_WITH_MOTIF}
        player="evanleongxinyu"
        onSummaryGenerated={NOOP}
      />,
    );
    // 4 paragraphs in the source separated by `\n\n` → 4 <p> tags
    const paragraphs = container.querySelectorAll("p.text-sm.leading-relaxed");
    expect(paragraphs.length).toBe(4);
  });

  it("shows the empty-state copy when summary is null", () => {
    render(
      <TrendSummary
        summary={null}
        player="evanleongxinyu"
        onSummaryGenerated={NOOP}
      />,
    );
    // Card title still renders
    expect(screen.getByText("Coaching Summary")).toBeInTheDocument();
    // Empty-state CTA copy
    expect(
      screen.getByText(/Generate an AI coaching summary/i),
    ).toBeInTheDocument();
    // The "AI-generated" provenance label must NOT appear without a summary
    expect(screen.queryByText("AI-generated")).not.toBeInTheDocument();
    // Motif text from the non-null case must NOT leak into the empty state
    expect(screen.queryByText(/hanging pieces/i)).not.toBeInTheDocument();
  });

  it("renders the 'AI-generated' provenance label when summary exists", () => {
    render(
      <TrendSummary
        summary={SUMMARY_WITH_MOTIF}
        player="evanleongxinyu"
        onSummaryGenerated={NOOP}
      />,
    );
    // User-visible signal that the text is LLM-generated
    expect(screen.getByText("AI-generated")).toBeInTheDocument();
  });
});
