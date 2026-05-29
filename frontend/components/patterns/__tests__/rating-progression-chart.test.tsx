import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { GameListItem } from "@/lib/types";

// Recharts is heavy and the chart internals don't matter for these smoke
// tests — what matters is structural: how many SinglePlatformCharts are
// rendered, and which platform toggle buttons appear.
vi.mock("recharts", () => ({
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  Tooltip: () => null,
  Brush: () => null, // v1.18.3: date-range zoom
}));

import { RatingProgressionChart } from "@/components/patterns/rating-progression-chart";

function makeGame(overrides: Partial<GameListItem>): GameListItem {
  return {
    id: 1,
    player_id: 1,
    game_url: "",
    player_color: "white",
    player_rating: 1100,
    opponent_rating: 1100,
    opponent_username: "opp",
    result: "win",
    time_control: "600",
    time_class: "rapid",
    date_played: "2026-04-01",
    analysis_status: "complete",
    coaching_status: "complete",
    platform: "chess.com",
    username: "testkid",
    display_name: "TestKid",
    tier: "elementary",
    tier_label: "Elementary",
    tier_icon: "📘",
    ...overrides,
  } as GameListItem;
}

describe("RatingProgressionChart — platform splitting (v1.7.2)", () => {
  it("hides the platform toggle when the player only has chess.com games", () => {
    const games = Array.from({ length: 5 }, (_, i) =>
      makeGame({
        id: i + 1,
        date_played: `2026-04-0${i + 1}`,
        platform: "chess.com",
      }),
    );
    render(<RatingProgressionChart games={games} />);

    // No platform toggle UI should appear
    expect(screen.queryByRole("button", { name: /^Both$/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /^lichess$/i })).toBeNull();
    // Exactly one chart should render
    expect(screen.getAllByTestId("line-chart")).toHaveLength(1);
  });

  it("hides the platform toggle when the player only has lichess games", () => {
    const games = Array.from({ length: 3 }, (_, i) =>
      makeGame({
        id: i + 1,
        date_played: `2026-04-0${i + 1}`,
        platform: "lichess",
        player_rating: 1500,  // typical lichess rating range
      }),
    );
    render(<RatingProgressionChart games={games} />);

    expect(screen.queryByRole("button", { name: /^Both$/i })).toBeNull();
    expect(screen.getAllByTestId("line-chart")).toHaveLength(1);
  });

  it("shows the platform toggle when player has both platforms", () => {
    const games = [
      ...Array.from({ length: 10 }, (_, i) =>
        makeGame({
          id: i + 1,
          date_played: `2026-04-${String(i + 1).padStart(2, "0")}`,
          platform: "chess.com",
        }),
      ),
      ...Array.from({ length: 3 }, (_, i) =>
        makeGame({
          id: 100 + i,
          date_played: `2026-04-${String(i + 15).padStart(2, "0")}`,
          platform: "lichess",
          player_rating: 1500,
        }),
      ),
    ];
    render(<RatingProgressionChart games={games} />);

    expect(screen.getByRole("button", { name: /^Both$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^chess\.com$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^lichess$/i })).toBeInTheDocument();
  });

  it("defaults to the most-played platform when both exist", () => {
    // chess.com has 10 games, lichess has 3 → default should be chess.com
    const games = [
      ...Array.from({ length: 10 }, (_, i) =>
        makeGame({
          id: i + 1,
          date_played: `2026-04-${String(i + 1).padStart(2, "0")}`,
          platform: "chess.com",
        }),
      ),
      ...Array.from({ length: 3 }, (_, i) =>
        makeGame({
          id: 100 + i,
          date_played: `2026-04-${String(i + 15).padStart(2, "0")}`,
          platform: "lichess",
          player_rating: 1500,
        }),
      ),
    ];
    render(<RatingProgressionChart games={games} />);

    // Only one chart visible by default (most-played platform, not "Both")
    expect(screen.getAllByTestId("line-chart")).toHaveLength(1);
    // The "chess.com" toggle button should be in the active state. In our
    // styling the active button has `bg-primary` class; smoke-test it.
    const chessBtn = screen.getByRole("button", { name: /^chess\.com$/i });
    expect(chessBtn.className).toMatch(/bg-primary/);
  });

  it("renders two stacked charts when 'Both' is selected", async () => {
    const user = userEvent.setup();
    const games = [
      ...Array.from({ length: 10 }, (_, i) =>
        makeGame({
          id: i + 1,
          date_played: `2026-04-${String(i + 1).padStart(2, "0")}`,
          platform: "chess.com",
        }),
      ),
      ...Array.from({ length: 3 }, (_, i) =>
        makeGame({
          id: 100 + i,
          date_played: `2026-04-${String(i + 15).padStart(2, "0")}`,
          platform: "lichess",
          player_rating: 1500,
        }),
      ),
    ];
    render(<RatingProgressionChart games={games} />);

    // Default: 1 chart
    expect(screen.getAllByTestId("line-chart")).toHaveLength(1);

    // Click "Both"
    await user.click(screen.getByRole("button", { name: /^Both$/i }));

    // Now: 2 charts stacked
    expect(screen.getAllByTestId("line-chart")).toHaveLength(2);
  });

  it("returns null when there are no rated games at all", () => {
    const games = [
      makeGame({ player_rating: null }),
      makeGame({ id: 2, player_rating: null }),
    ];
    const { container } = render(<RatingProgressionChart games={games} />);
    expect(container.firstChild).toBeNull();
  });
});

describe("RatingProgressionChart — time-class smart default (v1.7.3)", () => {
  it("defaults to the most-played time class instead of 'All'", () => {
    // 8 rapid games + 3 daily games → default should be 'rapid', not 'All'
    const games = [
      ...Array.from({ length: 8 }, (_, i) =>
        makeGame({
          id: i + 1,
          date_played: `2026-04-${String(i + 1).padStart(2, "0")}`,
          time_class: "rapid",
          player_rating: 1100,
        }),
      ),
      ...Array.from({ length: 3 }, (_, i) =>
        makeGame({
          id: 100 + i,
          date_played: `2026-04-${String(i + 15).padStart(2, "0")}`,
          time_class: "daily",
          player_rating: 600,  // daily pool — much lower
        }),
      ),
    ];
    render(<RatingProgressionChart games={games} />);

    const rapidBtn = screen.getByRole("button", { name: /^Rapid$/i });
    expect(rapidBtn.className).toMatch(/bg-primary/);
    // 'All' should NOT be the active default
    const allBtn = screen.queryByRole("button", { name: /All/i });
    if (allBtn) {
      expect(allBtn.className).not.toMatch(/bg-primary/);
    }
  });

  it("hides chips for time classes the player has no games in", () => {
    // Only rapid games → only "Rapid" chip should appear (no bullet/blitz/daily)
    const games = Array.from({ length: 5 }, (_, i) =>
      makeGame({
        id: i + 1,
        date_played: `2026-04-0${i + 1}`,
        time_class: "rapid",
      }),
    );
    render(<RatingProgressionChart games={games} />);

    expect(screen.getByRole("button", { name: /^Rapid$/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Bullet$/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Blitz$/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Daily$/i })).toBeNull();
  });

  it("hides the 'All' chip when the player has only one time class", () => {
    const games = Array.from({ length: 5 }, (_, i) =>
      makeGame({
        id: i + 1,
        date_played: `2026-04-0${i + 1}`,
        time_class: "rapid",
      }),
    );
    render(<RatingProgressionChart games={games} />);

    // Only one time class → 'All' would be a duplicate, so it's hidden
    expect(screen.queryByRole("button", { name: /All/i })).toBeNull();
  });

  it("shows the 'All' chip with a warning marker when multiple time classes exist", () => {
    const games = [
      ...Array.from({ length: 5 }, (_, i) =>
        makeGame({
          id: i + 1,
          date_played: `2026-04-0${i + 1}`,
          time_class: "rapid",
        }),
      ),
      ...Array.from({ length: 3 }, (_, i) =>
        makeGame({
          id: 100 + i,
          date_played: `2026-04-1${i}`,
          time_class: "daily",
          player_rating: 600,
        }),
      ),
    ];
    render(<RatingProgressionChart games={games} />);

    // 'All' chip is present and contains the warning glyph (⚠)
    const allBtn = screen.getByRole("button", { name: /All/i });
    expect(allBtn).toBeInTheDocument();
    expect(allBtn.textContent).toContain("⚠");
    // The warning explanation is in the title attribute
    expect(allBtn.getAttribute("title")).toMatch(/mixes rating pools/i);
  });
});
