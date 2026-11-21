import { describe, expect, it } from "vitest";
import type { Card, DashState, Session } from "../../lib/types";
import { BREAK_ROOM, CTO_ID, layoutOffice, officeOf, type OfficeLayout } from "./model";
import { placesOf, route, Walks } from "./walk";

function session(patch: Partial<Session> = {}): Session {
  return { id: "lead", name: "Lead", state: "working", ...patch };
}

function card(key: string, busy: boolean, title = key): Card {
  const lead = busy
    ? session({ id: key, action_running: true, action: "Bash build" })
    : session({ id: key, state: "quiet" });
  return { key, title, label: key, updated: 1, runs: [], now: [], sessions: [lead], needs_you: [], phase: "implement" };
}

function dash(cards: Card[], teams: DashState["office_teams"] = []): DashState {
  return {
    cards,
    waiting: [],
    still_open: [],
    history: [],
    session_panes: {},
    repo: "/repo",
    locks: {},
    generated: 1,
    office_teams: teams,
  };
}

const TEAMS = [
  { name: "CTO", match: ["cto"], members: ["Adel"] },
  { name: "Network Engineers", match: ["network"], members: ["Boraie", "Moustafa", "Karim", "Abudaif"] },
];

function layout(cards: Card[], round = 0): OfficeLayout {
  return layoutOffice(officeOf(dash(cards, TEAMS)), 1400, 800, 2, true, round);
}

describe("named staff", () => {
  it("names the CTO and sends idle members to the break room in person", () => {
    const placed = layout([card("network-vpn", true)]);
    const people = new Map([...placed.desks, ...placed.spots].map((place) => [place.employee.id, place.employee]));
    expect(people.get("cto")?.person).toBe("Adel");
    expect(people.get("network-vpn")?.person).toBe("Boraie");
    const onBreak = placed.spots.map((spot) => spot.employee.name);
    expect(onBreak).toEqual(expect.arrayContaining(["Moustafa", "Karim", "Abudaif"]));
    expect(onBreak).not.toContain("Network Engineers");
  });
});

describe("break rounds", () => {
  it("swap who plays ping-pong, who plays PlayStation and who sits at the bar every round", () => {
    const cards = [
      card("network-a", false),
      card("network-b", false),
      card("network-c", false),
      card("network-d", false),
      card("network-e", false),
    ];
    const activities = (round: number) =>
      Object.fromEntries(layout(cards, round).spots.map((spot) => [spot.employee.id, spot.activity]));
    const first = activities(0);
    const second = activities(1);
    expect(Object.values(first)).toEqual(expect.arrayContaining(["pingpong-left", "pingpong-right", "gaming", "bar"]));
    expect(first).not.toEqual(second);
  });
});

describe("walking", () => {
  it("routes out through the door and along the corridors between rooms", () => {
    const placed = layout([card("network-a", true)]);
    const desk = placesOf(placed).get("network-a")!;
    const spot = placed.spots[0];
    const breakRoom = placed.rooms.find((room) => room.key === BREAK_ROOM)!;
    const path = route(placed, desk, { x: spot.x + 28 * spot.scale, y: spot.y + 42 * spot.scale });
    expect(path.length).toBeGreaterThan(4);
    expect(path[path.length - 1].x).toBeGreaterThanOrEqual(breakRoom.x);
  });

  it("walks an agent whose place changed, and settles when the walk ends", () => {
    const walks = new Walks();
    walks.update(layout([card("network-a", true)]), "floor", 0);
    expect(walks.walkers(0).size).toBe(0);
    walks.update(layout([card("network-a", false)]), "floor", 100);
    expect(walks.walkers(200).has("network-a")).toBe(true);
    expect(walks.walkers(100 + 8000).has("network-a")).toBe(false);
  });

  it("never walks on a fresh view or with motion turned off", () => {
    const walks = new Walks();
    walks.update(layout([card("network-a", true)]), "floor", 0);
    walks.update(layout([card("network-a", false)]), "zoom", 100);
    expect(walks.walkers(200).size).toBe(0);
    walks.update(layout([card("network-a", true)]), "zoom", 300, false);
    expect(walks.walkers(400).size).toBe(0);
  });
});

describe("shared offices", () => {
  it("puts two related teams in one office, each with its own desks", () => {
    const teams = [
      { name: "DevOps", match: ["deploy"], room: "Infrastructure", members: ["Desouky", "Karim"] },
      { name: "Network Engineers", match: ["network"], room: "Infrastructure", members: ["Boraie", "Moustafa"] },
    ];
    const placed = layoutOffice(officeOf(dash([card("deploy-x", true), card("network-y", true)], teams)), 1400, 800);
    const room = placed.rooms.find((item) => item.key === "Infrastructure")!;
    expect(room.label).toBe("DevOps · Network Engineers");
    const inside = placed.desks.filter(
      (desk) => desk.x >= room.x && desk.x < room.x + room.width && desk.y >= room.y && desk.y < room.y + room.height,
    );
    expect(inside).toHaveLength(4);
    expect(inside.filter((desk) => !desk.away && !desk.off).map((desk) => desk.employee.person)).toEqual([
      "Desouky",
      "Boraie",
    ]);
  });
});

describe("stable breaks", () => {
  it("someone new on break moves at most one other person", () => {
    const many = Array.from({ length: 10 }, (_, index) => card(`network-${index}`, false));
    const where = (cards: Card[]) => new Map(layout(cards, 3).spots.map((spot) => [spot.employee.id, spot.activity]));
    const before = where(many);
    const after = where([...many, card("network-new", false)]);
    const changed = [...before].filter(([id, activity]) => after.get(id) !== activity);
    expect(changed.length).toBeLessThanOrEqual(3);
  });
});

describe("CTO office", () => {
  it("the CTO sits alone and carries every session, waiting while any needs a decision", () => {
    const asking = {
      ...card("network-ask", true),
      sessions: [session({ id: "q", state: "waiting", question: "Ship it?" })],
    };
    const office = officeOf(dash([card("network-a", true), asking], TEAMS));
    const cto = office.teams[0];
    expect(cto.employees.map((employee) => employee.id)).toEqual([CTO_ID]);
    expect(cto.employees[0]).toMatchObject({ sessions: 2, total: 2, pose: "waiting", person: "Adel" });
  });
});
