import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { OpeningTargets } from "../opening-targets";
import type { OpeningTarget } from "@/lib/types";

const target: OpeningTarget = {
  opening: "Italian Game", eco: "C50", color: "white",
  opponent_count: 5, total_games: 20, outcome_games: 16,
  agg_rate: 80, opponents: ["a", "b", "c", "d", "e"],
};
const caution: OpeningTarget = {
  opening: "Sicilian Najdorf", eco: "B90", color: "black",
  opponent_count: 4, total_games: 18, outcome_games: 13,
  agg_rate: 72, opponents: ["a", "c", "f", "g"],
};

describe("OpeningTargets (v1.21.0)", () => {
  it("renders the headline from the top target", () => {
    render(<OpeningTargets targets={[target]} cautions={[caution]} />);
    const headline = screen.getByTestId("opening-targets-headline");
    expect(headline.textContent).toMatch(/Prep the Italian Game/);
    expect(headline.textContent).toContain("5 of this field");
  });

  it("renders prep + avoid lists", () => {
    render(<OpeningTargets targets={[target]} cautions={[caution]} />);
    const prep = screen.getByTestId("prep-list");
    const avoid = screen.getByTestId("avoid-list");
    expect(prep.textContent).toContain("Italian Game");
    expect(avoid.textContent).toContain("Sicilian Najdorf");
  });

  it("shows an empty-state headline when no targets", () => {
    render(<OpeningTargets targets={[]} cautions={[]} />);
    expect(
      screen.queryByTestId("opening-targets-headline"),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/No shared opening targets yet/i)).toBeInTheDocument();
  });
});
