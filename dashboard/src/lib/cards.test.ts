import { describe, expect, it } from "vitest";
import { fleetCompare, fleetMatches, followHandoff, type FleetState } from "./cards";
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

describe("followHandoff", () => {
  const lead = (id: string, previous?: string) => ({ id, name: id, state: "idle", previous });
  const solo = (id: string, previous?: string) => card({ key: `session:${id}`, sessions: [lead(id, previous)] });

  it("keeps the key while its card is live (catches needless re-pointing)", () => {
    expect(followHandoff([solo("a"), solo("b", "a")], "session:a", {})).toBe("session:a");
  });

  it("follows one handoff to the card continuing the session (catches the panel closing on a handoff)", () => {
    expect(followHandoff([solo("b", "a")], "session:a", {})).toBe("session:b");
  });

  it("follows a two-hop chain (catches stopping at the first successor)", () => {
    const cards = [card({ key: "wt", sessions: [lead("b", "a"), lead("c", "b")] }), solo("d", "c")];
    expect(followHandoff(cards, "session:a", {})).toBe("session:d");
  });

  it("falls back to the card in the same pane (catches a handoff whose previous is unread)", () => {
    const cards = [solo("x"), solo("n")];
    expect(followHandoff(cards, "session:a", { x: "p1", n: "p2" }, "p2")).toBe("session:n");
  });

  it("returns null when nothing continues the key (catches jumping to an unrelated card)", () => {
    expect(followHandoff([solo("x")], "session:a", { x: "p1" }, "p9")).toBeNull();
  });
});
