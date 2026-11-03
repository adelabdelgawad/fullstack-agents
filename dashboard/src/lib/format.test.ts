import { describe, expect, it } from "vitest";
import { esc, fmtCost, fmtTokens, modelShort } from "./format";

describe("esc", () => {
  it("escapes html-sensitive characters", () => {
    expect(esc(`<b>"it's" & more</b>`)).toBe("&lt;b&gt;&quot;it&#39;s&quot; &amp; more&lt;/b&gt;");
  });

  it("coerces null and undefined to an empty string", () => {
    expect(esc(null)).toBe("");
    expect(esc(undefined)).toBe("");
  });
});

describe("fmtTokens", () => {
  it("formats zero", () => {
    expect(fmtTokens(0)).toBe("0");
  });

  it("formats thousands", () => {
    expect(fmtTokens(2500)).toBe("3k");
  });

  it("formats millions", () => {
    expect(fmtTokens(3_000_000)).toBe("3.0M");
  });

  it("drops the decimal above 1e8", () => {
    expect(fmtTokens(150_000_000)).toBe("150M");
  });

  it("formats billions", () => {
    expect(fmtTokens(1_500_000_000)).toBe("1.50B");
  });
});

describe("fmtCost", () => {
  it("renders a dash for null or undefined", () => {
    expect(fmtCost(null)).toBe("—");
    expect(fmtCost(undefined)).toBe("—");
  });

  it("rounds costs at or above 100", () => {
    expect(fmtCost(125.6)).toBe("$126");
  });

  it("keeps cents below 100", () => {
    expect(fmtCost(12.5)).toBe("$12.50");
  });
});

describe("modelShort", () => {
  it("drops the claude prefix and adds a dot to the version", () => {
    expect(modelShort("claude-sonnet-5-5")).toBe("sonnet 5.5");
  });

  it("keeps a single trailing number as-is", () => {
    expect(modelShort("gpt-5")).toBe("gpt 5");
  });

  it("returns an empty string for falsy input", () => {
    expect(modelShort(undefined)).toBe("");
  });
});
