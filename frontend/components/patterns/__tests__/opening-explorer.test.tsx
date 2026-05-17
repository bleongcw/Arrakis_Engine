import { render, screen, waitFor } from "@testing-library/react";
import type { OpeningGameEntry } from "@/lib/types";

vi.mock("@/components/game-detail/chess-board", () => ({
  ChessBoard: () => <div data-testid="chess-board" />,
}));
vi.mock("@/components/game-detail/move-controls", () => ({
  MoveControls: () => <div data-testid="move-controls" />,
}));

import { OpeningExplorer } from "@/components/patterns/opening-explorer";

const MOCK_BOOK = [
  {
    eco: "C50",
    name: "Italian Game",
    moves: "1. e4 e5 2. Nf3 Nc6 3. Bc4",
  },
];

const GAME_LIST: OpeningGameEntry[] = [
  { game_id: 101, date: "2026-04-15", opponent: "alice", result: "win" },
  { game_id: 102, date: "2026-04-12", opponent: "bob", result: "loss" },
  { game_id: 103, date: "2026-04-10", opponent: "carol", result: "draw" },
];

beforeAll(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("openings.json")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_BOOK),
        } as Response);
      }
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    }),
  );
});

afterAll(() => {
  vi.unstubAllGlobals();
});

describe("OpeningExplorer", () => {
  it("renders the game list with links pointing to /<username>/games/<id>", () => {
    render(
      <OpeningExplorer
        openingName="Italian Game"
        openingMoves="1. e4 e5 2. Nf3 Nc6 3. Bc4"
        gameList={GAME_LIST}
        playerUsername="eleanor"
        boardOrientation="white"
      />,
    );

    expect(screen.getByText(/Games \(3\)/)).toBeInTheDocument();

    const gameLinks = screen
      .getAllByRole("link")
      .filter((a) =>
        /\/eleanor\/games\/\d+/.test(a.getAttribute("href") ?? ""),
      );
    const hrefs = gameLinks.map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/eleanor/games/101");
    expect(hrefs).toContain("/eleanor/games/102");
    expect(hrefs).toContain("/eleanor/games/103");
  });

  it("renders the move text once parseMoveText has run", () => {
    render(
      <OpeningExplorer
        openingName="Italian Game"
        openingMoves="1. e4 e5 2. Nf3 Nc6 3. Bc4"
        gameList={GAME_LIST}
        playerUsername="eleanor"
        boardOrientation="white"
      />,
    );

    // Without a book match the raw move text is shown; with a book match
    // each SAN token is rendered as its own span. Either way, "e4" must
    // appear somewhere in the move panel.
    expect(screen.queryAllByText(/e4/).length).toBeGreaterThan(0);
  });

  it("shows the ECO badge once the opening book loads (book match)", async () => {
    render(
      <OpeningExplorer
        openingName="Italian Game"
        openingMoves="1. e4 e5 2. Nf3 Nc6 3. Bc4"
        gameList={GAME_LIST}
        playerUsername="eleanor"
        boardOrientation="white"
      />,
    );

    // The Badge text is split across nodes ("C50 — Italian Game"). Match
    // on the ECO substring once the async book fetch resolves.
    await waitFor(() =>
      expect(screen.getByText(/C50/)).toBeInTheDocument(),
    );
  });

  it("mounts the mini-board and move controls", () => {
    render(
      <OpeningExplorer
        openingName="Italian Game"
        openingMoves="1. e4 e5 2. Nf3 Nc6 3. Bc4"
        gameList={GAME_LIST}
        playerUsername="eleanor"
        boardOrientation="white"
      />,
    );
    expect(screen.getByTestId("chess-board")).toBeInTheDocument();
    expect(screen.getByTestId("move-controls")).toBeInTheDocument();
  });

  it("shows result badges for each game in the list", () => {
    render(
      <OpeningExplorer
        openingName="Italian Game"
        openingMoves="1. e4 e5 2. Nf3 Nc6 3. Bc4"
        gameList={GAME_LIST}
        playerUsername="eleanor"
        boardOrientation="white"
      />,
    );
    // W / L / D badges — one of each from GAME_LIST.
    expect(screen.getByText("W")).toBeInTheDocument();
    expect(screen.getByText("L")).toBeInTheDocument();
    expect(screen.getByText("D")).toBeInTheDocument();
  });
});
