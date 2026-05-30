import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

/** §6: NavBar accepts an `extraItems` prop so out-of-tree code (the
 *  commercial Atreides build's PGN-import page) can add nav entries
 *  without forking the component. We mock usePathname / usePlayerContext
 *  so the base items render and a player-scoped extra item gets the
 *  /<slug> prefix applied through the same mapping. */

vi.mock("next/navigation", () => ({
  usePathname: () => "/evanleong/games",
}));

vi.mock("@/app/providers", () => ({
  usePlayerContext: () => ({ currentPlayer: "evanleong" }),
}));

import { NavBar, type NavItem } from "@/components/nav-bar";

describe("NavBar — §6 extraItems", () => {
  it("renders the base nav items", () => {
    render(<NavBar />);
    expect(screen.getByRole("link", { name: "Dashboard" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Games" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Reports" })).toBeTruthy();
  });

  it("renders a player-scoped extra item with the /<slug> prefix", () => {
    const extraItems: NavItem[] = [
      { href: "/import", label: "Import", playerScoped: true },
    ];
    render(<NavBar extraItems={extraItems} />);

    const importLink = screen.getByRole("link", { name: "Import" });
    expect(importLink.getAttribute("href")).toBe("/evanleong/import");
  });
});
