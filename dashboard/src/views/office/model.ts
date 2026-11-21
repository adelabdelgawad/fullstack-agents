import { cardAgents, needsHuman } from "../../lib/cards";
import type { Card, DashState, OfficeTeamRule, Run, Session } from "../../lib/types";

export type OfficeRole = "lead" | "worker" | "helper";
export type OfficePose = "typing" | "reading" | "waiting" | "idle" | "asleep";

export interface OfficeEmployee {
  id: string;
  name: string;
  role: OfficeRole;
  cardKey: string;
  pose: OfficePose;
  bubble: string;
  cost: number | null;
  tokens: number;
  pane: string | null;
  colour: number;
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

export type BreakActivity = "coffee" | "pingpong-left" | "pingpong-right";

export interface PlacedSpot {
  x: number;
  y: number;
  scale: number;
  employee: OfficeEmployee;
  activity: BreakActivity;
}

export const BREAK_ROOM = "break";

/** Idle and sleeping agents leave their desk for the break room; working and waiting agents stay at it. */
export function isAway(employee: OfficeEmployee): boolean {
  return employee.pose === "idle" || employee.pose === "asleep";
}

const READ_ACTION = /^(?:Read|Grep|Glob|search|rg|WebFetch|WebSearch)\b/i;

function textOf(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function shortBubble(item: Record<string, unknown>): string {
  const text = textOf(item.question || item.ask || item.need || item.said || item.said_full).replace(/\s+/g, " ");
  return text.length <= 60 ? text : `${text.slice(0, 59)}…`;
}

function colourOf(id: string): number {
  let hash = 2166136261;
  for (const char of id) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
  return (hash >>> 0) % 8;
}

function poseOf(card: Card, item: Record<string, unknown>, role: OfficeRole): OfficePose {
  if ((role === "lead" && needsHuman(card)) || textOf(item.ask) || textOf(item.question)) return "waiting";
  if (item.state === "quiet") return "asleep";
  if (item.action_running && READ_ACTION.test(textOf(item.action))) return "reading";
  if (item.action_running || item.state === "working") return "typing";
  return "idle";
}

function baseEmployee(card: Card, item: Record<string, unknown>, role: OfficeRole, id: string) {
  return {
    id,
    role,
    cardKey: card.key,
    pose: poseOf(card, item, role),
    bubble: shortBubble(item),
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

function cardEmployees(card: Card, panes: Record<string, string>): OfficeEmployee[] {
  const leads = card.sessions.map((lead) => leadEmployee(card, lead, panes));
  const workers = card.runs.filter((run) => run.state === "running").map((run) => workerEmployee(card, run, panes));
  const helpers = cardAgents(card).map((helper) => helperEmployee(card, helper, panes));
  return [...leads, ...workers, ...helpers];
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
    team.employees.push(...cardEmployees(card, state.session_panes));
    teams.set(key, team);
  }
  return { name: baseName(textOf(state.repo)) || "Company", teams: [...teams.values()] };
}

export function teamOfEmployee(office: Office, id: string): OfficeTeam | undefined {
  return office.teams.find((team) => team.employees.some((employee) => employee.id === id));
}

export interface PlacedRoom {
  key: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  scale: number;
}

export type PlacedBuilding = PlacedRoom;

export interface OfficeLayout {
  building: PlacedBuilding | null;
  rooms: PlacedRoom[];
  desks: PlacedDesk[];
  spots: PlacedSpot[];
  height: number;
}

const MARGIN = 8;
const DESK_W = 56;
const DESK_H = 58;
/** The wall art may grow to 1.5x the chrome scale when the room has space. */
const decorCap = (chrome: number) => chrome * 1.5;

/** Building chrome in units of the chrome scale: outer wall, sign band, corridor, room header and padding. */
export const BUILDING = { wall: 6, sign: 18, corridor: 6, pad: 6, header: 26 };

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

function roomGrid(counts: number[], innerW: number, innerH: number, chrome: number) {
  const corridor = BUILDING.corridor * chrome;
  const cap = decorCap(chrome);
  const inset = { x: 2 * BUILDING.pad * cap, y: (BUILDING.header + BUILDING.pad) * cap };
  let best = { columns: 1, scale: -1, roomW: 0, roomH: 0 };
  for (let columns = 1; columns <= counts.length; columns += 1) {
    const rows = Math.ceil(counts.length / columns);
    const roomW = (innerW - (columns - 1) * corridor) / columns;
    const roomH = (innerH - (rows - 1) * corridor) / rows;
    const fits = counts.map((count) => deskFit(count, roomW - inset.x, roomH - inset.y).scale);
    const scale = Math.min(...fits);
    if (scale > best.scale) best = { columns, scale, roomW, roomH };
  }
  return { ...best, corridor, scale: Math.max(0.5, Math.min(3, Math.floor(best.scale * 4) / 4)) };
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

function placeDesks(team: OfficeTeam, room: PlacedRoom, scale: number): PlacedDesk[] {
  const cells = placeCells(team.employees.length, room, scale);
  return team.employees.map((employee, index) => ({ ...cells[index], scale, employee, away: isAway(employee) }));
}

/** Pairs in one row play table tennis; everyone else gets a coffee. */
function placeSpots(away: OfficeEmployee[], room: PlacedRoom, scale: number): PlacedSpot[] {
  const cells = placeCells(away.length, room, scale);
  return away.map((employee, index) => {
    const pair = index - (index % 2);
    const sameRow = pair + 1 < away.length && Math.abs(cells[pair].y - cells[pair + 1].y) < 1;
    const activity: BreakActivity = sameRow ? (index % 2 ? "pingpong-right" : "pingpong-left") : "coffee";
    const x = activity === "pingpong-right" ? cells[pair].x + DESK_W * scale : cells[index].x;
    return { x, y: cells[index].y, scale, employee, activity };
  });
}

/** Fit one company building to the canvas: one room per team plus the break room, desks scaled to fit every room. */
export function layoutOffice(office: Office, width: number, height: number, chrome = 2): OfficeLayout {
  if (!office.teams.length) return { building: null, rooms: [], desks: [], spots: [], height: 0 };
  const away = office.teams.flatMap((team) => team.employees.filter(isAway));
  const specs = [...office.teams.map((team) => ({ key: team.key, label: team.label, count: team.employees.length })),
    { key: BREAK_ROOM, label: "Break Room", count: Math.max(2, away.length) }];
  const edge = BUILDING.wall * chrome;
  const bw = Math.max(width, 240) - 2 * MARGIN;
  const bh = Math.max(height, 240) - 2 * MARGIN;
  const grid = roomGrid(specs.map((spec) => spec.count), bw - 2 * edge, bh - BUILDING.sign * chrome - edge, chrome);
  const roomH = Math.max(grid.roomH, (BUILDING.header + BUILDING.pad) * decorCap(chrome) + DESK_H * grid.scale);
  const decor = Math.max(chrome, Math.min(decorCap(chrome), grid.scale));
  const rooms: PlacedRoom[] = specs.map((spec, index) => ({
    key: spec.key,
    label: spec.label,
    x: MARGIN + edge + (index % grid.columns) * (grid.roomW + grid.corridor),
    y: MARGIN + BUILDING.sign * chrome + Math.floor(index / grid.columns) * (roomH + grid.corridor),
    width: grid.roomW,
    height: roomH,
    scale: decor,
  }));
  const desks = office.teams.flatMap((team, index) => placeDesks(team, rooms[index], grid.scale));
  const spots = placeSpots(away, rooms[rooms.length - 1], grid.scale);
  const bottom = Math.max(MARGIN + bh, rooms[rooms.length - 1].y + roomH + edge);
  const building = { key: "building", label: office.name, x: MARGIN, y: MARGIN, width: bw, height: bottom - MARGIN, scale: chrome };
  return { building, rooms, desks, spots, height: bottom + MARGIN };
}
