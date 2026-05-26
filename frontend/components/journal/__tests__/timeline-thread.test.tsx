import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { TimelineNode } from "../timeline-thread";

describe("TimelineNode", () => {
  it("renders an emerald node for kind=review", () => {
    const { container } = render(<TimelineNode kind="review" />);
    const node = container.firstChild as HTMLElement;
    expect(node.className).toMatch(/bg-emerald-500/);
  });

  it("renders a blue node for kind=note", () => {
    const { container } = render(<TimelineNode kind="note" />);
    expect((container.firstChild as HTMLElement).className).toMatch(/bg-blue-500/);
  });

  it("falls back to gray for unknown kinds", () => {
    const { container } = render(<TimelineNode kind="some_future_kind" />);
    expect((container.firstChild as HTMLElement).className).toMatch(/bg-zinc-400/);
  });

  it("sets the title attribute when provided", () => {
    const { container } = render(<TimelineNode kind="review" title="Review · chess.com" />);
    expect((container.firstChild as HTMLElement).getAttribute("title")).toBe(
      "Review · chess.com",
    );
  });

  it("is aria-hidden because the node is decorative", () => {
    const { container } = render(<TimelineNode kind="review" />);
    expect((container.firstChild as HTMLElement).getAttribute("aria-hidden")).not.toBeNull();
  });
});
