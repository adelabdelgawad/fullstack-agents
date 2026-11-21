import { describe, expect, it } from "vitest";
import type { Card, DashState, Session } from "../../lib/types";
import { cardMembers, CTO_ID, departmentOf, layoutOffice, officeOf, teamOfEmployee, type Office } from "./model";

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
const agents = (office: Office) =>
  office.teams.flatMap((team) => team.employees).filter((agent) => agent.id !== CTO_ID);

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

describe("officeOf", () => {
  it("makes one agent per card that counts its active sessions", () => {
    const source = card({
      sessions: [session({ id: "lead", state: "idle" })],
      runs: [{ id: "w1", mode: "implement", state: "running", action_running: true, action: "Bash build" }],
    });
    const [agent] = agents(officeOf(dash([source])));
    expect(agent).toMatchObject({ id: "office", name: "Lead", pose: "typing", sessions: 1, total: 2, cost: 2.5 });
  });

  it("an agent with no active session is away; plan and design work goes to the meeting room", () => {
    const office = officeOf(
      dash([
        card({ key: "rest", sessions: [session({ id: "r", state: "idle" })] }),
        card({ key: "plan", phase: "plan", sessions: [session({ id: "p" })] }),
      ]),
    );
    const byId = Object.fromEntries(agents(office).map((agent) => [agent.id, agent]));
    expect(byId.rest.sessions).toBe(0);
    expect(byId.plan.meeting).toBe(true);
  });

  it("puts the CTO first, in the CTO office, counting every active session", () => {
    const office = officeOf(
      dash([card({ key: "a" }), card({ key: "b", sessions: [session({ id: "b", state: "idle" })] })]),
    );
    expect(office.teams[0].label).toBe("CTO");
    expect(office.teams[0].employees[0]).toMatchObject({ id: CTO_ID, sessions: 1, total: 2, fixed: true });
  });

  it("puts each agent in the first matching department and keeps empty offices", () => {
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
      ["CTO", [CTO_ID]],
      ["DevOps", []],
      ["VOIP Engineering", ["s2"]],
      ["Fullstack Engineers", ["s1", "s4"]],
      ["General", ["s3"]],
    ]);
    expect(teamOfEmployee(office, "s4")?.label).toBe("Fullstack Engineers");
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
  const office = () =>
    officeOf({
      ...dash([
        card({ key: "a", title: "alpha", sessions: [session({ id: "a1" })] }),
        card({ key: "b", title: "beta", sessions: [session({ id: "b1", state: "idle" })] }),
        card({ key: "c", title: "beta two", sessions: [session({ id: "c1", state: "idle" })] }),
        card({ key: "d", title: "alpha plan", phase: "plan", sessions: [session({ id: "d1" })] }),
      ]),
      office_teams: [
        { name: "alpha", match: ["alpha"] },
        { name: "beta", match: ["beta"] },
      ],
    });

  it("fills the canvas with one floor plan: offices, meeting room, break room, corridors and a lobby", () => {
    const layout = layoutOffice(office(), 1400, 800);
    expect(layout).toEqual(layoutOffice(office(), 1400, 800));
    expect(layout.building).toMatchObject({ x: 8, y: 8, width: 1384 });
    expect(layout.height).toBe(800);
    expect(layout.rooms.map((room) => room.label)).toEqual(["CTO", "alpha", "beta", "Meeting Room", "Break Room"]);
    expect(layout.lobby).not.toBeNull();
  });

  it("opens every room's door onto a corridor or the lobby", () => {
    const layout = layoutOffice(office(), 1400, 800);
    const halls = [...layout.corridors, layout.lobby!];
    for (const room of layout.rooms) {
      const sill = room.y + room.height + room.door!.depth;
      const doorMid = room.door!.x + room.door!.width / 2;
      const hall = halls.find(
        (rect) => Math.abs(rect.y - sill) < 0.01 && doorMid >= rect.x && doorMid <= rect.x + rect.width,
      );
      expect(hall, room.label).toBeDefined();
    }
  });

  it("keeps desks inside their office and sends away and meeting agents out of them", () => {
    const layout = layoutOffice(office(), 1400, 800);
    const away = Object.fromEntries(
      layout.desks
        .filter((desk) => !desk.employee.id.startsWith("vacant:"))
        .map((desk) => [desk.employee.id, Boolean(desk.away)]),
    );
    expect(away).toEqual({ [CTO_ID]: false, a: false, b: true, c: true, d: true });
    const activities = Object.fromEntries(
      layout.spots
        .filter((spot) => !spot.employee.id.startsWith("team:"))
        .map((spot) => [spot.employee.id, spot.activity]),
    );
    for (const id of ["b", "c"])
      expect(["bar", "gaming", "pingpong-left", "pingpong-right", "coffee"]).toContain(activities[id]);
    expect(activities.d).toBe("meeting");
    const breakRoom = layout.rooms.find((room) => room.key === "break")!;
    expect(breakRoom.table).toBeDefined();
    expect(layout.rooms.find((room) => room.key === "meeting")!.table).toBeDefined();
  });

  it("always furnishes the break room, even with nobody on break", () => {
    const quiet = officeOf(dash([card()]));
    const breakRoom = layoutOffice(quiet, 1200, 700).rooms.find((room) => room.key === "break")!;
    expect(breakRoom.table!.width).toBeGreaterThan(0);
  });

  it("stacks rooms on a narrow canvas and grows past the viewport when desks cannot shrink further", () => {
    const tall = layoutOffice(office(), 200, 1600, 1);
    expect(new Set(tall.rooms.map((room) => room.x)).size).toBe(1);
    expect(layoutOffice(office(), 240, 120, 1).height).toBeGreaterThanOrEqual(240);
  });

  it("names the company after the repository", () => {
    expect(officeOf({ ...dash([card()]), repo: "/home/x/acme" }).name).toBe("acme");
  });
});

describe("reporting lines", () => {
  it("each agent delegates to its workers and subagents; the CTO leads every agent", () => {
    const source = card({
      runs: [{ id: "w1", mode: "implement", state: "running", action_running: true, action: "Bash build" }],
      now: [session({ id: "lead", agents: [{ id: "h1", state: "running", label: "Reviewer" }] })],
    });
    const office = officeOf(dash([source, card({ key: "solo", sessions: [session({ id: "s" })] })]));
    const [agent, solo] = agents(office);
    expect(agent.reports?.map((report) => [report.id, report.role])).toEqual([
      ["w1", "worker"],
      ["h1", "helper"],
    ]);
    expect(solo.reports).toEqual([]);
    expect(office.teams[0].employees[0].reports?.map((report) => report.id)).toEqual(["office", "solo"]);
  });
});

describe("background work keeps the agent at its desk", () => {
  it("a running background shell or a finished answer is not a break", () => {
    const shell = card({
      key: "bg",
      sessions: [session({ id: "a", state: "idle" })],
      now: [session({ id: "a", state: "idle", agents: [{ id: "t1", state: "running", label: "shell · build" }] })],
    });
    const open = card({ key: "open", sessions: [session({ id: "b", state: "still_open", said_full: "Done." })] });
    const rest = card({ key: "rest", sessions: [session({ id: "c", state: "idle" })] });
    const office = officeOf(dash([shell, open, rest]));
    const layout = layoutOffice(office, 1400, 800);
    const away = layout.spots.filter((spot) => spot.activity !== "meeting").map((spot) => spot.employee.id);
    expect(away.filter((id) => !id.startsWith("team:"))).toEqual(["rest"]);
  });
});

describe("idle departments", () => {
  it("a department with no running work takes its break in the Break Room", () => {
    const office = officeOf(
      dash([card({ key: "busy", sessions: [session({ id: "b", action_running: true, action: "Bash build" })] })]),
    );
    const layout = layoutOffice(office, 1400, 800);
    const onBreak = layout.spots.filter((spot) => spot.employee.id.startsWith("team:"));
    const busyTeam = office.teams.find((team) => team.employees.some((employee) => employee.id === "busy"))!;
    expect(onBreak.length).toBe(office.teams.length - 2);
    expect(onBreak.some((spot) => spot.employee.id === `team:${busyTeam.key}`)).toBe(false);
    expect(onBreak.some((spot) => spot.employee.id === `team:${office.teams[0].key}`)).toBe(false);
  });
});

describe("department offices", () => {
  it("seat two desks; only agents on a running session work at a lit PC", () => {
    const office = officeOf(
      dash([card({ key: "busy", sessions: [session({ id: "b", action_running: true, action: "Bash build" })] })]),
    );
    const layout = layoutOffice(office, 1400, 800);
    const team = office.teams.find((item) => item.employees.some((employee) => employee.id === "busy"))!;
    const room = layout.rooms.find((item) => item.key === team.key)!;
    const desks = layout.desks.filter(
      (desk) => desk.x >= room.x && desk.x < room.x + room.width && desk.y >= room.y && desk.y < room.y + room.height,
    );
    expect(desks).toHaveLength(2);
    expect(desks.filter((desk) => !desk.away).map((desk) => desk.employee.id)).toEqual(["busy"]);
    expect(layout.desks.filter((desk) => desk.employee.id === CTO_ID)).toHaveLength(1);
  });
});

describe("finished agents", () => {
  it("raise a hand with the first three lines of the answer", () => {
    const said_full = "**Shipped 3.94.0.**\n\n- Office PC opens the card\n- Tests pass\n- Build clean";
    const office = officeOf(dash([card({ key: "fin", sessions: [session({ id: "f", state: "idle", said_full })] })]));
    const agent = agents(office)[0];
    expect(agent.pose).toBe("done");
    expect(agent.answer).toEqual(["Shipped 3.94.0.", "- Office PC opens the card", "- Tests pass"]);
  });

  it("a question for you stays a wait, not a raised hand", () => {
    const office = officeOf(
      dash([card({ key: "ask", sessions: [session({ id: "q", state: "waiting", said_full: "Which one?" })] })]),
    );
    expect(agents(office)[0].pose).toBe("waiting");
  });
});

describe("office zoom hit", () => {
  it("finds the department office under the point, never the meeting or break room", async () => {
    const { roomHit } = await import("./draw");
    const layout = layoutOffice(
      officeOf(dash([card({ key: "a", sessions: [session({ id: "a", action_running: true, action: "Bash x" })] })])),
      1400,
      800,
    );
    for (const room of layout.rooms) {
      const hit = roomHit(layout, room.x + room.width / 2, room.y + room.height / 2);
      expect(hit).toBe(room.key === "break" || room.key === "meeting" ? null : room.key);
    }
  });
});
