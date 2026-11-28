export interface GitTree {
  branch?: string;
  dirty?: number;
  own?: number;
  [key: string]: unknown;
}

export interface Usage {
  fill?: number;
  context?: number;
  window?: number;
  model?: string;
  compactions?: number;
  cost?: number | null;
  tokens?: number;
  blowout?: boolean;
  [key: string]: unknown;
}

export interface Doc {
  path: string;
  name: string;
  shown: string;
  size: number;
  [key: string]: unknown;
}

export interface Session {
  id: string;
  name: string;
  state: string;
  branch?: string;
  question?: string;
  said?: string;
  said_full?: string;
  said_at?: number;
  action?: string;
  action_running?: boolean;
  action_at?: number;
  ask?: string;
  need?: string;
  docs?: Doc[];
  agents?: unknown[];
  task_tracking?: Record<string, unknown>;
  engine?: string;
  updated?: number;
  previous?: string;
  [key: string]: unknown;
}

export interface Run {
  id: string;
  run_id?: string;
  mode?: string;
  unit?: string;
  state: string;
  model?: string;
  cause?: string;
  root?: string;
  artifact?: string;
  open_risks?: string[];
  [key: string]: unknown;
}

export interface Card {
  key: string;
  title?: string;
  label?: string;
  tree?: GitTree | null;
  updated: number;
  runs: Run[];
  now: Session[];
  sessions: Session[];
  usage?: Usage | null;
  needs_you: string[];
  phase: string;
  steps?: unknown[];
  rounds?: unknown[];
  repo?: string;
  worktree?: string;
  favourite?: boolean;
  fresh?: boolean;
  [key: string]: unknown;
}

export interface WaitingEntry {
  key: string;
  updated: number;
  name: string;
  snippet: string;
  card: string;
  [key: string]: unknown;
}

/** A prompt the user started with '#', with the final text reply of its turn (/api/session-history `questions`). */
export interface SessionQuestion {
  question: string;
  asked: number;
  answer: string;
  answered: number;
  done: boolean;
}

export interface HistoryEntry {
  id: string;
  name: string;
  model?: string;
  engine?: string;
  state: string;
  branch?: string;
  tokens?: number;
  cost?: number | null;
  fill?: number;
  compactions?: number;
  updated: number;
  /** Set on a subagent row: the session it worked for. */
  parent?: string;
  /** The session this one continued after a context handoff. */
  previous?: string;
  [key: string]: unknown;
}

export interface Locks {
  deploy?: boolean;
  [key: string]: unknown;
}

export interface OfficeTeamRule {
  name: string;
  match: string[];
  /** The team's staff by name; for the CTO team the CTO first, then the assistant. */
  members?: string[];
  /** Teams that name the same room share one office (two related teams, e.g. DevOps and Network). */
  room?: string;
}

export interface Goal {
  id: string;
  title: string;
  owner: string;
  status: string;
  requests: string[];
  cards: string[];
  done: number;
  total: number;
  repo?: string;
}

export interface DashState {
  cards: Card[];
  waiting: WaitingEntry[];
  still_open: WaitingEntry[];
  history: HistoryEntry[];
  session_panes: Record<string, string>;
  totals?: Record<string, unknown>;
  repo: string;
  locks: Locks;
  generated: number;
  ui?: string;
  office_teams?: OfficeTeamRule[];
  goals?: Goal[];
  [key: string]: unknown;
}

export interface HerdrPane {
  pane_id: string;
  title?: string;
  status?: string;
  [key: string]: unknown;
}

export interface HerdrTab {
  [key: string]: unknown;
}

export interface HerdrWorkspace {
  [key: string]: unknown;
}

export interface HerdrState {
  running: boolean;
  workspaces: HerdrWorkspace[];
  tabs: HerdrTab[];
  panes: HerdrPane[];
  focused_pane_id: string | null;
  focused_tab_id?: string | null;
  focused_workspace_id?: string | null;
  [key: string]: unknown;
}

/** A linked host's dashboard, as this host lists it (its token never reaches the browser). */
export interface NodeInfo {
  id: string;
  label: string;
  host: string;
  port: number;
}
