import { describe, expect, it } from "vitest";
import { focusedByBackground, tabTintSpans, tintColour } from "./herdrTabTint";

const chip = (label: string, status = "working", focused = false) => ({ label, status, focused });

describe("herdr tab tint spans", () => {
  it("finds each tab label in order on the tab bar row", () => {
    const row = " herdr  │ 1 asr-session02 │ 2 2 │ 3 api ";
    expect(tabTintSpans(row, [chip("asr-session02", "working", true), chip("2", "idle"), chip("api", "done")])).toEqual([
      { label: "asr-session02", status: "working", focused: true, start: 12, end: 25 },
      { label: "2", status: "idle", focused: false, start: 28, end: 29 },
      { label: "api", status: "done", focused: false, start: 36, end: 39 },
    ]);
  });

  it("skips labels inside longer words and labels not on the row", () => {
    const row = " api-gateway │ api ";
    expect(tabTintSpans(row, [chip("api"), chip("missing"), chip("")]).map((s) => s.start)).toEqual([15]);
  });

  it("takes the focused tab from the one label background that differs", () => {
    expect(focusedByBackground(["#282c34", "#61afef", "#282c34"])).toBe(1);
    expect(focusedByBackground(["#282c34", "#282c34"])).toBe(-1);
    expect(focusedByBackground(["#61afef"])).toBe(-1);
    expect(focusedByBackground(["#1", "#2", "#3"])).toBe(-1);
  });

  it("copies the sidebar label colour, and uses the state table only when the sidebar has no label", () => {
    expect(tintColour("#e5c07b", "idle")).toBe("#e5c07b");
    expect(tintColour(null, "working")).toBeNull();
    expect(tintColour(undefined, "working")).toBe("var(--herdr-yellow)");
    expect(tintColour(undefined, "idle")).toBeNull();
  });
});
