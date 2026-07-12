import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Player } from "@/lib/types";

/** v1.16.1: PlayerSelector routes by slug, not chess.com username.
 *
 *  Mocks usePathname / useRouter and the usePlayerContext hook so we
 *  can assert on the exact path passed to router.push(). */

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/evanleong/patterns",
}));

const mockSetCurrentPlayer = vi.fn();
const mockPlayers: Player[] = [
  {
    id: 1,
    username: "nevergiveupgreatthings",  // chess.com handle
    slug: "evanleong",                   // v1.16.1 URL slug
    display_name: "Evan Leong",
    age: 9, rating: 1100,
    fide_id: null, fide_rating: null, fide_rating_classical: null, fide_rating_rapid: null, fide_rating_blitz: null, lichess_username: null,
    tier: "developing", tier_label: "Developing", tier_icon: "🌱",
    tier_description: "", latest_rating: 1100,
    chesscom_url: "", lichess_url: null, fide_url: null,
    chesscom_games: 0, lichess_games: 0,
  },
  {
    id: 2,
    username: "sixsevenequals42",
    slug: "estellaleong",
    display_name: "Estella Leong",
    age: 7, rating: 600,
    fide_id: null, fide_rating: null, fide_rating_classical: null, fide_rating_rapid: null, fide_rating_blitz: null, lichess_username: null,
    tier: "developing", tier_label: "Developing", tier_icon: "🌱",
    tier_description: "", latest_rating: 600,
    chesscom_url: "", lichess_url: null, fide_url: null,
    chesscom_games: 0, lichess_games: 0,
  },
  // Pre-v1.16.1-shaped player with no slug — must fall back to username
  {
    id: 3,
    username: "legacyplayer",
    display_name: "Legacy Player",
    age: null, rating: null,
    fide_id: null, fide_rating: null, fide_rating_classical: null, fide_rating_rapid: null, fide_rating_blitz: null, lichess_username: null,
    tier: "developing", tier_label: "Developing", tier_icon: "🌱",
    tier_description: "", latest_rating: null,
    chesscom_url: "", lichess_url: null, fide_url: null,
    chesscom_games: 0, lichess_games: 0,
  },
];

vi.mock("@/app/providers", () => ({
  usePlayerContext: () => ({
    players: mockPlayers,
    currentPlayer: "evanleong",
    setCurrentPlayer: mockSetCurrentPlayer,
  }),
}));

import { PlayerSelector } from "@/components/player-selector";

describe("PlayerSelector — v1.16.1 slug routing", () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockSetCurrentPlayer.mockClear();
  });

  it("renders display_name labels for each player", () => {
    render(<PlayerSelector />);
    // Desktop labels render display_name (Evan Leong)
    expect(screen.getAllByText("Evan Leong").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Estella Leong").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Legacy Player").length).toBeGreaterThanOrEqual(1);
  });

  it("routes to /<slug>/<subpath> when switching to a player with a slug", () => {
    render(<PlayerSelector />);
    // Switch to Estella — current pathname is /evanleong/patterns,
    // so the new URL should preserve the "patterns" subpath.
    fireEvent.click(screen.getByLabelText("Switch to Estella Leong"));
    expect(mockPush).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenCalledWith("/estellaleong/patterns");
    // NOT the chess.com username
    expect(mockPush).not.toHaveBeenCalledWith("/sixsevenequals42/patterns");
  });

  it("falls back to username for pre-v1.16.1 players without a slug", () => {
    render(<PlayerSelector />);
    fireEvent.click(screen.getByLabelText("Switch to Legacy Player"));
    expect(mockPush).toHaveBeenCalledWith("/legacyplayer/patterns");
  });

  it("uses slug (not username) as the React key + currentPlayer comparison", () => {
    render(<PlayerSelector />);
    // The selector's currentPlayer prop is "evanleong" (slug), so the
    // Evan button should have the active variant styling. Confirm by
    // grabbing its button and checking the bg color class.
    const evanButton = screen.getByLabelText("Switch to Evan Leong");
    // The active variant applies bg-[#1e40af] when currentPlayer === routeId
    expect(evanButton.className).toContain("bg-[#1e40af]");
  });
});
