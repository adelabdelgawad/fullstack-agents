import { describe, expect, it } from "vitest";
import type { Card, DashState, Session } from "../../lib/types";
import { layoutOffice, officeOf } from "./model";

function session(patch: Partial<Session> = {}): Session {
  return { id: "lead", name: "Lead", state: "working", ...patch };
}

function card(patch: Partial<Card> = {}): Card {
  return {
    key: "office",
    label: "Office team",
    updated: 1,
    runs: [],
    now: [],
    sessions: [session()],
    usage: { cost: 2.5, tokens: 2400 },
    needs_you: [],
    phase: "implement",
    ...patch,
  };
}

function dash(cards: Card[], panes: Record<string, string> = {}): DashState {
  return {
    cards,
    waiting: [],
    still_open: [],
    history: [],
    session_panes: panes,
    repo: "/repo",
    locks: {},
    generated: 1,
  };
}

describe("officeOf", () => {
  it("maps questions and card requests to waiting", () => {
    const employees = officeOf(
      dash([
        card({ sessions: [session({ id: "question", question: "Which path?" })] }),
        card({ key: "human", needs_you: ["approval"], sessions: [session({ id: "asked", ask: "Approve?" })] }),
      ]),
    ).teams.flatMap((team) => team.employees);
    expect(employees.map((employee) => employee.pose)).toEqual(["waiting", "waiting"]);
    expect(employees[0].bubble).toBe("Which path?");
  });

  it("keeps a running worker typing while its lead waits on the card request", () => {
    const source = card({
      needs_you: ["approval"],
      runs: [{ id: "run", mode: "implement", state: "running", action_running: true, action: "Bash build" }],
    });
    const poses = officeOf(dash([source])).teams[0].employees.map((employee) => employee.pose);
    expect(poses).toEqual(["waiting", "typing"]);
  });

  it.each([
    [session({ state: "quiet" }), "asleep"],
    [session({ action_running: true, action: "Read dashboard/src/store.ts" }), "reading"],
    [session({ action_running: true, action: "rg session_panes" }), "reading"],
    [session({ action_running: true, action: "Bash npm build" }), "typing"],
    [session({ state: "idle" }), "idle"],
  ] as const)("maps session activity to %s pose", (lead, pose) => {
    expect(officeOf(dash([card({ sessions: [lead] })])).teams[0].employees[0].pose).toBe(pose);
  });

  it("keeps running workers, helpers, panes, and lead-only card usage", () => {
    const source = card({
      runs: [
        { id: "running", mode: "implement", unit: "UI", state: "running" },
        { id: "done", mode: "audit", state: "done" },
      ],
      now: [session({ id: "lead", agents: [{ id: "helper", state: "running", label: "Reviewer" }] })],
    });
    const employees = officeOf(dash([source], { lead: "w:p1" })).teams[0].employees;
    expect(employees.map(({ id, role }) => [id, role])).toEqual([
      ["lead", "lead"],
      ["running", "worker"],
      ["helper", "helper"],
    ]);
    expect(employees[0]).toMatchObject({ pane: "w:p1", cost: 2.5, tokens: 2400 });
    expect(employees[1]).toMatchObject({ pane: null, cost: null });
    expect(employees.some((employee) => employee.id === "done")).toBe(false);
  });

  it("truncates bubbles and assigns stable colours", () => {
    const long = "A".repeat(80);
    const first = officeOf(dash([card({ sessions: [session({ said: long })] })])).teams[0].employees[0];
    const second = officeOf(dash([card({ sessions: [session({ said: long })] })])).teams[0].employees[0];
    expect(first.bubble).toHaveLength(60);
    expect(first.colour).toBe(second.colour);
  });

  it("returns an empty office for absent state", () => {
    expect(officeOf(null)).toEqual({ name: "", teams: [] });
  });
});

describe("layoutOffice", () => {
  it("places desks deterministically inside their team room", () => {
    const office = officeOf(dash([card({ sessions: [session(), session({ id: "two", name: "Two" })] })]));
    const layout = layoutOffice(office, 400);
    expect(layout).toEqual(layoutOffice(office, 400));
    for (const desk of layout.desks) {
      const room = layout.rooms[0];
      expect(desk.x).toBeGreaterThanOrEqual(room.x);
      expect(desk.x + 52 * desk.scale).toBeLessThanOrEqual(room.x + room.width);
      expect(desk.y + 58 * desk.scale).toBeLessThanOrEqual(room.y + room.height);
    }
  });

  it("puts every team room inside one company building, rows split by a corridor", () => {
    const office = officeOf(
      dash([card({ key: "a", label: "A" }), card({ key: "b", label: "B", sessions: [session({ id: "b1" })] })]),
    );
    office.name = "acme";
    const layout = layoutOffice(office, 300);
    const building = layout.building!;
    expect(building.label).toBe("acme");
    expect(layout.rooms.map((room) => room.key)).toEqual(["a", "b"]);
    const [a, b] = layout.rooms;
    expect(b.y).toBeGreaterThanOrEqual(a.y + a.height + 20 * a.scale);
    for (const room of layout.rooms) {
      expect(room.x).toBeGreaterThan(building.x);
      expect(room.x + room.width).toBeLessThan(building.x + building.width);
      expect(room.y).toBeGreaterThan(building.y);
      expect(room.y + room.height).toBeLessThan(building.y + building.height);
    }
    expect(layout.height).toBe(building.y + building.height + 16);
  });

  it("names the company after the repository", () => {
    expect(officeOf({ ...dash([card()]), repo: "/home/x/acme" }).name).toBe("acme");
  });
});
