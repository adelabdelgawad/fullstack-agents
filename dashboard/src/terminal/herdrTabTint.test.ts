import { describe, expect, it } from "vitest";
import { tabTintSpans } from "./herdrTabTint";

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
});
