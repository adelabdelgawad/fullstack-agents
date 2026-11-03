import type { Card, DashState, Session } from "./types";

export interface Stage {
  key: string;
  label: string;
  who: string;
  phases: string[];
  flow?: boolean;
}

export const STAGES: Stage[] = [
  { key: "investigate", label: "Investigate", who: "lead", phases: ["idle", "investigate"], flow: true },
  { key: "plan", label: "Plan", who: "lead", phases: ["plan"], flow: true },
  { key: "build", label: "Build", who: "implementer", phases: ["implement", "rework"], flow: true },
  {
    key: "review",
    label: "Review",
    who: "lead audit · test-runner · diff-reviewer",
    phases: ["audit", "validate"],
    flow: true,
  },
  { key: "complete", label: "Done", who: "lead", phases: ["complete"] },
  { key: "human", label: "Needs human", who: "you · approve · rework", phases: ["review"] },
];

export const QUIET = new Set(["idle", "complete"]);

export const FLAG_TEXT: Record<string, string> = {
  failed: "run failed",
  stalled: "run stalled",
  out_of_scope: "edited files outside its brief",
  no_changes: "changed nothing",
  retries_exhausted: "retries used up",
};

export const favKeys = (c: Card): string[] => [c.key, ...c.sessions.map((s) => `session:${s.id}`)];

export const gitBadge = (c: Card): number =>
  !c.tree ? 0 : typeof c.tree.own === "number" ? (c.tree.own as number) : (c.tree.dirty as number) || 0;

export const rank = (c: Card): number =>
  c.fresh
    ? -1
    : c.sessions.some((s) => s.state === "working") || c.runs.some((r) => r.state === "running")
      ? 0
      : needsHuman(c)
        ? 1
        : QUIET.has(c.phase)
          ? 3
          : 2;

export const needsHuman = (c: Card): boolean =>
  c.phase !== "complete" &&
  (c.phase === "review" || c.needs_you.length > 0 || c.sessions.some((s) => s.state === "waiting"));

export const stageOf = (c: Card): string =>
  needsHuman(c) ? "human" : (STAGES.find((s) => s.phases.includes(c.phase)) || STAGES[0]).key;

export const STAGE_LABEL = (c: Card): string =>
  (STAGES.find((s) => s.key === stageOf(c)) || ({} as Stage)).label || c.phase;

export const soleSid = (c: Card): string => (c.tree && c.sessions.length === 1 ? c.sessions[0].id : "");

export const worktreesOf = (c: Card, state: DashState | null): Card[] => {
  const sid = soleSid(c);
  return sid
    ? ((state && state.cards) || [])
        .filter((x) => soleSid(x) === sid)
        .sort((a, b) => rank(a) - rank(b) || b.updated - a.updated)
    : [];
};

export const cardOfSession = (sid: string, state: DashState | null): Card | null =>
  ((state && state.cards) || []).find((c) => (c.now || []).some((s) => s.id === sid)) || null;

export const sessionOf = (sid: string, state: DashState | null): Session | null => {
  for (const c of (state && state.cards) || []) for (const s of c.now || []) if (s.id === sid) return s;
  return null;
};

export const isStale = (c: Card): boolean => (c.sessions || []).some((s) => s.state === "quiet");

export const isRunning = (c: Card): boolean =>
  c.sessions.some((s) => s.state === "working") || c.runs.some((r) => r.state === "running");

export interface FleetState {
  filter: string;
  text: string;
  sort: string;
}

export function fleetMatches(c: Card, fleet: FleetState): boolean {
  const f = fleet.filter;
  const u = c.usage;
  if (f === "running" && !isRunning(c)) return false;
  if (f === "waiting" && !needsHuman(c)) return false;
  if (f === "stale" && !isStale(c)) return false;
  if (f === "blowouts" && !(u && u.blowout)) return false;
  if (!fleet.text) return true;
  const hay = [
    c.title,
    c.label,
    c.tree && c.tree.branch,
    u && u.model,
    ...c.sessions.map((s) => s.name + " " + (s.branch || "")),
  ]
    .join(" ")
    .toLowerCase();
  return hay.includes(fleet.text.toLowerCase());
}

export function fleetCompare(a: Card, b: Card, fleet: FleetState): number {
  const ux = a.usage || {};
  const uy = b.usage || {};
  if (fleet.sort === "updated") return b.updated - a.updated;
  if (fleet.sort === "cost") return ((uy.cost as number) || 0) - ((ux.cost as number) || 0) || b.updated - a.updated;
  if (fleet.sort === "context") return ((uy.fill as number) || 0) - ((ux.fill as number) || 0) || b.updated - a.updated;
  return rank(a) - rank(b) || b.updated - a.updated;
}

export const STATE_TEXT: Record<string, string> = {
  working: "working",
  waiting: "waiting on you",
  idle: "just finished a turn",
  still_open: "stopped",
  quiet: "stale · no output for 5+ min",
};

export interface Step {
  text?: string;
  state: string;
  [key: string]: unknown;
}

export interface CardAgent {
  id: string;
  sid: string;
  state: string;
  at: number;
  shell?: unknown;
  [key: string]: unknown;
}

const stepsOf = (c: Card): Step[] => (c.steps || []) as Step[];

export const stepsDone = (c: Card): number =>
  stepsOf(c).filter((x) => x.state === "done" || x.state === "skipped").length;

export const activeStep = (c: Card): Step | undefined => stepsOf(c).find((x) => x.state === "active");

export function cardAgents(c: Partial<Card>): CardAgent[] {
  return (c.now || [])
    .flatMap((s) => ((s.agents || []) as CardAgent[]).map((a) => ({ ...a, sid: s.id })))
    .sort((a, b) => Number(b.state === "running") - Number(a.state === "running") || b.at - a.at);
}
