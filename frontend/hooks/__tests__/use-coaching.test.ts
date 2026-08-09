import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// v1.30.0: the poller must stop when the component unmounts, and a second
// startCoaching must not orphan the first interval. Before this, navigating
// away mid-coaching left a 3s interval calling fetchGameDetail for up to 10
// minutes, and a double-start could clear the wrong handle and hang the UI.

const triggerCoaching = vi.fn();
const fetchGameDetail = vi.fn();

vi.mock("@/lib/api", () => ({
  triggerCoaching: (...a: unknown[]) => triggerCoaching(...a),
  fetchGameDetail: (...a: unknown[]) => fetchGameDetail(...a),
}));

import { useCoaching } from "@/hooks/use-coaching";

describe("useCoaching — poller lifecycle", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    triggerCoaching.mockReset().mockResolvedValue(undefined);
    // Never "completes", so the interval keeps firing until cleared.
    fetchGameDetail.mockReset().mockResolvedValue({
      game: { coaching_status: "pending" },
      coaching: { provider: "old" },
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("stops polling after unmount", async () => {
    const { result, unmount } = renderHook(() => useCoaching(1));

    await act(async () => {
      result.current.startCoaching("claude", () => {});
    });
    // let the pre-poll fetchGameDetail + triggerCoaching settle
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });

    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    const callsBeforeUnmount = fetchGameDetail.mock.calls.length;
    expect(callsBeforeUnmount).toBeGreaterThan(0);

    unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(20000); });

    // No further polling once unmounted.
    expect(fetchGameDetail.mock.calls.length).toBe(callsBeforeUnmount);
  });
});
