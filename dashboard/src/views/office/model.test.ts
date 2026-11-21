import { describe, expect, it } from "vitest";
import type { Card, DashState, Session } from "../../lib/types";
import { departmentOf, layoutOffice, officeOf, teamOfEmployee } from "./model";

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
    expect(employees.find((employee) => employee.id === "question")?.bubble).toBe("Which path?");
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

  it("puts each session in the first matching department and keeps empty offices", () => {
    const rules = [
      { name: "DevOps", match: ["deploy"] },
      { name: "VOIP Engineering", match: ["ivr", "tts"] },
      { name: "Fullstack Engineers", match: ["ucm"] },
    ];
    const office = officeOf({
      ...dash([
        card({ key: "s1", repo: "/w/ucm", title: "contacts-people", sessions: [session({ id: "a" })] }),
        card({ key: "s2", repo: "/w/ucm", title: "ivr-domain", sessions: [session({ id: "b" })] }),
        card({ key: "s3", repo: "/w/misc", title: "notes", sessions: [session({ id: "c" })] }),
        card({ key: "s4", repo: "/w/ucm", title: "contacts-two", sessions: [session({ id: "d" })] }),
      ]),
      office_teams: rules,
    });
    expect(office.teams.map((team) => [team.label, team.employees.map((employee) => employee.id)])).toEqual([
      ["DevOps", []],
      ["VOIP Engineering", ["b"]],
      ["Fullstack Engineers", ["a", "d"]],
      ["General", ["c"]],
    ]);
    expect(teamOfEmployee(office, "d")?.label).toBe("Fullstack Engineers");
  });

  it("matches keywords only at the start of a word", () => {
    const rules = [{ name: "VOIP Engineering", match: ["sip"] }];
    expect(departmentOf(card({ title: "gossip-fix" }), rules)).toBe("General");
    expect(departmentOf(card({ title: "fix sip-trunk" }), rules)).toBe("VOIP Engineering");
  });

  it("returns an empty office for absent state", () => {
    expect(officeOf(null)).toEqual({ name: "", teams: [] });
  });
});

describe("layoutOffice", () => {
  const twoTeams = () =>
    officeOf({
      ...dash([
        card({ key: "a", title: "alpha", sessions: [session({ id: "a1" }), session({ id: "a2" }), session({ id: "a3" })] }),
        card({ key: "b", title: "beta", sessions: [session({ id: "b1" })] }),
      ]),
      office_teams: [
        { name: "alpha", match: ["alpha"] },
        { name: "beta", match: ["beta"] },
      ],
    });

  it("fills the canvas with one company building", () => {
    const layout = layoutOffice(twoTeams(), 1200, 700);
    expect(layout).toEqual(layoutOffice(twoTeams(), 1200, 700));
    expect(layout.building).toMatchObject({ label: "repo", x: 8, y: 8, width: 1184, height: 684 });
    expect(layout.height).toBe(700);
  });

  it("puts one room per team inside the building, desks inside their room", () => {
    const layout = layoutOffice(twoTeams(), 1200, 700);
    const building = layout.building!;
    expect(layout.rooms.map((room) => room.label)).toEqual(["alpha", "beta", "Break Room"]);
    for (const room of layout.rooms) {
      expect(room.x).toBeGreaterThan(building.x);
      expect(room.x + room.width).toBeLessThan(building.x + building.width);
      expect(room.y + room.height).toBeLessThan(building.y + building.height);
    }
    for (const desk of layout.desks) {
      const room = layout.rooms.find((candidate) => candidate.key === teamOfEmployee(twoTeams(), desk.employee.id)?.key)!;
      expect(desk.x).toBeGreaterThanOrEqual(room.x);
      expect(desk.x + 56 * desk.scale).toBeLessThanOrEqual(room.x + room.width + 0.001);
      expect(desk.y + 58 * desk.scale).toBeLessThanOrEqual(room.y + room.height + 0.001);
    }
  });

  it("stacks rooms on a narrow canvas and grows past the viewport when desks cannot shrink further", () => {
    const tall = layoutOffice(twoTeams(), 200, 900, 1);
    expect(new Set(tall.rooms.map((room) => room.x)).size).toBe(1);
    const layout = layoutOffice(twoTeams(), 240, 120, 1);
    expect(layout.height).toBeGreaterThanOrEqual(240);
    expect(layout.desks.every((desk) => desk.scale >= 0.5)).toBe(true);
  });

  it("keeps working agents at a running desk and sends idle ones to the break room", () => {
    const office = officeOf({
      ...dash([
        card({
          title: "alpha",
          sessions: [
            session({ id: "busy", action_running: true, action: "Bash build" }),
            session({ id: "idle1", state: "idle" }),
            session({ id: "idle2", state: "quiet" }),
            session({ id: "idle3", state: "idle" }),
          ],
        }),
      ]),
      office_teams: [{ name: "alpha", match: ["alpha"] }],
    });
    const layout = layoutOffice(office, 1400, 800);
    expect(layout.desks.map((desk) => [desk.employee.id, Boolean(desk.away)])).toEqual([
      ["busy", false],
      ["idle1", true],
      ["idle2", true],
      ["idle3", true],
    ]);
    const breakRoom = layout.rooms.find((room) => room.key === "break")!;
    const activities = Object.fromEntries(layout.spots.map((spot) => [spot.employee.id, spot.activity]));
    expect(activities).toEqual({ idle1: "pingpong-left", idle2: "pingpong-right", idle3: "coffee" });
    for (const spot of layout.spots) {
      expect(spot.x).toBeGreaterThanOrEqual(breakRoom.x);
      expect(spot.y + 58 * spot.scale).toBeLessThanOrEqual(breakRoom.y + breakRoom.height + 0.001);
    }
  });

  it("names the company after the repository", () => {
    expect(officeOf({ ...dash([card()]), repo: "/home/x/acme" }).name).toBe("acme");
  });
});
