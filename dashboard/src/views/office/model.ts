import { cardAgents, needsHuman } from "../../lib/cards";
import type { Card, DashState, OfficeTeamRule, Run, Session } from "../../lib/types";

export type OfficeRole = "lead" | "worker" | "helper";
export type OfficePose = "typing" | "reading" | "waiting" | "done" | "idle" | "asleep";

export interface OfficeEmployee {
  id: string;
  name: string;
  role: OfficeRole;
  cardKey: string;
  pose: OfficePose;
  /** First lines of the last answer, shown in a bubble while the agent has its hand up. */
  answer?: string[];
  bubble: string;
  cost: number | null;
  tokens: number;
  pane: string | null;
  colour: number;
  /** Sessions of this agent (lead, workers, subagents) that are working or waiting, and all of them. */
  sessions: number;
  total: number;
  /** Planning or design work: the agent sits in the meeting room instead of at its desk. */
  meeting?: boolean;
  /** The CTO never leaves the CTO office. */
  fixed?: boolean;
  /** Who this agent delegates to: its card's workers and subagents (the CTO: every agent). */
  reports?: OfficeEmployee[];
}

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
  /** The employee is in the break room; the desk stays, empty, with its computer off. */
  away?: boolean;
}

export type BreakActivity = "coffee" | "pingpong-left" | "pingpong-right" | "meeting";

export interface PlacedSpot {
  x: number;
  y: number;
  scale: number;
  employee: OfficeEmployee;
  activity: BreakActivity;
  /** Meeting seats: the side of the table the agent sits on. */
  seat?: "north" | "south";
}

export const BREAK_ROOM = "break";
export const MEETING_ROOM = "meeting";
export const CTO_ID = "cto";
export const CTO_TEAM = "CTO";

/** Idle and sleeping agents leave their desk for the break room; working and waiting agents stay at it. */
export function isAway(employee: OfficeEmployee): boolean {
  return !employee.fixed && employee.sessions === 0;
}

export function inMeeting(employee: OfficeEmployee): boolean {
  return !isAway(employee) && Boolean(employee.meeting);
}

const MEETING_PHASES = /^(?:plan|design)/i;

const READ_ACTION = /^(?:Read|Grep|Glob|search|rg|WebFetch|WebSearch)\b/i;

function textOf(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function shortBubble(item: Record<string, unknown>): string {
  const text = textOf(item.question || item.ask || item.need || item.said || item.said_full).replace(/\s+/g, " ");
  return text.length <= 60 ? text : `${text.slice(0, 59)}…`;
}

/** The first three lines of the agent's last answer, for the raised-hand bubble. */
export function answerLines(item: Record<string, unknown>): string[] {
  return textOf(item.said_full || item.said)
    .split("\n")
    .map((line) => line.replace(/[*_`#>]/g, "").replace(/\s+/g, " ").trim())
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

/** One agent per card: its desk computer is on while one or more of its sessions works or waits. */
function agentOf(card: Card, panes: Record<string, string>): OfficeEmployee | null {
  const members = cardMembers(card, panes);
  const lead = members.find((member) => member.role === "lead") || members[0];
  if (!lead) return null;
  const active = members.filter((member) => ACTIVE.includes(member.pose));
  const pose = ACTIVE.find((candidate) => active.some((member) => member.pose === candidate))
    || (members.every((member) => member.pose === "asleep") ? "asleep" : "idle");
  return {
    ...lead,
    id: card.key,
    name: lead.role === "lead" ? lead.name : card.title || lead.name,
    pose,
    bubble: active.find((member) => member.bubble)?.bubble || lead.bubble,
    answer: pose === "done" ? active.find((member) => member.pose === "done")?.answer || [] : [],
    cost: card.usage?.cost ?? null,
    tokens: members.reduce((sum, member) => sum + member.tokens, 0),
    colour: colourOf(card.key),
    sessions: active.length,
    total: members.length,
    meeting: MEETING_PHASES.test(textOf(card.phase)),
    reports: members.filter((member) => member !== lead),
  };
}

/** The CTO leads every agent: at the desk always, busy while any agent works, waiting while any agent waits. */
function ctoOf(agents: OfficeEmployee[]): OfficeEmployee {
  const pose = ACTIVE.find((candidate) => agents.some((agent) => agent.pose === candidate)) || "idle";
  return {
    id: CTO_ID, name: "CTO", role: "lead", cardKey: "", pose, bubble: "", cost: null, pane: null, colour: 2,
    tokens: agents.reduce((sum, agent) => sum + agent.tokens, 0),
    sessions: agents.reduce((sum, agent) => sum + agent.sessions, 0),
    total: agents.length,
    fixed: true,
    reports: agents,
  };
}

function baseName(path: string): string {
  return path.split("/").filter(Boolean).pop() || "";
}

export const GENERAL_TEAM = "General";

function cardText(card: Card): string {
  const names = card.sessions.map((lead) => lead.name || "");
  return [card.title, card.label, card.tree?.branch, baseName(textOf(card.repo)), ...names].join(" ").toLowerCase();
}

function matches(text: string, word: string): boolean {
  const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(^|[^a-z0-9])${escaped}`).test(text);
}

/** A card (a lead session with its workers) joins the first department whose keyword starts a word in its text. */
export function departmentOf(card: Card, rules: OfficeTeamRule[]): string {
  const text = cardText(card);
  return rules.find((rule) => rule.match.some((word) => matches(text, word)))?.name || GENERAL_TEAM;
}

/** Every department has an office, empty or not; General opens only when a session matches no department. */
export function officeOf(state: DashState | null): Office {
  if (!state) return { name: "", teams: [] };
  const rules = state.office_teams || [];
  const teams = new Map<string, OfficeTeam>(rules.map((rule) => [rule.name, { key: rule.name, label: rule.name, employees: [] }]));
  for (const card of state.cards) {
    const key = departmentOf(card, rules);
    const team = teams.get(key) || { key, label: key, employees: [] };
    const agent = agentOf(card, state.session_panes);
    if (agent) team.employees.push(agent);
    teams.set(key, team);
  }
  const cto = teams.get(CTO_TEAM) || { key: CTO_TEAM, label: CTO_TEAM, employees: [] };
  cto.employees.unshift(ctoOf([...teams.values()].flatMap((team) => team.employees)));
  teams.delete(CTO_TEAM);
  return { name: baseName(textOf(state.repo)) || "Company", teams: [cto, ...teams.values()] };
}

export function teamOfEmployee(office: Office, id: string): OfficeTeam | undefined {
  return office.teams.find((team) => team.employees.some((employee) => employee.id === id));
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
  /** Fixed furniture: the meeting table or the table-tennis table, in desk-scale pixels. */
  table?: Rect;
}

export type PlacedBuilding = PlacedRoom;

export interface OfficeLayout {
  building: PlacedBuilding | null;
  rooms: PlacedRoom[];
  desks: PlacedDesk[];
  spots: PlacedSpot[];
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
  if (best.scale < 0) best = { columns: 1, rows: counts.length, roomW: innerW, roomH: innerH / counts.length, scale: 0.5 };
  return { ...best, scale: Math.max(0.5, Math.min(3, Math.floor(best.scale * 4) / 4)) };
}

/** Desks spread over the room floor like an office: each sits centred in its cell, cells at most 1.8x a desk. */
function placeCells(count: number, room: PlacedRoom, scale: number): { x: number; y: number; columns: number }[] {
  const d = room.scale;
  const innerW = room.width - 2 * BUILDING.pad * d;
  const innerH = room.height - (BUILDING.header + BUILDING.pad) * d;
  const { columns } = deskFit(count, innerW, innerH);
  const rows = Math.max(1, Math.ceil(count / columns));
  const cellW = Math.max(DESK_W * scale, Math.min(innerW / columns, DESK_W * scale * 1.8));
  const cellH = Math.max(DESK_H * scale, Math.min(innerH / rows, DESK_H * scale * 1.5));
  const left = room.x + (room.width - columns * cellW) / 2 + (cellW - DESK_W * scale) / 2;
  const top = room.y + BUILDING.header * d + Math.max(0, (innerH - rows * cellH) / 2) + (cellH - DESK_H * scale) / 2;
  return Array.from({ length: count }, (_, index) => ({
    x: left + (index % columns) * cellW,
    y: top + Math.floor(index / columns) * cellH,
    columns,
  }));
}

/** Every department office seats TEAM_DESKS; the CTO office seats the CTO alone. */
export const TEAM_DESKS = 4;

function deskCount(team: OfficeTeam): number {
  return team.employees.some((employee) => employee.fixed) ? team.employees.length : Math.max(TEAM_DESKS, team.employees.length);
}

/** Agents on a running session sit at a lit PC first; the rest of the office's desks stand empty, computer off. */
function placeDesks(team: OfficeTeam, room: PlacedRoom, scale: number): PlacedDesk[] {
  const cells = placeCells(deskCount(team), room, scale);
  const seated = (employee: OfficeEmployee) => !isAway(employee) && !inMeeting(employee);
  const order = [...team.employees.filter(seated), ...team.employees.filter((employee) => !seated(employee))];
  return cells.map((cell, index) => {
    const employee = order[index];
    if (!employee) return { ...cell, scale, employee: { ...teamMember(team), id: `vacant:${team.key}:${index}` }, away: true };
    return { ...cell, scale, employee, away: !seated(employee) };
  });
}

/** The first pair plays at the fixed table; everyone else queues for coffee along the left of the room. */
function placeBreak(away: OfficeEmployee[], room: PlacedRoom, s: number): PlacedSpot[] {
  const table = room.table!;
  const d = room.scale;
  const top = room.y + BUILDING.header * d + 26 * d;
  let col = 0;
  let y = top;
  return away.map((employee, index) => {
    if (away.length > 1 && index < 2) {
      const x = table.x - 24 * s + index * DESK_W * s;
      return { x, y: table.y - 24 * s, scale: s, employee, activity: index ? "pingpong-right" : "pingpong-left" };
    }
    let x = room.x + 10 * d - 22 * s + col * 26 * s;
    if (col > 0 && x + 52 * s > table.x - 8 * s) {
      col = 0;
      y += 52 * s;
      x = room.x + 10 * d - 22 * s;
    }
    col += 1;
    return { x, y, scale: s, employee, activity: "coffee" as BreakActivity };
  });
}

/** Meeting seats along both long sides of the table. */
function placeMeeting(people: OfficeEmployee[], room: PlacedRoom, s: number): PlacedSpot[] {
  const table = room.table!;
  const perSide = Math.max(1, Math.ceil(people.length / 2));
  const step = table.width / perSide;
  return people.map((employee, index) => {
    const side = index % 2;
    const seat = Math.floor(index / 2);
    const x = table.x + step * (seat + 0.5) - 28 * s;
    // Spot y keeps the desk convention (name label at y + 48s): above a north seat, below a south seat.
    const y = side ? table.y + table.height + s - 24 * s : table.y - 22 * s - 58 * s;
    return { x, y, scale: s, employee, activity: "meeting" as BreakActivity, seat: side ? "south" : "north" } as PlacedSpot;
  });
}

function furnish(room: PlacedRoom, s: number, seats: number): PlacedRoom {
  const d = room.scale;
  const floorTop = room.y + BUILDING.header * d;
  const floorH = room.y + room.height - floorTop;
  if (room.key === BREAK_ROOM) {
    const t = Math.min(s, (room.width - 8 * d) / 112);
    const width = 64 * t;
    const x = room.x + Math.max(room.width / 2 - width / 2, Math.min(room.width - width - 32 * t, room.width - width - 4 * d));
    return { ...room, table: { x, y: floorTop + floorH / 2 - 7 * t, width, height: 14 * t } };
  }
  if (room.key === MEETING_ROOM) {
    const width = Math.min(room.width - 40 * d, Math.max(90 * s, Math.ceil(seats / 2) * 34 * s));
    return { ...room, table: { x: room.x + (room.width - width) / 2, y: floorTop + floorH / 2 - 10 * s, width, height: 22 * s } };
  }
  return room;
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
    return furnish(room, plan.scale, spec.count);
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

/** A department with nobody at a desk (no running work) takes its break: it shows in the Break Room. */
function teamOnBreak(team: OfficeTeam): boolean {
  return !team.employees.some((employee) => employee.fixed || (!isAway(employee) && !inMeeting(employee)));
}

/** The department's stand-in for the Break Room: named after the team, with no card behind it. */
function teamMember(team: OfficeTeam): OfficeEmployee {
  return {
    id: `team:${team.key}`, name: team.label, role: "helper", cardKey: "", pose: "idle", bubble: "", pane: null,
    colour: colourOf(team.key), sessions: 0, total: 0, cost: null, tokens: 0,
  };
}

export const EMPTY_LAYOUT: OfficeLayout = { building: null, rooms: [], desks: [], spots: [], corridors: [], lobby: null, height: 0 };

/** Fit one company floor plan to the canvas: department offices, a meeting room and a break room along corridors. */
export function layoutOffice(office: Office, width: number, height: number, chrome = 2, common = true): OfficeLayout {
  if (!office.teams.length) return EMPTY_LAYOUT;
  const everyone = office.teams.flatMap((team) => team.employees);
  const away = [...everyone.filter(isAway), ...office.teams.filter(teamOnBreak).map(teamMember)];
  const meeting = everyone.filter(inMeeting);
  const shared: Spec[] = [{ key: MEETING_ROOM, label: "Meeting Room", count: Math.max(4, meeting.length) },
    { key: BREAK_ROOM, label: "Break Room", count: Math.max(2, away.length) }];
  const specs: Spec[] = [...office.teams.map((team) => ({ key: team.key, label: team.label, count: deskCount(team) })),
    ...(common ? shared : [])];
  const edge = BUILDING.wall * chrome;
  const bw = Math.max(width, 240) - 2 * MARGIN;
  const bh = Math.max(height, 240) - 2 * MARGIN;
  const inner = { x: MARGIN + edge, y: MARGIN + BUILDING.sign * chrome, width: bw - 2 * edge, height: bh - BUILDING.sign * chrome - edge };
  const plan = planGrid(specs.map((spec) => spec.count), inner.width, inner.height, chrome);
  plan.roomH = Math.max(plan.roomH, (BUILDING.header + BUILDING.pad) * decorCap(chrome) + DESK_H * plan.scale);
  const rooms = placeRooms(specs, plan, inner, chrome);
  const roomOf = (key: string) => rooms.find((room) => room.key === key)!;
  const desks = office.teams.flatMap((team, index) => placeDesks(team, rooms[index], plan.scale));
  const spots = !common ? [] : [...placeBreak(away, roomOf(BREAK_ROOM), plan.scale), ...placeMeeting(meeting, roomOf(MEETING_ROOM), plan.scale)];
  const used = { ...inner, height: Math.max(inner.height, rooms[rooms.length - 1].y + plan.roomH + BUILDING.wallT * chrome + BUILDING.lobby * chrome - inner.y) };
  const { corridors, lobby } = circulation(plan, used, chrome);
  const bottom = used.y + used.height + edge;
  const building = { key: "building", label: office.name, x: MARGIN, y: MARGIN, width: bw, height: bottom - MARGIN, scale: chrome };
  return { building, rooms, desks, spots, corridors, lobby, height: bottom + MARGIN };
}
