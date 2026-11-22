import { describe, it, expect } from "vitest";
import { timeClassName, timeClassLabel } from "../time-class";

describe("time-class display names (v1.34.1)", () => {
  it("shows the stored 'classical' time class as Standard", () => {
    expect(timeClassName("classical")).toBe("standard");
    expect(timeClassLabel("classical")).toBe("Standard");
  });

  it("leaves every other time class as it is", () => {
    for (const tc of ["bullet", "blitz", "rapid", "daily"]) {
      expect(timeClassName(tc)).toBe(tc);
    }
    expect(timeClassLabel("rapid")).toBe("Rapid");
    expect(timeClassLabel("correspondence")).toBe("Correspondence");
  });

  it("uses the fallback for a missing time class", () => {
    expect(timeClassName(null)).toBe("?");
    expect(timeClassName(undefined, "—")).toBe("—");
    expect(timeClassLabel("")).toBe("?");
  });
});
