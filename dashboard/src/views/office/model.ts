import { cardAgents, needsHuman } from "../../lib/cards";
import type { Card, DashState, Run, Session } from "../../lib/types";

export type OfficeRole = "lead" | "worker" | "helper";
export type OfficePose = "typing" | "reading" | "waiting" | "done" | "idle" | "asleep";

export interface OfficeEmployee {
  id: string;
  name: string;
  role: OfficeRole;
  cardKey: string;
  pose: OfficePose;
  /** The CTO's name, shown above "CTO" on his label. */
  person?: string;
  /** First lines of the last answer, shown in a bubble over a finished leader's desk. */
  answer?: string[];
  bubble: string;
  cost: number | null;
  tokens: number;
  pane: string | null;
  colour: number;
  /** Members of this session (leader, workers, subagents) that are working or waiting, and all of them. */
  sessions: number;
  total: number;
  /** The CTO never leaves the CTO office. */
  fixed?: boolean;
  /** Who this agent delegates to: the session's workers and subagents (the CTO: every session leader). */
  reports?: OfficeEmployee[];
  /** A subagent's desk slot along the walls; it keeps it while others come and go (see Seating). */
  seat?: number;
}

/** One office: the CTO's, or a session's, titled with the session and holding its leader and subagents. */
export interface OfficeTeam {
  key: string;
  label: string;
  employees: OfficeEmployee[];
}

export interface Office {
  name: string;
  teams: OfficeTeam[];
}

export interface PlacedDesk {
  x: number;
  y: number;
  scale: number;
  employee: OfficeEmployee;
}

export const CTO_ID = "cto";
export const CTO_TEAM = "CTO";

const READ_ACTION = /^(?:Read|Grep|Glob|search|rg|WebFetch|WebSearch)\b/i;

function textOf(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function shortBubble(item: Record<string, unknown>): string {
  const text = textOf(item.question || item.ask || item.need || item.said || item.said_full).replace(/\s+/g, " ");
  return text.length <= 60 ? text : `${text.slice(0, 59)}…`;
}

/** The first three lines of the agent's last answer, for the bubble over a finished leader's desk. */
export function answerLines(item: Record<string, unknown>): string[] {
  return textOf(item.said_full || item.said)
    .split("\n")
    .map((line) =>
      line
        .replace(/[*_`#>]/g, "")
        .replace(/\s+/g, " ")
        .trim(),
    )
    .filter(Boolean)
    .slice(0, 3);
}

function colourOf(id: string): number {
  let hash = 2166136261;
  for (const char of id) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
  return (hash >>> 0) % 8;
}

function poseOf(card: Card, item: Record<string, unknown>, role: OfficeRole): OfficePose {
  if (item.state === "waiting" || textOf(item.ask) || textOf(item.question)) return "waiting";
  // The turn ended with an answer and no question: the agent raises its hand with the answer in a bubble.
  if ((item.state === "idle" || item.state === "still_open") && textOf(item.said_full || item.said)) return "done";
  if (role === "lead" && needsHuman(card)) return "waiting";
  if (item.state === "quiet") return "asleep";
  if (item.action_running && READ_ACTION.test(textOf(item.action))) return "reading";
  // A running background shell, subagent or worker run is work in progress: the agent stays at its desk.
  if (item.action_running || item.state === "working" || item.state === "running") return "typing";
  return "idle";
}

function baseEmployee(card: Card, item: Record<string, unknown>, role: OfficeRole, id: string) {
  return {
    sessions: 0,
    total: 1,
    id,
    role,
    cardKey: card.key,
    pose: poseOf(card, item, role),
    bubble: shortBubble(item),
    answer: answerLines(item),
    pane: null as string | null,
    colour: colourOf(id),
  };
}

function leadEmployee(card: Card, lead: Session, panes: Record<string, string>): OfficeEmployee {
  return {
    ...baseEmployee(card, lead, "lead", lead.id),
    name: lead.name || lead.id,
    cost: card.usage?.cost ?? null,
    tokens: Number(card.usage?.tokens || 0),
    pane: panes[lead.id] ?? null,
  };
}

function workerEmployee(card: Card, run: Run, panes: Record<string, string>): OfficeEmployee {
  const record = run as Record<string, unknown>;
  const sid = textOf(record.session || run.run_id || run.id);
  return {
    ...baseEmployee(card, record, "worker", run.id),
    name: [run.mode, run.unit || run.id].filter(Boolean).join(" "),
    cost: null,
    tokens: Number(record.tokens || 0),
    pane: panes[sid] ?? null,
  };
}

function helperEmployee(card: Card, helper: Record<string, unknown>, panes: Record<string, string>): OfficeEmployee {
  const id = textOf(helper.id);
  const sid = textOf(helper.sid);
  return {
    ...baseEmployee(card, helper, "helper", id),
    name: textOf(helper.label) || id,
    cost: null,
    tokens: Number(helper.tokens || 0),
    pane: panes[sid] ?? null,
  };
}

/** Every session of one card: its lead, running implementer runs and subagents. */
export function cardMembers(card: Card, panes: Record<string, string>): OfficeEmployee[] {
  const leads = card.sessions.map((lead) => leadEmployee(card, lead, panes));
  const workers = card.runs.filter((run) => run.state === "running").map((run) => workerEmployee(card, run, panes));
  const helpers = cardAgents(card).map((helper) => helperEmployee(card, helper, panes));
  return [...leads, ...workers, ...helpers];
}

const ACTIVE: OfficePose[] = ["waiting", "typing", "reading", "done"];
const WORKING: OfficePose[] = ["waiting", "typing", "reading"];

/** A leader whose session has finished its work: the desk lamp goes off and the leader sleeps. */
export function finished(employee: OfficeEmployee): boolean {
  return employee.role === "lead" && !employee.fixed && !WORKING.includes(employee.pose);
}

const isShell = (member: OfficeEmployee) => member.name.startsWith("shell · ");

/** A session's office: its leader (the session itself) and everything it has running now: subagents, Codex worker
 * runs and background shells, each at its own desk. */
function sessionOffice(card: Card, panes: Record<string, string>): OfficeTeam | null {
  const members = cardMembers(card, panes);
  const lead = members.find((member) => member.role === "lead");
  if (!lead) return null;
  const workers = members
    .filter(
      (member) => member.role !== "lead" && (isShell(member) ? WORKING.includes(member.pose) : member.pose !== "idle"),
    )
    .map((member) => ({ ...member, sessions: WORKING.includes(member.pose) ? 1 : 0, total: 1 }));
  const label = card.sessions[0]?.name || card.title || card.label || card.key;
  // A leader whose background work still runs has not finished: it keeps working with the lamp on.
  const busy = workers.some((member) => WORKING.includes(member.pose));
  const pose: OfficePose = busy && !WORKING.includes(lead.pose) ? "typing" : lead.pose;
  const leader: OfficeEmployee = {
    ...lead,
    pose,
    name: label,
    cost: card.usage?.cost ?? null,
    tokens: members.reduce((sum, member) => sum + member.tokens, 0),
    // The number on the leader's screen: who works in this office now, the leader and everyone at a desk beside it.
    sessions: (WORKING.includes(pose) ? 1 : 0) + workers.filter((member) => WORKING.includes(member.pose)).length,
    total: 1 + workers.length,
    reports: workers,
  };
  return { key: card.key, label, employees: [leader, ...workers] };
}

/** The CTO runs every session: his desk counts them all; he waits while any needs a decision, else works while any does. */
function ctoOf(leaders: OfficeEmployee[], name: string | undefined): OfficeEmployee {
  const pose = ACTIVE.find((candidate) => leaders.some((agent) => agent.pose === candidate)) || "idle";
  return {
    id: CTO_ID,
    name: "CTO",
    person: name,
    role: "lead",
    cardKey: "",
    pose,
    bubble: "",
    cost: null,
    pane: null,
    colour: 2,
    tokens: leaders.reduce((sum, agent) => sum + agent.tokens, 0),
    // The number on the CTO's screen: sessions, not their subagents or shells.
    sessions: leaders.length,
    total: leaders.length,
    fixed: true,
    reports: leaders,
  };
}

function baseName(path: string): string {
  return path.split("/").filter(Boolean).pop() || "";
}

/** The floor: the CTO's office first, then one office per session. The CTO's name comes from the CTO team's members. */
export function officeOf(state: DashState | null): Office {
  if (!state) return { name: "", teams: [] };
  const sessions = state.cards
    .map((card) => sessionOffice(card, state.session_panes))
    .filter((team): team is OfficeTeam => Boolean(team));
  const name = (state.office_teams || []).find((rule) => rule.name === CTO_TEAM)?.members?.[0];
  const cto = {
    key: CTO_TEAM,
    label: CTO_TEAM,
    employees: [
      ctoOf(
        sessions.map((team) => team.employees[0]),
        name,
      ),
    ],
  };
  return { name: baseName(textOf(state.repo)) || "Company", teams: [cto, ...sessions] };
}

/** Keys in the order first seen: known ones keep their place, new ones join at the end, gone ones drop out. */
export function keepOrder(previous: string[], keys: string[]): string[] {
  const live = new Set(keys);
  const kept = previous.filter((key) => live.has(key));
  return [...kept, ...keys.filter((key) => !kept.includes(key))];
}

/** Seats by id: everyone keeps the seat they had; a newcomer takes the lowest free one. */
export function assignSeats(previous: Map<string, number>, ids: string[]): Map<string, number> {
  const seats = new Map([...previous].filter(([id]) => ids.includes(id)));
  const taken = new Set(seats.values());
  let free = 0;
  for (const id of ids) {
    if (seats.has(id)) continue;
    while (taken.has(free)) free += 1;
    seats.set(id, free);
    taken.add(free);
  }
  return seats;
}

/**
 * Keeps the floor still while agents work. The state lists sessions by last activity, so laying them out in that order
 * moved every desk whenever another session spoke; a subagent's desk likewise followed its position in the list.
 * Seating remembers the session order and each subagent's seat, so desks move only when someone arrives or leaves.
 */
export class Seating {
  private order: string[] = [];
  private seats = new Map<string, Map<string, number>>();

  apply(office: Office): Office {
    const byKey = new Map(office.teams.map((team) => [team.key, team]));
    this.order = keepOrder(
      this.order,
      office.teams.map((team) => team.key),
    );
    const teams = this.order.map((key) => byKey.get(key)!).map((team) => this.seat(team));
    for (const key of this.seats.keys()) if (!byKey.has(key)) this.seats.delete(key);
    return { ...office, teams };
  }

  private seat(team: OfficeTeam): OfficeTeam {
    const [leader, ...workers] = team.employees;
    if (!leader) return team;
    const seats = assignSeats(
      this.seats.get(team.key) || new Map(),
      workers.map((worker) => worker.id),
    );
    this.seats.set(team.key, seats);
    return { ...team, employees: [leader, ...workers.map((worker) => ({ ...worker, seat: seats.get(worker.id) }))] };
  }
}

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface PlacedRoom extends Rect {
  key: string;
  label: string;
  scale: number;
  /** Height of the band along the top that carries the name plate: an office's back wall, a session group's top margin. */
  band: number;
  /** The door gap in an office's bottom wall, opening onto the lobby below. */
  door?: { x: number; width: number; depth: number };
}

export type PlacedBuilding = PlacedRoom;

export interface OfficeLayout {
  building: PlacedBuilding | null;
  /** The walled offices above the lobby: the CTO's and the one Sessions office every session shares. */
  halls: PlacedRoom[];
  /** Each team's place: the CTO's office, and one unmarked group of desks per session on the shared Sessions floor. */
  rooms: PlacedRoom[];
  desks: PlacedDesk[];
  lobby: Rect | null;
  height: number;
}

export const SESSIONS_HALL = "sessions";

const MARGIN = 8;
const DESK_W = 56;
const DESK_H = 58;
/** The wall art may grow to 1.5x the chrome scale when the room has space. */
const decorCap = (chrome: number) => chrome * 1.5;

/** Floor-plan geometry in chrome units: walls, sign band, lobby, office back wall, a session group's top margin and padding. */
export const BUILDING = { wall: 6, wallT: 4, sign: 18, lobby: 44, pad: 6, header: 26, space: 4 };

interface Fit {
  scale: number;
  columns: number;
}

function deskFit(count: number, width: number, height: number): Fit {
  let best: Fit = { scale: 0, columns: 1 };
  for (let columns = 1; columns <= Math.max(1, count); columns += 1) {
    const rows = Math.max(1, Math.ceil(count / columns));
    const scale = Math.min(width / (columns * DESK_W), height / (rows * DESK_H));
    if (scale > best.scale) best = { scale, columns };
  }
  return best;
}

/** Desk size counts up to the 3x cap; past it, spaces shaped like real offices (about 1.4:1) win over long strips. */
function roomScore(scale: number, roomW: number, roomH: number): number {
  const shape = Math.abs(Math.log(Math.max(roomW, 1) / Math.max(roomH, 1) / 1.4));
  return Math.min(scale, 3) - shape * 0.6;
}

/** A session space has room for its leader and two subagents before it grows. */
export const OFFICE_DESKS = 3;

interface Grid {
  columns: number;
  rows: number;
  width: number;
  height: number;
  scale: number;
}

/** Session spaces in rows across the Sessions office floor: the column count giving the largest desks in
 * office-shaped spaces. */
function planSpaces(counts: number[], width: number, height: number, gap: number, cap: number): Grid {
  const inset = { x: 2 * BUILDING.pad * cap, y: (BUILDING.space + BUILDING.pad) * cap };
  let best: Grid = { columns: 1, rows: counts.length, width, height: height / counts.length, scale: 0 };
  let bestScore = -Infinity;
  for (let columns = 1; columns <= counts.length; columns += 1) {
    const rows = Math.ceil(counts.length / columns);
    const w = (width - (columns - 1) * gap) / columns;
    const h = (height - (rows - 1) * gap) / rows;
    const scale = Math.min(...counts.map((count) => deskFit(count, w - inset.x, h - inset.y).scale));
    const score = roomScore(scale, w, h);
    if (scale > 0 && score > bestScore) {
      bestScore = score;
      best = { columns, rows, width: w, height: h, scale };
    }
  }
  return best;
}

/** Subagent desks are smaller than the leader's. */
export const SUBAGENT_SCALE = 0.6;

/** A team's space: the leader's desk in the middle, its subagents at smaller desks right beside it, the first on the
 * right, then the left, alternating, each side filling a column top to bottom (then the next column outwards). */
function placeTeam(team: OfficeTeam, room: PlacedRoom | undefined, scale: number): PlacedDesk[] {
  const [leader, ...workers] = team.employees;
  if (!leader || !room) return [];
  const d = room.scale;
  const floorTop = room.y + room.band;
  const floorH = room.y + room.height - floorTop;
  const lead = {
    x: room.x + (room.width - DESK_W * scale) / 2,
    y: floorTop + (floorH - DESK_H * scale) / 2,
    scale,
    employee: leader,
  };
  const small = scale * SUBAGENT_SCALE;
  const pad = BUILDING.pad * d;
  const perColumn = Math.max(1, Math.floor((floorH - pad) / (DESK_H * small)));
  // Columns start level with the leader's desk, moved up only as far as needed to keep a full column on the floor.
  const top = Math.max(floorTop + pad / 2, Math.min(lead.y, room.y + room.height - perColumn * DESK_H * small));
  const placed = workers.map((employee, position) => {
    const index = employee.seat ?? position;
    const slot = Math.floor(index / 2);
    const column = Math.floor(slot / perColumn);
    const x =
      index % 2 === 0 ? lead.x + DESK_W * scale + column * DESK_W * small : lead.x - (column + 1) * DESK_W * small;
    return { x, y: top + (slot % perColumn) * DESK_H * small, scale: small, employee };
  });
  return [lead, ...placed];
}

export const EMPTY_LAYOUT: OfficeLayout = { building: null, halls: [], rooms: [], desks: [], lobby: null, height: 0 };

const quantise = (scale: number) => Math.max(0.5, Math.min(3, Math.floor(scale * 4) / 4));

function hallOf(key: string, label: string, rect: Rect, decor: number, chrome: number, centred: boolean): PlacedRoom {
  const width = Math.min(20 * decor, rect.width / 3);
  const x = centred ? rect.x + (rect.width - width) / 2 : rect.x + 10 * decor;
  return {
    key,
    label,
    ...rect,
    scale: decor,
    band: BUILDING.header * decor,
    door: { x, width, depth: BUILDING.wallT * chrome },
  };
}

/** The session spaces on the Sessions office floor, row by row; the last row's spaces share the full width. */
function placeSpaces(teams: OfficeTeam[], grid: Grid, floor: Rect, gap: number, decor: number): PlacedRoom[] {
  const lastRow = Math.floor((teams.length - 1) / grid.columns);
  const lastCount = teams.length - lastRow * grid.columns;
  return teams.map((team, index) => {
    const row = Math.floor(index / grid.columns);
    const width = row === lastRow ? (floor.width - (lastCount - 1) * gap) / lastCount : grid.width;
    return {
      key: team.key,
      label: team.label,
      x: floor.x + (index % grid.columns) * (width + gap),
      y: floor.y + row * (grid.height + gap),
      width,
      height: grid.height,
      scale: decor,
      band: BUILDING.space * decor,
    };
  });
}

/** Where the two offices go above the lobby: side by side, or stacked on a narrow canvas. */
interface Split {
  side: boolean;
  stacked: boolean;
  cto: Rect | null;
  hall: Rect;
}

function splitFloor(inner: Rect, areaH: number, chrome: number, cto: boolean, sessions: boolean): Split {
  const wall = BUILDING.wall * chrome;
  const side = cto && sessions && inner.width >= 320 * chrome;
  const stacked = cto && sessions && !side;
  const ctoW = side ? Math.round(Math.min(inner.width * 0.3, Math.max(inner.width * 0.2, 140 * chrome))) : inner.width;
  const ctoH = stacked ? Math.max(areaH * 0.3, (BUILDING.header + BUILDING.pad) * decorCap(chrome) + DESK_H) : areaH;
  const offset = { x: side ? ctoW + wall : 0, y: stacked ? ctoH + wall : 0 };
  return {
    side,
    stacked,
    cto: cto ? { x: inner.x, y: inner.y, width: ctoW, height: ctoH } : null,
    hall: { x: inner.x + offset.x, y: inner.y + offset.y, width: inner.width - offset.x, height: areaH - offset.y },
  };
}

/** One desk scale for the whole floor: the largest that fits every session space and the CTO office. */
function floorScale(split: Split, grid: Grid | null, chrome: number): number {
  const cap = decorCap(chrome);
  const cto = split.cto
    ? deskFit(1, split.cto.width - 2 * BUILDING.pad * cap, split.cto.height - (BUILDING.header + BUILDING.pad) * cap)
        .scale
    : 3;
  return quantise(Math.min(grid ? grid.scale : 3, cto));
}

/** Grow the offices to fit their desks at the chosen scale, keeping side-by-side offices the same height. */
function growOffices(split: Split, grid: Grid | null, scale: number, decor: number, gap: number, wall: number): void {
  const { cto, hall } = split;
  if (cto) cto.height = Math.max(cto.height, (BUILDING.header + BUILDING.pad) * decor + DESK_H * scale);
  if (!grid) return;
  grid.height = Math.max(grid.height, (BUILDING.space + BUILDING.pad) * decor + DESK_H * scale);
  const needed = BUILDING.header * decor + 1.5 * gap + grid.rows * grid.height + (grid.rows - 1) * gap;
  hall.height = Math.max(hall.height, needed);
  if (split.stacked && cto) hall.y = cto.y + cto.height + wall;
  if (split.side && cto) hall.height = cto.height = Math.max(cto.height, hall.height);
}

/** The lobby under the offices and the building around everything. */
function shellOf(name: string, inner: Rect, halls: PlacedRoom[], width: number, chrome: number) {
  const bottom = Math.max(...halls.map((hall) => hall.y + hall.height));
  const lobby = {
    x: inner.x,
    y: bottom + BUILDING.wallT * chrome,
    width: inner.width,
    height: BUILDING.lobby * chrome,
  };
  const end = lobby.y + lobby.height + BUILDING.wall * chrome;
  const building = { key: "building", label: name, x: MARGIN, y: MARGIN, width, height: end - MARGIN, scale: chrome };
  return { building: { ...building, band: BUILDING.sign * chrome }, lobby, height: end + MARGIN };
}

/** Fit the floor plan to the canvas: the CTO office and the shared Sessions office (one space per session) above the
 * lobby. Grows past the canvas when desks cannot shrink further. */
export function layoutOffice(office: Office, width: number, height: number, chrome = 2): OfficeLayout {
  if (!office.teams.length) return EMPTY_LAYOUT;
  const b = (key: keyof typeof BUILDING) => BUILDING[key] * chrome;
  const bw = Math.max(width, 240) - 2 * MARGIN;
  const bh = Math.max(height, 240) - 2 * MARGIN;
  const inner = {
    x: MARGIN + b("wall"),
    y: MARGIN + b("sign"),
    width: bw - 2 * b("wall"),
    height: bh - b("sign") - b("wall"),
  };
  const cto = office.teams.find((team) => team.key === CTO_TEAM);
  const sessions = office.teams.filter((team) => team.key !== CTO_TEAM);
  const split = splitFloor(inner, inner.height - b("lobby") - b("wallT"), chrome, Boolean(cto), sessions.length > 0);
  const gap = 2 * BUILDING.pad * chrome;
  const floorH = split.hall.height - BUILDING.header * decorCap(chrome) - 1.5 * gap;
  const counts = sessions.map((team) => Math.max(OFFICE_DESKS, team.employees.length));
  const grid = sessions.length ? planSpaces(counts, split.hall.width - 2 * gap, floorH, gap, decorCap(chrome)) : null;
  const scale = floorScale(split, grid, chrome);
  const decor = Math.max(chrome, Math.min(decorCap(chrome), scale));
  growOffices(split, grid, scale, decor, gap, b("wall"));
  const halls: PlacedRoom[] = [];
  if (split.cto) halls.push(hallOf(CTO_TEAM, CTO_TEAM, split.cto, decor, chrome, false));
  const floor = {
    x: split.hall.x + gap,
    y: split.hall.y + BUILDING.header * decor + gap / 2,
    width: split.hall.width - 2 * gap,
    height: 0,
  };
  const spaces = grid ? placeSpaces(sessions, grid, floor, gap, decor) : [];
  if (grid) halls.push(hallOf(SESSIONS_HALL, "Sessions", split.hall, decor, chrome, true));
  const rooms = [...halls.filter((hall) => hall.key === CTO_TEAM), ...spaces];
  const desks = office.teams.flatMap((team) =>
    placeTeam(
      team,
      rooms.find((item) => item.key === team.key),
      scale,
    ),
  );
  const { building, lobby, height: total } = shellOf(office.name, inner, halls, bw, chrome);
  return { building, halls, rooms, desks, lobby, height: total };
}
