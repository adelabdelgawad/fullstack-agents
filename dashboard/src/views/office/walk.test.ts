import { describe, expect, it } from "vitest";
import type { Card, DashState, Session } from "../../lib/types";
import { layoutOffice, officeOf, type OfficeLayout } from "./model";
import { entranceOf, route, Walks, warehouseDoor } from "./walk";

function session(patch: Partial<Session> = {}): Session {
  return { id: "lead", name: "Lead", state: "working", ...patch };
}

function card(key: string, helpers: string[] = []): Card {
  const lead = session({ id: key, name: key, action_running: true, action: "Bash build" });
  const now = [{ ...lead, agents: helpers.map((id) => ({ id, label: `Explore ${id}`, state: "running", at: 1 })) }];
  return {
    key,
    title: key,
    label: key,
    updated: 1,
    runs: [],
    now,
    sessions: [lead],
    needs_you: [],
    phase: "implement",
  };
}

function dash(cards: Card[]): DashState {
  return { cards, waiting: [], still_open: [], history: [], session_panes: {}, repo: "/repo", locks: {}, generated: 1 };
}

const layout = (cards: Card[]): OfficeLayout => layoutOffice(officeOf(dash(cards)), 1400, 800);

describe("routes", () => {
  it("leave an office through its door and reach the warehouse in the lobby", () => {
    const placed = layout([card("alpha")]);
    const desk = placed.desks.find((item) => item.employee.id === "alpha")!;
    const path = route(placed, { x: desk.x + 28 * desk.scale, y: desk.y + 42 * desk.scale }, warehouseDoor(placed)!);
    expect(path.length).toBeGreaterThan(2);
    expect(path[path.length - 1]).toEqual(warehouseDoor(placed));
  });
});

describe("subagents and their desks", () => {
  it("a new subagent comes in from the lobby, collects a desk at the warehouse and carries it to the office", () => {
    const walks = new Walks();
    walks.update(layout([card("alpha")]), "floor", 0);
    walks.update(layout([card("alpha", ["h1"])]), "floor", 100);
    const start = walks.walkers(101).get("h1")!;
    expect(start).toMatchObject({ arriving: true, carrying: false });
    expect(Math.abs(start.y - entranceOf(layout([card("alpha", ["h1"])]))!.y)).toBeLessThan(5);
    const late = walks.walkers(100 + 8800).get("h1")!;
    expect(late.carrying).toBe(true);
    expect(walks.walkers(100 + 9100).has("h1")).toBe(false);
  });

  it("a finished subagent carries its desk back to the warehouse and then leaves without it", () => {
    const walks = new Walks();
    walks.update(layout([card("alpha", ["h1"])]), "floor", 0);
    walks.update(layout([card("alpha")]), "floor", 100);
    expect(walks.walkers(101).get("h1")).toMatchObject({ carrying: true, arriving: false });
    expect(walks.walkers(100 + 8900).get("h1")?.carrying).toBe(false);
  });

  it("a new session's leader walks in without a desk; a fresh view or reduced motion walks nobody", () => {
    const walks = new Walks();
    walks.update(layout([card("alpha")]), "floor", 0);
    expect(walks.walkers(1).size).toBe(0);
    walks.update(layout([card("alpha"), card("beta")]), "floor", 100);
    expect(walks.walkers(200).get("beta")).toMatchObject({ carrying: false, arriving: false });
    walks.update(layout([card("alpha"), card("beta", ["h1"])]), "zoom", 300);
    expect(walks.walkers(400).size).toBe(0);
    walks.update(layout([card("alpha"), card("beta", ["h1", "h2"])]), "zoom", 500, false);
    expect(walks.walkers(600).size).toBe(0);
  });
});
