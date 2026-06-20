import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

/** §6: NavBar accepts an `extraItems` prop so out-of-tree code (the
 *  commercial Atreides build's OCR/Scan page) can add nav entries without
 *  forking the component. We mock usePathname / usePlayerContext so the base
 *  items render and a player-scoped extra item gets the /<slug> prefix applied
 *  through the same mapping. (Import is a native nav item as of v1.24.0, so the
 *  example here uses a commercial-only label to avoid colliding with it.) */

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
      { href: "/scan", label: "Scan", playerScoped: true },
    ];
    render(<NavBar extraItems={extraItems} />);

    const scanLink = screen.getByRole("link", { name: "Scan" });
    expect(scanLink.getAttribute("href")).toBe("/evanleong/scan");
  });

  it("renders Import as a native nav item (v1.24.0)", () => {
    render(<NavBar />);
    const importLink = screen.getByRole("link", { name: "Import" });
    expect(importLink.getAttribute("href")).toBe("/evanleong/import");
  });
});
