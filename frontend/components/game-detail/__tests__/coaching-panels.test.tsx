import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CoachingPanels } from "../coaching-panels";
import type { GameCoaching } from "@/lib/types";

/** v1.13.0: confirms the new sectioned renderer in the "Feedback to the
 *  Player" card works for both v1.13.0+ entries (5 sections) and legacy
 *  pre-v1.13.0 entries (single block, no headings). */

const baseCoaching: Partial<GameCoaching> = {
  id: 1,
  game_id: 1,
  provider: "openai:gpt-5.5-pro-2026-04-23",
  narrative: "n",
  key_lesson: "k",
  practical_focus: "p",
  critical_moments: null,
  critical_moments_json: null,
  opening_analysis: null,
  opening_analysis_json: null,
  coach_notes: "c",
};

const FIVE_SECTION_FEEDBACK = `## ♟ Opening
Italian Game played cleanly through move 4.

## ⚔ Middlegame
Move 18 was a mistake — trading the good bishop for an inactive knight.

## ♔ Endgame
This game ended in the middlegame — no endgame technique needed today.

## 🪤 Watch Out For (Trap Awareness)
Watch for the Fried Liver Attack.

## 🎯 Top 3 Improvements
1. Find a knight outpost before move 15.
2. Check piece activity every move.
3. Look for forks before quiet moves.`;

describe("CoachingPanels — v1.13.0 sectioned player_feedback", () => {
  it("renders all 5 section headings for a v1.13.0 entry", () => {
    const coaching = {
      ...baseCoaching,
      player_feedback: FIVE_SECTION_FEEDBACK,
    } as GameCoaching;
    render(<CoachingPanels coaching={coaching} />);

    expect(screen.getByText("♟ Opening")).toBeInTheDocument();
    expect(screen.getByText("⚔ Middlegame")).toBeInTheDocument();
    expect(screen.getByText("♔ Endgame")).toBeInTheDocument();
    expect(screen.getByText("🪤 Watch Out For (Trap Awareness)")).toBeInTheDocument();
    expect(screen.getByText("🎯 Top 3 Improvements")).toBeInTheDocument();
  });

  it("renders section bodies under their respective headings", () => {
    const coaching = {
      ...baseCoaching,
      player_feedback: FIVE_SECTION_FEEDBACK,
    } as GameCoaching;
    render(<CoachingPanels coaching={coaching} />);

    expect(screen.getByText(/Italian Game played cleanly/)).toBeInTheDocument();
    expect(screen.getByText(/Move 18 was a mistake/)).toBeInTheDocument();
    expect(screen.getByText(/Watch for the Fried Liver Attack/)).toBeInTheDocument();
  });

  it("legacy single-block feedback renders with NO headings", () => {
    const legacy =
      "Evan, you played a great game. Keep working on knight outposts!";
    const coaching = {
      ...baseCoaching,
      player_feedback: legacy,
    } as GameCoaching;
    render(<CoachingPanels coaching={coaching} />);

    // The card title "Feedback to the Player" should still be there
    expect(screen.getByText("Feedback to the Player")).toBeInTheDocument();
    // The legacy body renders
    expect(screen.getByText(/Evan, you played a great game/)).toBeInTheDocument();
    // None of the v1.13.0 emoji headings should appear
    expect(screen.queryByText("♟ Opening")).not.toBeInTheDocument();
    expect(screen.queryByText("🎯 Top 3 Improvements")).not.toBeInTheDocument();
  });

  it("omits the Feedback to the Player card entirely when player_feedback is null", () => {
    const coaching = {
      ...baseCoaching,
      player_feedback: null,
    } as GameCoaching;
    render(<CoachingPanels coaching={coaching} />);

    expect(screen.queryByText("Feedback to the Player")).not.toBeInTheDocument();
  });
});

// ─── v1.14.0: tactical motif badges on Critical Moments cards ───

describe("CoachingPanels — Critical Moments motif badges (v1.14.0)", () => {
  it("renders motif badges when motifs_missed is populated", () => {
    const coaching = {
      ...baseCoaching,
      critical_moments: [
        {
          move_number: 18,
          side: "black",
          what_happened: "You moved your queen away from the fight.",
          what_was_better: "Nxf7 would have won the queen.",
          move_played: "Qh4",
          best_move: "Nxf7",
          motifs_found: ["fork"],
          motifs_missed: ["fork"],
        },
      ],
    } as GameCoaching;
    render(<CoachingPanels coaching={coaching} />);

    expect(screen.getByText("Critical Moments")).toBeInTheDocument();
    // Missed badge appears as "🍴 fork" — getAllByText since "fork" appears
    // in both the missed and found chips
    const forkBadges = screen.getAllByText(/🍴 fork/);
    expect(forkBadges.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("missed:")).toBeInTheDocument();
  });

  it("renders nothing motif-related when arrays are empty (legacy entries)", () => {
    const coaching = {
      ...baseCoaching,
      critical_moments: [
        {
          move_number: 18,
          side: "black",
          what_happened: "x",
          what_was_better: "y",
          move_played: "Qh4",
          best_move: "Nd4",
          // No motifs_found / motifs_missed (pre-v1.14.0 entry)
        },
      ],
    } as GameCoaching;
    render(<CoachingPanels coaching={coaching} />);

    expect(screen.queryByText("missed:")).not.toBeInTheDocument();
    expect(screen.queryByText("found:")).not.toBeInTheDocument();
    expect(screen.queryByText(/🍴/)).not.toBeInTheDocument();
  });

  it("renders only found chips when nothing was missed", () => {
    const coaching = {
      ...baseCoaching,
      critical_moments: [
        {
          move_number: 25,
          side: "white",
          what_happened: "Solid move.",
          what_was_better: "—",
          move_played: "Nxe5",
          best_move: "Nxe5",
          motifs_found: ["hanging_piece"],
          motifs_missed: [],
        },
      ],
    } as GameCoaching;
    render(<CoachingPanels coaching={coaching} />);

    expect(screen.getByText("found:")).toBeInTheDocument();
    expect(screen.queryByText("missed:")).not.toBeInTheDocument();
    expect(screen.getByText(/🎁 hanging piece/)).toBeInTheDocument();
  });

  it("uses the correct emoji+label for each motif identifier", () => {
    const coaching = {
      ...baseCoaching,
      critical_moments: [
        {
          move_number: 30,
          side: "white",
          what_happened: "x",
          what_was_better: "y",
          move_played: "a",
          best_move: "b",
          motifs_found: [
            "fork", "pin", "skewer", "discovered_check",
            "mate_threat", "removing_defender",
            "hanging_piece", "trapped_piece",
          ],
          motifs_missed: [],
        },
      ],
    } as GameCoaching;
    render(<CoachingPanels coaching={coaching} />);

    expect(screen.getByText(/🍴 fork/)).toBeInTheDocument();
    expect(screen.getByText(/📌 pin/)).toBeInTheDocument();
    expect(screen.getByText(/🗡 skewer/)).toBeInTheDocument();
    expect(screen.getByText(/💥 discovered check/)).toBeInTheDocument();
    expect(screen.getByText(/🎯 mate threat/)).toBeInTheDocument();
    expect(screen.getByText(/🛡 removing defender/)).toBeInTheDocument();
    expect(screen.getByText(/🎁 hanging piece/)).toBeInTheDocument();
    expect(screen.getByText(/🪤 trapped piece/)).toBeInTheDocument();
  });
});
