import { describe, it, expect, vi } from "vitest";

/** v1.18.2: regression lock for the mobile viewport meta tag.
 *
 *  The app shipped with 74 responsive breakpoint classes but no
 *  viewport meta tag, so mobile browsers rendered at desktop width
 *  and the breakpoints never fired. v1.18.2 added the `viewport`
 *  export. This test ensures a future refactor can't silently drop
 *  it again — the exact "missing meta tag" gap class that motivated
 *  the ship.
 *
 *  We mock the child components + Providers so importing the layout
 *  module doesn't drag in their dependency trees (next/navigation,
 *  SWR, etc.). We only care about the module-level `viewport` and
 *  `metadata` exports here, not the rendered tree. */

vi.mock("@/components/app-header", () => ({ AppHeader: () => null }));
vi.mock("@/components/nav-bar", () => ({ NavBar: () => null }));
vi.mock("../providers", () => ({ Providers: ({ children }: { children: React.ReactNode }) => children }));

import { metadata, viewport } from "../layout";

describe("RootLayout — v1.18.2 viewport meta tag", () => {
  it("exports a viewport with width=device-width", () => {
    expect(viewport).toBeDefined();
    expect(viewport.width).toBe("device-width");
  });

  it("sets initial-scale to 1", () => {
    expect(viewport.initialScale).toBe(1);
  });

  it("does NOT lock zoom (pinch-zoom must stay available)", () => {
    // Accessibility: never set maximumScale or userScalable=false.
    // A 9-year-old may want to zoom the board.
    expect(viewport.maximumScale).toBeUndefined();
    expect(viewport.userScalable).not.toBe(false);
  });

  it("still exports the page metadata (title/description)", () => {
    // Sanity: the viewport export sits alongside metadata, not
    // replacing it.
    expect(metadata.title).toBe("Arrakis Engine");
    expect(metadata.description).toContain("Chess Coach");
  });
});
