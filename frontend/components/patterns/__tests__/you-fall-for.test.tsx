import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { TrapEntry } from "@/lib/types";

vi.mock("@/components/game-detail/chess-board", () => ({
  ChessBoard: () => <div data-testid="chess-board" />,
}));
vi.mock("@/components/game-detail/move-controls", () => ({
  MoveControls: () => <div data-testid="move-controls" />,
}));

import { YouFallFor } from "@/components/patterns/you-fall-for";

const MOCK_TRAPS = [
  {
    eco: "C57",
    name: "Fried Liver Attack",
    moves_san: "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. Ng5 d5 5. exd5 Nxd5 6. Nxf7",
    moves: ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5", "d5", "exd5", "Nxd5", "Nxf7"],
    depth: 11,
  },
];

function buildFallEntry(): TrapEntry {
  return {
    name: "Fried Liver Attack",
    eco: "C57",
    count: 2,
    total: 2,
    wins: 0,
    losses: 2,
    draws: 0,
    win_rate: 0,
    recent_dates: ["2026-04-15", "2026-04-08"],
    recent_game_ids: [101, 102],
    frequency_label: "Rare",
    trend: "flat",
  };
}

beforeAll(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("traps.json")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_TRAPS),
        } as Response);
      }
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    }),
  );
});

afterAll(() => {
  vi.unstubAllGlobals();
});

describe("YouFallFor", () => {
  it("renders trap rows for the falls list", () => {
    render(<YouFallFor falls={[buildFallEntry()]} player="eleanor" />);
    expect(screen.getByText("Fried Liver Attack")).toBeInTheDocument();
    expect(screen.getByText("C57")).toBeInTheDocument();
    expect(screen.getByText("Rare")).toBeInTheDocument();
  });

  it("expands a trap row on click and shows recent-game links to /<player>/games/<id>", async () => {
    const user = userEvent.setup();
    render(<YouFallFor falls={[buildFallEntry()]} player="eleanor" />);

    const row = screen.getByRole("button", { name: /Fried Liver Attack/ });
    await user.click(row);
    await waitFor(() =>
      expect(row).toHaveAttribute("aria-expanded", "true"),
    );

    // Recent-game links should point to /eleanor/games/101 and /102
    const gameLinks = screen
      .getAllByRole("link")
      .filter((a) => /\/eleanor\/games\/\d+/.test(a.getAttribute("href") ?? ""));
    const hrefs = gameLinks.map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/eleanor/games/101");
    expect(hrefs).toContain("/eleanor/games/102");
  });

  it("expanded view's Lichess link uses the /analysis/standard/ form (v1.4.5 lock)", async () => {
    const user = userEvent.setup();
    render(<YouFallFor falls={[buildFallEntry()]} player="eleanor" />);

    await user.click(
      screen.getByRole("button", { name: /Fried Liver Attack/ }),
    );

    // The Lichess link only renders once libraryTrap loads (async fetch).
    const lichess = await screen.findByRole("link", {
      name: /Study this position on Lichess/,
    });
    const href = lichess.getAttribute("href") ?? "";
    expect(href).toMatch(/^https:\/\/lichess\.org\/analysis\/standard\//);
    expect(href).not.toContain("?pgn=");
  });

  it("shows the empty state when neither arsenal nor falls have entries", () => {
    render(<YouFallFor arsenal={[]} falls={[]} player="eleanor" />);
    expect(
      screen.getByText(/No named trap patterns detected yet/),
    ).toBeInTheDocument();
  });
});
