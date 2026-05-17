import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { OpponentProfile } from "@/lib/types";

// Mock the heavy chess-board / move-controls — we only need to know they
// mounted, not that they render correct pixels. The hook tests cover
// navigation behavior end-to-end.
vi.mock("@/components/game-detail/chess-board", () => ({
  ChessBoard: () => <div data-testid="chess-board" />,
}));
vi.mock("@/components/game-detail/move-controls", () => ({
  MoveControls: () => <div data-testid="move-controls" />,
}));

import { TargetedPrep } from "@/components/hunter/targeted-prep";

const MOCK_OPENINGS = [
  {
    eco: "C50",
    name: "Italian Game",
    moves: "1. e4 e5 2. Nf3 Nc6 3. Bc4",
  },
];

function buildProfile(): OpponentProfile {
  return {
    total_games: 3,
    results: { wins: 0, losses: 3, draws: 0, win_rate: 0 },
    weaknesses: {
      white: [
        {
          name: "Italian Game",
          eco: "C50",
          total: 3,
          wins: 0,
          losses: 3,
          draws: 0,
          rate: 100,
          representative_games: [
            {
              pgn: "1. e4 e5 2. Nf3 Nc6 3. Bc4",
              date_played: "2026-05-01",
              opponent_color: "black",
              game_url: null,
            },
          ],
        },
      ],
      black: [],
    },
    strengths: { white: [], black: [] },
    meta: {
      cached: false,
      platform: "chess.com",
      username: "testopp",
      fetched_at: "2026-05-01 12:00:00",
      accumulated_games: 3,
    },
  };
}

beforeAll(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("openings.json")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_OPENINGS),
        } as Response);
      }
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    }),
  );
});

afterAll(() => {
  vi.unstubAllGlobals();
});

describe("TargetedPrep", () => {
  it("renders the opponent header and one weakness row", () => {
    render(
      <TargetedPrep profile={buildProfile()} onRefresh={() => {}} />,
    );
    expect(screen.getByText("testopp")).toBeInTheDocument();
    expect(screen.getByText("Italian Game")).toBeInTheDocument();
    expect(screen.getByText("C50")).toBeInTheDocument();
    // Row breakdown: "3 games · 3L / 0W / 0D" — the weakness variant
    // reverses the L/W order, which uniquely identifies the row body.
    expect(screen.getByText(/3L \/ 0W \/ 0D/)).toBeInTheDocument();
  });

  it("expands an opening row on click and mounts the mini-board", async () => {
    const user = userEvent.setup();
    render(
      <TargetedPrep profile={buildProfile()} onRefresh={() => {}} />,
    );
    const row = screen.getByRole("button", { name: /Italian Game/ });
    expect(row).toHaveAttribute("aria-expanded", "false");

    await user.click(row);

    await waitFor(() =>
      expect(row).toHaveAttribute("aria-expanded", "true"),
    );
    expect(screen.getByTestId("chess-board")).toBeInTheDocument();
    expect(screen.getByTestId("move-controls")).toBeInTheDocument();
    expect(screen.getByText(/Game 1 of 1/)).toBeInTheDocument();
  });

  it("expanded view's Lichess link uses the /analysis/standard/ form (v1.4.5 lock)", async () => {
    const user = userEvent.setup();
    render(
      <TargetedPrep profile={buildProfile()} onRefresh={() => {}} />,
    );
    await user.click(screen.getByRole("button", { name: /Italian Game/ }));

    const lichess = await screen.findByRole("link", {
      name: /Study this position on Lichess/,
    });
    const href = lichess.getAttribute("href") ?? "";
    expect(href).toMatch(/^https:\/\/lichess\.org\/analysis\/standard\//);
    expect(href).not.toContain("?pgn=");
  });

  it("calls onRefresh when the Refresh button is clicked", () => {
    const onRefresh = vi.fn();
    render(
      <TargetedPrep profile={buildProfile()} onRefresh={onRefresh} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Refresh/ }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it("shows the 'no games' empty state when total_games is 0", () => {
    const profile = buildProfile();
    profile.total_games = 0;
    profile.results = { wins: 0, losses: 0, draws: 0, win_rate: 0 };
    profile.weaknesses = { white: [], black: [] };
    profile.strengths = { white: [], black: [] };
    render(<TargetedPrep profile={profile} onRefresh={() => {}} />);
    expect(
      screen.getByText(/No public games found for/),
    ).toBeInTheDocument();
  });
});
