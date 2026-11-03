import { describe, expect, it } from "vitest";
import { fleetCompare, fleetMatches, type FleetState } from "./cards";
import type { Card } from "./types";

function card(overrides: Partial<Card>): Card {
  return {
    key: "k",
    title: "Search",
    label: "",
    tree: null,
    updated: 100,
    runs: [],
    now: [],
    sessions: [{ id: "s1", name: "lead", state: "idle", branch: "main" }],
    usage: null,
    needs_you: [],
    phase: "implement",
    ...overrides,
  };
}

describe("fleetMatches", () => {
  it("keeps only blowouts under the blowouts filter", () => {
    const hot = card({ key: "hot", usage: { blowout: true, model: "claude-opus-5-5" } });
    const cold = card({ key: "cold", title: "Other", usage: { blowout: false, model: "x" } });
    const fleet: FleetState = { filter: "blowouts", sort: "stage", text: "" };
    expect([hot, cold].filter((c) => fleetMatches(c, fleet)).map((c) => c.key)).toEqual(["hot"]);
  });

  it("matches free text against title, branch and model", () => {
    const hot = card({ key: "hot", usage: { blowout: true, model: "claude-opus-5-5" } });
    const cold = card({ key: "cold", title: "Other", usage: { blowout: false, model: "x" } });
    const fleet: FleetState = { filter: "all", sort: "stage", text: "oth" };
    expect([hot, cold].filter((c) => fleetMatches(c, fleet)).map((c) => c.key)).toEqual(["cold"]);
  });
});

describe("fleetCompare", () => {
  it("puts the most expensive card first", () => {
    const cards = [card({ key: "a", usage: { cost: 1 } }), card({ key: "b", usage: { cost: 9 } }), card({ key: "c" })];
    const fleet: FleetState = { filter: "all", sort: "cost", text: "" };
    expect([...cards].sort((a, b) => fleetCompare(a, b, fleet)).map((c) => c.key)).toEqual(["b", "a", "c"]);
  });
});
