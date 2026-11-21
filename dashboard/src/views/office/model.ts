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
  if (!state) return { teams: [] };
  return { teams: state.cards.map((card) => teamOf(card, state.session_panes)) };
}

export function layoutOffice(office: Office, width: number, scale = 2): PlacedDesk[] {
  const employees = office.teams.flatMap((team) => team.employees);
  const gap = 16;
  const cellWidth = 56 * scale;
  const cellHeight = 58 * scale;
  const columns = Math.max(1, Math.floor((Math.max(width, cellWidth + gap) - gap) / cellWidth));
  return employees.map((employee, index) => ({
    x: gap + (index % columns) * cellWidth,
    y: gap + Math.floor(index / columns) * cellHeight,
    scale,
    employee,
  }));
}
