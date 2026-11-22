import { describe, expect, it } from "vitest";
import type { Card, DashState, Session } from "../../lib/types";
import { cardMembers, CTO_ID, finished, layoutOffice, officeOf, SUBAGENT_SCALE, type Office } from "./model";

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

const members = (source: Card, panes: Record<string, string> = {}) => cardMembers(source, panes);

describe("cardMembers", () => {
  it("maps questions and card requests to waiting", () => {
    expect(members(card({ sessions: [session({ id: "question", question: "Which path?" })] }))[0]).toMatchObject({
      pose: "waiting",
      bubble: "Which path?",
    });
    expect(
      members(card({ needs_you: ["approval"], sessions: [session({ id: "asked", ask: "Approve?" })] }))[0].pose,
    ).toBe("waiting");
  });

  it.each([
    [session({ state: "quiet" }), "asleep"],
    [session({ action_running: true, action: "Read dashboard/src/store.ts" }), "reading"],
    [session({ action_running: true, action: "rg session_panes" }), "reading"],
    [session({ action_running: true, action: "Bash npm build" }), "typing"],
    [session({ state: "working" }), "typing"],
    [session({ state: "idle" }), "idle"],
  ] as const)("maps session activity to %s pose", (lead, pose) => {
    expect(members(card({ sessions: [lead] }))[0].pose).toBe(pose);
  });

  it("keeps running workers, helpers and panes", () => {
    const source = card({
      runs: [
        { id: "running", mode: "implement", unit: "UI", state: "running", action_running: true, action: "Bash build" },
        { id: "done", mode: "audit", state: "done" },
      ],
      now: [session({ id: "lead", agents: [{ id: "helper", state: "running", label: "Reviewer" }] })],
    });
    const list = members(source, { lead: "w:p1" });
    expect(list.map(({ id, role }) => [id, role])).toEqual([
      ["lead", "lead"],
      ["running", "worker"],
      ["helper", "helper"],
    ]);
    expect(list[0].pane).toBe("w:p1");
  });

  it("truncates bubbles and assigns stable colours", () => {
    const long = "A".repeat(80);
    const first = members(card({ sessions: [session({ said: long })] }))[0];
    expect(first.bubble).toHaveLength(60);
    expect(first.colour).toBe(members(card({ sessions: [session({ said: long })] }))[0].colour);
  });
});

const helper = (id: string, state: string, label = id) => ({ id, state, label, at: 1 });
const people = (office: Office) => office.teams.flatMap((team) => team.employees);

describe("officeOf", () => {
  it("puts the CTO first, then one office per session titled with the session", () => {
    const office = officeOf(
      dash([
        card({ key: "a", sessions: [session({ id: "a", name: "ivr-domain" })] }),
        card({ key: "b", sessions: [session({ id: "b", name: "wa-cleanup", state: "idle" })] }),
      ]),
    );
    expect(office.teams.map((team) => team.label)).toEqual(["CTO", "ivr-domain", "wa-cleanup"]);
    expect(office.teams[1].employees[0]).toMatchObject({ id: "a", role: "lead", name: "ivr-domain" });
  });

  it("seats the session's running subagents, workers and shells in its office, never finished ones", () => {
    const source = card({
      key: "a",
      sessions: [session({ id: "a" })],
      runs: [{ id: "w1", mode: "implement", state: "running" }],
      now: [
        session({
          id: "a",
          agents: [
            helper("h1", "running", "Explore"),
            helper("h2", "completed"),
            helper("s1", "running", "shell · npm test"),
          ],
        }),
      ],
    });
    const [, office] = officeOf(dash([source])).teams;
    expect(office.employees.map((employee) => [employee.id, employee.role])).toEqual([
      ["a", "lead"],
      ["w1", "worker"],
      ["h1", "helper"],
      ["s1", "helper"],
    ]);
    expect(office.employees[0].reports?.map((report) => report.id)).toEqual(["w1", "h1", "s1"]);
  });

  it("the CTO, named from the CTO team, carries every session and waits while any needs a decision", () => {
    const office = officeOf({
      ...dash([
        card({ key: "a", sessions: [session({ id: "a" })] }),
        card({ key: "b", sessions: [session({ id: "b", state: "waiting", question: "Ship?" })] }),
      ]),
      office_teams: [{ name: "CTO", match: [], members: ["Adel"] }],
    });
    expect(office.teams[0].employees[0]).toMatchObject({ id: CTO_ID, person: "Adel", pose: "waiting", total: 2 });
  });

  it("a leader whose session finished turns off the lamp and sleeps, keeping its answer", () => {
    const done = card({
      key: "d",
      sessions: [session({ id: "d", state: "idle", said_full: "Shipped.\n- tests pass" })],
    });
    const [cto, office] = officeOf(dash([done, card({ key: "w" })])).teams;
    expect(finished(office.employees[0])).toBe(true);
    expect(office.employees[0].answer).toEqual(["Shipped.", "- tests pass"]);
    expect(finished(cto.employees[0])).toBe(false);
  });

  it("names the company after the repository and is empty without state", () => {
    expect(officeOf({ ...dash([card()]), repo: "/home/x/acme" }).name).toBe("acme");
    expect(officeOf(null).teams).toEqual([]);
  });
});

describe("leader count and shells", () => {
  it("a running shell sits at a desk and keeps the leader at work", () => {
    const source = card({
      key: "w",
      sessions: [session({ id: "w", state: "idle", said_full: "Started the runs." })],
      now: [
        session({
          id: "w",
          agents: [helper("r1", "completed", "diff-reviewer"), helper("s1", "running", "shell · wait")],
        }),
      ],
    });
    const [, office] = officeOf(dash([source])).teams;
    expect(office.employees.map((employee) => employee.id)).toEqual(["w", "s1"]);
    expect(office.employees[0]).toMatchObject({ pose: "typing", sessions: 2, total: 2 });
    expect(finished(office.employees[0])).toBe(false);
  });
});

describe("layoutOffice", () => {
  const office = () =>
    officeOf(
      dash([
        card({
          key: "a",
          sessions: [session({ id: "a", name: "alpha" })],
          now: [session({ id: "a", agents: [helper("h1", "running")] })],
        }),
        card({ key: "b", sessions: [session({ id: "b", name: "beta", state: "idle" })] }),
      ]),
    );

  it("has the CTO office and one Sessions office with a space per session, above the lobby", () => {
    const layout = layoutOffice(office(), 1400, 800);
    expect(layout).toEqual(layoutOffice(office(), 1400, 800));
    expect(layout.halls.map((hall) => hall.label)).toEqual(["CTO", "Sessions"]);
    expect(layout.rooms.map((room) => room.label)).toEqual(["CTO", "alpha", "beta"]);
    const hall = layout.halls[1];
    for (const space of layout.rooms.slice(1)) {
      expect(space.x).toBeGreaterThanOrEqual(hall.x);
      expect(space.x + space.width).toBeLessThanOrEqual(hall.x + hall.width + 0.01);
      expect(space.y).toBeGreaterThanOrEqual(hall.y + hall.band);
      expect(space.y + space.height).toBeLessThanOrEqual(hall.y + hall.height + 0.01);
    }
  });

  it("opens both offices' doors onto the lobby", () => {
    const layout = layoutOffice(office(), 1400, 800);
    const lobby = layout.lobby!;
    for (const hall of layout.halls) {
      expect(Math.abs(hall.y + hall.height + hall.door!.depth - lobby.y), hall.label).toBeLessThan(0.01);
      const doorMid = hall.door!.x + hall.door!.width / 2;
      expect(doorMid).toBeGreaterThan(hall.x);
      expect(doorMid).toBeLessThan(hall.x + hall.width);
    }
  });

  it("keeps each leader and its subagents at desks inside their own office", () => {
    const layout = layoutOffice(office(), 1400, 800);
    for (const desk of layout.desks) {
      const room = layout.rooms.find((item) => item.key === (desk.employee.cardKey || "CTO"))!;
      expect(desk.x, desk.employee.id).toBeGreaterThanOrEqual(room.x);
      expect(desk.y + 58 * desk.scale, desk.employee.id).toBeLessThanOrEqual(room.y + room.height + 0.01);
    }
    expect(layout.desks.map((desk) => desk.employee.id)).toEqual([CTO_ID, "a", "h1", "b"]);
  });

  it("stacks the offices on a narrow canvas and grows past the viewport when desks cannot shrink further", () => {
    const tall = layoutOffice(office(), 200, 1600, 1);
    expect(new Set(tall.halls.map((hall) => hall.x)).size).toBe(1);
    expect(tall.halls[1].y).toBeGreaterThan(tall.halls[0].y + tall.halls[0].height);
    expect(layoutOffice(office(), 240, 120, 1).height).toBeGreaterThanOrEqual(240);
  });

  it("finds the office under the point for zooming", async () => {
    const { roomHit } = await import("./draw");
    const layout = layoutOffice(office(), 1400, 800);
    for (const room of layout.rooms)
      expect(roomHit(layout, room.x + room.width / 2, room.y + room.height / 2)).toBe(room.key);
  });
});

describe("helpers", () => {
  it("everyone on the floor has a stable colour", () => {
    expect(people(office2()).every((employee) => employee.colour >= 0 && employee.colour < 8)).toBe(true);
  });
});

function office2(): Office {
  return officeOf(dash([card({ key: "x" })]));
}

describe("office seating", () => {
  it("the leader sits in the middle; smaller subagent desks line the walls, right first, then left", () => {
    const source = card({
      key: "a",
      sessions: [session({ id: "a" })],
      now: [session({ id: "a", agents: [helper("h1", "running"), helper("h2", "running"), helper("h3", "running")] })],
    });
    const layout = layoutOffice(officeOf(dash([source])), 1400, 800);
    const room = layout.rooms.find((item) => item.key === "a")!;
    const desk = (id: string) => layout.desks.find((item) => item.employee.id === id)!;
    const lead = desk("a");
    expect(Math.abs(lead.x + (56 * lead.scale) / 2 - (room.x + room.width / 2))).toBeLessThan(1);
    for (const id of ["h1", "h2", "h3"]) expect(desk(id).scale).toBeCloseTo(lead.scale * SUBAGENT_SCALE);
    expect(desk("h1").x).toBeGreaterThan(lead.x);
    expect(desk("h2").x).toBeLessThan(lead.x);
    expect(desk("h3").x).toBe(desk("h1").x);
    expect(desk("h3").y).toBeGreaterThan(desk("h1").y);
  });

  it("the CTO's screen counts sessions, not their subagents", () => {
    const busy = card({
      key: "a",
      sessions: [session({ id: "a" })],
      now: [session({ id: "a", agents: [helper("h1", "running"), helper("h2", "running")] })],
    });
    const office = officeOf(dash([busy, card({ key: "b", sessions: [session({ id: "b" })] })]));
    expect(office.teams[0].employees[0]).toMatchObject({ sessions: 2, total: 2 });
  });
});
