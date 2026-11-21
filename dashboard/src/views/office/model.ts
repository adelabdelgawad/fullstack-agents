import { cardAgents, needsHuman } from "../../lib/cards";
import type { Card, DashState, Run, Session } from "../../lib/types";

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
  if (item.action_running) return "typing";
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

function teamOf(card: Card, panes: Record<string, string>): OfficeTeam {
  const leads = card.sessions.map((lead) => leadEmployee(card, lead, panes));
  const workers = card.runs.filter((run) => run.state === "running").map((run) => workerEmployee(card, run, panes));
  const helpers = cardAgents(card).map((helper) => helperEmployee(card, helper, panes));
  return { key: card.key, label: card.label || card.title || card.key, employees: [...leads, ...workers, ...helpers] };
}

export function officeOf(state: DashState | null): Office {
  if (!state) return { name: "", teams: [] };
  const name = textOf(state.repo).split("/").filter(Boolean).pop() || "Company";
  return { name, teams: state.cards.map((card) => teamOf(card, state.session_panes)) };
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
  height: number;
}

const GAP = 16;
const MAX_ROOM_COLUMNS = 4;

/** Building geometry in unscaled pixels: outer wall, sign band, corridor between room rows. */
export const BUILDING = { wall: 4, sign: 20, corridor: 20, pad: 6 };

function roomSize(team: OfficeTeam, inner: number, scale: number) {
  const cellWidth = 56 * scale;
  const pad = 8 * scale;
  const fit = Math.floor((Math.max(inner, cellWidth + 2 * pad) - 2 * pad) / cellWidth);
  const columns = Math.max(1, Math.min(MAX_ROOM_COLUMNS, fit, team.employees.length || 1));
  const rows = Math.max(1, Math.ceil(team.employees.length / columns));
  return { columns, width: columns * cellWidth + 2 * pad, height: 16 * scale + rows * 58 * scale + pad };
}

function placeDesks(team: OfficeTeam, room: PlacedRoom, columns: number): PlacedDesk[] {
  const s = room.scale;
  return team.employees.map((employee, index) => ({
    x: room.x + 8 * s + (index % columns) * 56 * s,
    y: room.y + 16 * s + Math.floor(index / columns) * 58 * s,
    scale: s,
    employee,
  }));
}

export function layoutOffice(office: Office, width: number, scale = 2): OfficeLayout {
  const rooms: PlacedRoom[] = [];
  const desks: PlacedDesk[] = [];
  if (!office.teams.length) return { building: null, rooms, desks, height: 0 };
  const edge = (BUILDING.wall + BUILDING.pad) * scale;
  const left = GAP + edge;
  const right = Math.max(width, left + 120 * scale) - GAP - edge;
  let x = left;
  let y = GAP + BUILDING.sign * scale + BUILDING.pad * scale;
  let rowHeight = 0;
  for (const team of office.teams) {
    const size = roomSize(team, right - left, scale);
    if (x > left && x + size.width > right) {
      x = left;
      y += rowHeight + BUILDING.corridor * scale;
      rowHeight = 0;
    }
    const room = { key: team.key, label: team.label, x, y, width: size.width, height: size.height, scale };
    rooms.push(room);
    desks.push(...placeDesks(team, room, size.columns));
    x += size.width + GAP;
    rowHeight = Math.max(rowHeight, size.height);
  }
  const bottom = y + rowHeight + edge;
  const building = { key: "building", label: office.name, x: GAP, y: GAP, width: right + edge - GAP, height: bottom - GAP, scale };
  return { building, rooms, desks, height: bottom + GAP };
}
