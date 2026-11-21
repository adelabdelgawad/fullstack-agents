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
  /** The door gap in the room's bottom wall, opening onto the corridor or lobby below. */
  door?: { x: number; width: number; depth: number };
}

export type PlacedBuilding = PlacedRoom;

export interface OfficeLayout {
  building: PlacedBuilding | null;
  rooms: PlacedRoom[];
  desks: PlacedDesk[];
  /** The small assets warehouse at the right end of the lobby: spare desks that subagents fetch and return. */
  warehouse: Rect | null;
  corridors: Rect[];
  lobby: Rect | null;
  height: number;
}

const MARGIN = 8;
const DESK_W = 56;
const DESK_H = 58;
/** The wall art may grow to 1.5x the chrome scale when the room has space. */
const decorCap = (chrome: number) => chrome * 1.5;

/** Floor-plan geometry in chrome units: walls, sign band, corridors, spine corridor, lobby, room header and padding. */
export const BUILDING = { wall: 6, wallT: 4, sign: 18, corridor: 22, spine: 26, lobby: 44, pad: 6, header: 26 };

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

interface Plan {
  columns: number;
  rows: number;
  roomW: number;
  roomH: number;
  scale: number;
}

/** Desk size counts up to the 3x cap; past it, rooms shaped like real offices (about 1.4:1) win over long strips. */
function roomScore(scale: number, roomW: number, roomH: number): number {
  const shape = Math.abs(Math.log(Math.max(roomW, 1) / Math.max(roomH, 1) / 1.4));
  return Math.min(scale, 3) - shape * 0.6;
}

/** Rows of rooms, a corridor under every row but the last (which opens onto the lobby), a spine corridor on the right. */
function planGrid(counts: number[], innerW: number, innerH: number, chrome: number): Plan {
  const b = (key: keyof typeof BUILDING) => BUILDING[key] * chrome;
  const cap = decorCap(chrome);
  const inset = { x: 2 * BUILDING.pad * cap, y: (BUILDING.header + BUILDING.pad) * cap };
  let best: Plan = { columns: 1, rows: 1, roomW: 0, roomH: 0, scale: -1 };
  let bestScore = -Infinity;
  for (let columns = 1; columns <= counts.length; columns += 1) {
    const rows = Math.ceil(counts.length / columns);
    const spine = rows > 1 ? b("spine") + b("wallT") : 0;
    const roomW = (innerW - spine - (columns - 1) * b("wall")) / columns;
    const roomH = (innerH - b("lobby") - rows * b("wallT") - (rows - 1) * b("corridor")) / rows;
    const scale = Math.min(...counts.map((count) => deskFit(count, roomW - inset.x, roomH - inset.y).scale));
    const score = roomScore(scale, roomW, roomH);
    if (scale > 0 && score > bestScore) {
      bestScore = score;
      best = { columns, rows, roomW, roomH, scale };
    }
  }
  if (best.scale < 0)
    best = { columns: 1, rows: counts.length, roomW: innerW, roomH: innerH / counts.length, scale: 0.5 };
  return { ...best, scale: Math.max(0.5, Math.min(3, Math.floor(best.scale * 4) / 4)) };
}

/** A session office has room for its leader and two subagents before it grows. */
export const OFFICE_DESKS = 3;

function deskCount(team: OfficeTeam): number {
  return team.key === CTO_TEAM ? 1 : Math.max(OFFICE_DESKS, team.employees.length);
}

interface Spec {
  key: string;
  label: string;
  count: number;
}

function placeRooms(specs: Spec[], plan: Plan, origin: { x: number; y: number }, chrome: number): PlacedRoom[] {
  const b = (key: keyof typeof BUILDING) => BUILDING[key] * chrome;
  const decor = Math.max(chrome, Math.min(decorCap(chrome), plan.scale));
  const rowWidth = plan.columns * plan.roomW + (plan.columns - 1) * b("wall");
  const lastRow = Math.floor((specs.length - 1) / plan.columns);
  const lastCount = specs.length - lastRow * plan.columns;
  return specs.map((spec, index) => {
    const row = Math.floor(index / plan.columns);
    const width = row === lastRow ? (rowWidth - (lastCount - 1) * b("wall")) / lastCount : plan.roomW;
    const x = origin.x + (index % plan.columns) * (width + b("wall"));
    const y = origin.y + row * (plan.roomH + b("wallT") + b("corridor"));
    const room: PlacedRoom = { key: spec.key, label: spec.label, x, y, width, height: plan.roomH, scale: decor };
    room.door = { x: x + 10 * decor, width: Math.min(20 * decor, width / 3), depth: b("wallT") };
    return room;
  });
}

function circulation(plan: Plan, inner: Rect, chrome: number): { corridors: Rect[]; lobby: Rect } {
  const b = (key: keyof typeof BUILDING) => BUILDING[key] * chrome;
  const lobby = { x: inner.x, y: inner.y + inner.height - b("lobby"), width: inner.width, height: b("lobby") };
  const corridors: Rect[] = [];
  for (let row = 0; row < plan.rows - 1; row += 1) {
    const y = inner.y + (row + 1) * (plan.roomH + b("wallT")) + row * b("corridor");
    corridors.push({ x: inner.x, y, width: inner.width, height: b("corridor") });
  }
  if (corridors.length) {
    const top = inner.y;
    corridors.push({ x: inner.x + inner.width - b("spine"), y: top, width: b("spine"), height: lobby.y - top });
  }
  return { corridors, lobby };
}

/** Subagent desks are smaller than the leader's. */
export const SUBAGENT_SCALE = 0.6;

/** A session office: the leader's desk in the middle, its subagents at smaller desks along the side walls, the first on
 * the right wall, then the left, alternating, each wall filling top to bottom (then a second row inwards). */
function placeTeam(team: OfficeTeam, room: PlacedRoom, scale: number): PlacedDesk[] {
  const [leader, ...workers] = team.employees;
  if (!leader) return [];
  const d = room.scale;
  const floorTop = room.y + BUILDING.header * d;
  const floorH = room.y + room.height - floorTop;
  const lead = {
    x: room.x + (room.width - DESK_W * scale) / 2,
    y: floorTop + (floorH - DESK_H * scale) / 2,
    scale,
    employee: leader,
  };
  const small = scale * SUBAGENT_SCALE;
  const pad = BUILDING.pad * d;
  const perWall = Math.max(1, Math.floor((floorH - pad) / (DESK_H * small)));
  const placed = workers.map((employee, index) => {
    const right = index % 2 === 0;
    const slot = Math.floor(index / 2);
    const row = slot % perWall;
    const inward = Math.floor(slot / perWall) * DESK_W * small;
    const x = right ? room.x + room.width - pad - DESK_W * small - inward : room.x + pad + inward;
    return { x, y: floorTop + pad / 2 + row * DESK_H * small, scale: small, employee };
  });
  return [lead, ...placed];
}

/** The assets warehouse: a small storeroom at the right end of the lobby. */
function warehouseOf(lobby: Rect, chrome: number): Rect {
  const width = Math.min(90 * chrome, lobby.width / 4);
  return {
    x: lobby.x + lobby.width - width - 6 * chrome,
    y: lobby.y + 4 * chrome,
    width,
    height: lobby.height - 8 * chrome,
  };
}

export const EMPTY_LAYOUT: OfficeLayout = {
  building: null,
  rooms: [],
  desks: [],
  warehouse: null,
  corridors: [],
  lobby: null,
  height: 0,
};

/** Fit the floor plan to the canvas: the CTO office and one office per session along corridors, the lobby below. */
export function layoutOffice(office: Office, width: number, height: number, chrome = 2): OfficeLayout {
  if (!office.teams.length) return EMPTY_LAYOUT;
  const specs: Spec[] = office.teams.map((team) => ({ key: team.key, label: team.label, count: deskCount(team) }));
  const edge = BUILDING.wall * chrome;
  const bw = Math.max(width, 240) - 2 * MARGIN;
  const bh = Math.max(height, 240) - 2 * MARGIN;
  const inner = {
    x: MARGIN + edge,
    y: MARGIN + BUILDING.sign * chrome,
    width: bw - 2 * edge,
    height: bh - BUILDING.sign * chrome - edge,
  };
  const plan = planGrid(
    specs.map((spec) => spec.count),
    inner.width,
    inner.height,
    chrome,
  );
  plan.roomH = Math.max(plan.roomH, (BUILDING.header + BUILDING.pad) * decorCap(chrome) + DESK_H * plan.scale);
  const rooms = placeRooms(specs, plan, inner, chrome);
  const desks = office.teams.flatMap((team, index) => placeTeam(team, rooms[index], plan.scale));
  const used = {
    ...inner,
    height: Math.max(
      inner.height,
      rooms[rooms.length - 1].y + plan.roomH + BUILDING.wallT * chrome + BUILDING.lobby * chrome - inner.y,
    ),
  };
  const { corridors, lobby } = circulation(plan, used, chrome);
  const bottom = used.y + used.height + edge;
  const building = {
    key: "building",
    label: office.name,
    x: MARGIN,
    y: MARGIN,
    width: bw,
    height: bottom - MARGIN,
    scale: chrome,
  };
  return { building, rooms, desks, warehouse: warehouseOf(lobby, chrome), corridors, lobby, height: bottom + MARGIN };
}
