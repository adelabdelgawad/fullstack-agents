import { describe, expect, it } from "vitest";
import type { Card, DashState, Session } from "../../lib/types";
import { layoutOffice, officeOf, type OfficeLayout } from "./model";
import { entranceOf, route, Walks } from "./walk";

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

/** Samples a walk until it ends: true when the agent carried its desk at every step. */
function carriedThroughout(walks: Walks, id: string, start: number): boolean {
  const seen: boolean[] = [];
  for (let t = start + 1; t < start + 9100; t += 250) {
    const walker = walks.walkers(t).get(id);
    if (walker) seen.push(walker.carrying);
  }
  return seen.length > 3 && seen.every(Boolean);
}

const layout = (cards: Card[]): OfficeLayout => layoutOffice(officeOf(dash(cards)), 1400, 800);

describe("routes", () => {
  it("leave the Sessions office through its door and cross the lobby to the CTO office", () => {
    const placed = layout([card("alpha")]);
    const seat = (id: string) => {
      const desk = placed.desks.find((item) => item.employee.id === id)!;
      return { x: desk.x + 28 * desk.scale, y: desk.y + 42 * desk.scale };
    };
    const path = route(placed, seat("alpha"), seat("cto"));
    const [cto, sessions] = placed.halls;
    expect(path).toContainEqual({
      x: sessions.door!.x + sessions.door!.width / 2,
      y: sessions.y + sessions.height - 4,
    });
    expect(path[path.length - 2]).toEqual({ x: cto.door!.x + cto.door!.width / 2, y: cto.y + cto.height - 4 });
    expect(path.some((point) => point.y > placed.lobby!.y)).toBe(true);
  });

  it("keep to the aisle between session spaces instead of crossing another session's space", () => {
    const placed = layout([card("alpha"), card("beta")]);
    const [a, b] = ["alpha", "beta"].map((id) => placed.desks.find((item) => item.employee.id === id)!);
    const path = route(placed, a, b);
    expect(path[0]).toEqual(a);
    expect(path[path.length - 1]).toEqual(b);
    const aisle = path[1].y;
    const bottom = Math.max(...placed.rooms.slice(1).map((space) => space.y + space.height));
    expect(aisle).toBeGreaterThan(bottom);
    expect(path.slice(1, -1).every((point) => point.y === aisle)).toBe(true);
  });
});

describe("agents and their desks", () => {
  it("a new subagent walks in from the entrance carrying its desk all the way to its place", () => {
    const walks = new Walks();
    walks.update(layout([card("alpha")]), "floor", 0);
    walks.update(layout([card("alpha", ["h1"])]), "floor", 100);
    const start = walks.walkers(101).get("h1")!;
    expect(start).toMatchObject({ arriving: true, carrying: true });
    expect(Math.abs(start.y - entranceOf(layout([card("alpha", ["h1"])]))!.y)).toBeLessThan(5);
    expect(carriedThroughout(walks, "h1", 100)).toBe(true);
    expect(walks.walkers(100 + 9100).has("h1")).toBe(false);
  });

  it("a finished subagent picks up its desk and carries it out", () => {
    const walks = new Walks();
    walks.update(layout([card("alpha", ["h1"])]), "floor", 0);
    walks.update(layout([card("alpha")]), "floor", 100);
    expect(walks.walkers(101).get("h1")).toMatchObject({ carrying: true, arriving: false });
    expect(carriedThroughout(walks, "h1", 100)).toBe(true);
  });

  it("a session's leader carries its desk in, and out when the session goes; the CTO never moves", () => {
    const walks = new Walks();
    walks.update(layout([card("alpha")]), "floor", 0);
    expect(walks.walkers(1).size).toBe(0);
    walks.update(layout([card("alpha"), card("beta")]), "floor", 100);
    expect(walks.walkers(200).get("beta")).toMatchObject({ carrying: true, arriving: true });
    walks.update(layout([card("alpha")]), "floor", 20000);
    expect(walks.walkers(20001).get("beta")).toMatchObject({ carrying: true, arriving: false });
    expect(walks.walkers(20001).has("cto")).toBe(false);
  });

  it("a fresh view or reduced motion walks nobody", () => {
    const walks = new Walks();
    walks.update(layout([card("alpha")]), "floor", 0);
    walks.update(layout([card("alpha"), card("beta", ["h1"])]), "zoom", 300);
    expect(walks.walkers(400).size).toBe(0);
    walks.update(layout([card("alpha"), card("beta", ["h1", "h2"])]), "zoom", 500, false);
    expect(walks.walkers(600).size).toBe(0);
  });
});
