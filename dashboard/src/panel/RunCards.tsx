import { cardAgents, STATE_TEXT } from "../lib/cards";
import { ago, esc } from "../lib/format";
import { toolLine } from "../lib/markup";
import type { Card } from "../lib/types";
import {
  AGENT_NAMES,
  dismissButton,
  factList,
  factRow,
  infoSection,
  infoShown,
  isDone,
  LIVE,
  notDismissed,
  recentRuns,
  RECENT_S,
  runSession,
  shellRun,
  shortPath,
} from "./panelLib";

export const ownAgents = (c: Card): any[] => cardAgents(c).filter((a) => !(a.shell && shellRun(a, c)));
export const launcherOf = (r: any, c: Card | null): any =>
  cardAgents(c || {}).find((a) => a.shell && shellRun(a, c)?.id === r.id) || null;
const goalBox = (r: any) =>
  r.desc || r.goal ? `<div class="goal" tabindex="0" aria-label="Goal">${esc(r.desc || r.goal)}</div>` : "";

export function runFacts(r: any, c: Card | null, withGoal = true): string {
  const shell = launcherOf(r, c);
  const launched = shell
    ? [
        shell.shell.description || shell.id,
        shell.id,
        shell.state + (shell.shell.exit != null ? ` · exit ${shell.shell.exit}` : ""),
      ].join(" · ")
    : "";
  const status = [
    r.state,
    (r.flags || []).join(", "),
    r.started ? `started ${ago(r.started)} ago` : "",
    r.updated ? `updated ${ago(r.updated)} ago` : "",
  ]
    .filter(Boolean)
    .join(" · ");
  return `${withGoal ? goalBox(r) : ""}<dl class="shell-facts">${factRow("Kind", `implementer run (${r.mode || "implement"})`)}${factRow("Target", r.root)}${factRow("Brief", r.unit)}${factRow("Status", status)}${factRow("Agent", [r.engine, r.model].filter(Boolean).join(" · "))}${factRow("Launched by", launched)}${factRow("Run id", r.id)}</dl>${factList(c, `run-files-${r.id}`, "Files touched", r.touched)}${factList(c, `run-out-${r.id}`, "Outside allowed paths", r.outside)}${factList(c, `run-risks-${r.id}`, "Open risks", r.open_risks)}`;
}

export function shellFacts(a: any, c: Card | null): string {
  const x = a.shell || {};
  const status = [
    a.state,
    x.exit != null ? `exit ${x.exit}` : "",
    x.started ? `started ${ago(x.started)} ago` : "",
    `output ${ago(a.at)} ago`,
  ]
    .filter(Boolean)
    .join(" · ");
  const kind = x.command
    ? x.moved
      ? "Bash command still running (started in the foreground)"
      : "background task (run_in_background)"
    : "";
  return `<dl class="shell-facts">${factRow("Kind", kind)}${factRow("Target", x.cwd)}${factRow("Brief", x.brief)}${factRow("Status", status)}${factRow("Agent", x.run ? `${x.run} (not listed on this card)` : "none")}${factRow("Task id", a.id)}</dl>${x.command ? `<details data-info-section="cmd-${esc(a.id)}"${c && infoShown(c, `cmd-${a.id}`, false) ? " open" : ""}><summary>Command</summary><pre>${esc(x.command)}</pre></details>` : ""}`;
}

const statePill = (state: string) =>
  `<span class="pill ${["running", "stalled"].includes(state) ? "live" : /fail|error|kill|stalled/.test(state) ? "bad" : "done"}">${esc(state)}</span>`;
const countBadges = (pairs: any[][]) =>
  pairs
    .filter(([, n]) => n)
    .map(
      ([one, n, tone, many]) =>
        `<span class="pill ${tone || ""}">${n} ${esc(n === 1 ? one : many || `${one}s`)}</span>`,
    )
    .join("");

function liveCard(x: any): string {
  return `<div class="live-shell${x.running ? " running" : ""}"><div class="ls-head"><b class="ls-title" title="${esc(x.title)}">${esc(x.title)}</b>${statePill(x.state)}${x.time ? `<span class="ls-time">${esc(x.time)}</span>` : ""}</div><div class="ls-sub">${x.sub}</div>${x.badges ? `<div class="ls-badges">${x.badges}</div>` : ""}${x.details}<div class="ls-actions">${x.actions}${dismissButton(x.dismissItem)}</div></div>`;
}

const runCard =
  (c: Card) =>
  (r: any): string => {
    const sid = esc(runSession(r, c)),
      shell = launcherOf(r, c);
    const sub = [
      r.unit ? `<b>${esc(r.unit)}</b>` : "",
      esc([r.engine, r.model].filter(Boolean).join(" · ")),
      r.root ? `<span title="${esc(r.root)}">${esc(shortPath(r.root))}</span>` : "",
      shell ? `via ${esc(shell.id)}` : "",
    ]
      .filter(Boolean)
      .join(" · ");
    const details = `<details data-info-section="run-more-${esc(r.id)}"${infoShown(c, `run-more-${r.id}`, false) ? " open" : ""}><summary>Details</summary>${runFacts(r, c, false)}</details>`;
    const actions = `<button class="action-button" data-asid="${sid}" data-agent="${esc(r.id)}" aria-haspopup="dialog">Console</button>${r.root ? `<button class="action-button" data-asid="${sid}" data-run-changes="${esc(r.id)}" aria-haspopup="dialog">Git changes</button>` : ""}<button class="action-button" data-open-run="${esc(r.id)}">Panel</button>`;
    return liveCard({
      running: LIVE(r),
      title: r.desc || r.goal || r.unit || r.id,
      state: r.state,
      time: r.started ? ago(r.started) : "",
      sub,
      badges: countBadges([
        ["file", (r.touched || []).length],
        ["outside brief", (r.outside || []).length, "bad", "outside brief"],
        ["risk", (r.open_risks || []).length, "warn"],
      ]),
      details,
      actions,
      dismissItem: r,
    });
  };

const agentCard = (a: any): string => {
  const [kind, ...rest] = a.label.split(" · "),
    name = AGENT_NAMES[kind] || kind,
    who = rest.join(" · ") || name;
  return liveCard({
    running: a.state === "running",
    title: a.task || who,
    state: a.state,
    time: ago(a.at),
    sub: [
      a.task ? `<b>${esc(who)}</b>` : "",
      esc(name),
      esc(a.state === "running" ? "working" : `finished ${ago(a.at)} ago`),
    ]
      .filter(Boolean)
      .join(" · "),
    badges: "",
    details: "",
    actions: `<button class="action-button" data-asid="${esc(a.sid)}" data-agent="${esc(a.id)}" aria-haspopup="dialog">Console</button>`,
    dismissItem: a,
  });
};

const shellCard =
  (c: Card) =>
  (a: any): string => {
    const x = a.shell || {},
      [, ...rest] = a.label.split(" · ");
    const sub = [
      x.command ? (x.moved ? "foreground command" : "background task") : "shell",
      x.cwd ? `<span title="${esc(x.cwd)}">${esc(shortPath(x.cwd))}</span>` : "",
      x.exit != null ? `exit ${esc(x.exit)}` : "",
    ]
      .filter(Boolean)
      .join(" · ");
    const details = `<details data-info-section="shell-more-${esc(a.id)}"${infoShown(c, `shell-more-${a.id}`, false) ? " open" : ""}><summary>Details</summary>${shellFacts(a, c)}</details>`;
    return liveCard({
      running: a.state === "running",
      title: x.description || rest.join(" · ") || a.id,
      state: a.state,
      time: x.started ? ago(x.started) : "",
      sub,
      badges: "",
      details,
      actions: `<button class="action-button" data-asid="${esc(a.sid)}" data-agent="${esc(a.id)}" aria-haspopup="dialog">Console</button>`,
      dismissItem: a,
    });
  };

const flowRuns = (c: any): any[] =>
  (c.workflow_runs || [])
    .map((r: any) => ({ ...r, id: r.run_id }))
    .filter((r: any) => r.state === "running" || Date.now() / 1000 - (r.updated || 0) < RECENT_S);
const liveAgents = (c: any): any[] => {
  const flows = new Set((c.workflow_runs || []).map((r: any) => r.run_id));
  return ownAgents(c).filter((a) => !flows.has(a.id));
};

const flowCard =
  (c: Card) =>
  (r: any): string => {
    const verdict = r.verdict
      ? `<span class="pill ${/^(PASS|GREEN)$/.test(r.verdict) ? "live" : "warn"}">${esc(r.verdict)}</span>`
      : "";
    const sub = [
      esc([r.engine, r.model].filter(Boolean).join(" · ")),
      r.root ? `<span title="${esc(r.root)}">${esc(shortPath(r.root))}</span>` : "",
    ]
      .filter(Boolean)
      .join(" · ");
    const facts = `<dl class="shell-facts">${factRow("Role", r.role)}${factRow("Target", r.root)}${factRow("Verdict", r.verdict)}${factRow("Started", r.started ? new Date(r.started * 1000).toLocaleString() : "")}${factRow("Report", r.artifact)}${factRow("Run id", r.run_id)}</dl>${factList(c, `flow-sum-${r.run_id}`, "Summary", r.summary ? [r.summary] : [])}${factList(c, `flow-brief-${r.run_id}`, "Brief", r.brief ? [r.brief] : [])}`;
    const details = `<details data-info-section="flow-more-${esc(r.run_id)}"${infoShown(c, `flow-more-${r.run_id}`, false) ? " open" : ""}><summary>Details</summary>${facts}</details>`;
    return liveCard({
      running: r.state === "running",
      title: r.summary || `${r.role || "run"} run`,
      state: r.state,
      time: r.started ? ago(r.started) : "",
      sub: `<b>${esc(r.role || "run")}</b> · ${sub}`,
      badges: verdict,
      details,
      actions: `<button class="action-button" data-open-flow="${esc(r.run_id)}">Panel</button>`,
      dismissItem: r,
    });
  };

export function liveSets(c: Card): any {
  return {
    agents: liveAgents(c).filter(notDismissed),
    flows: flowRuns(c).filter(notDismissed),
    runs: recentRuns(c)
      .filter(notDismissed)
      .sort((a, b) => Number(LIVE(b)) - Number(LIVE(a)) || (b.updated || 0) - (a.updated || 0)),
  };
}
export const liveTotal = ({ agents, runs, flows }: any): number =>
  agents.filter((a: any) => a.state === "running").length +
  runs.filter(LIVE).length +
  flows.filter((r: any) => r.state === "running").length;
export const allLiveItems = (c: Card): any[] => [...recentRuns(c), ...flowRuns(c), ...liveAgents(c)];

function liveGroup(title: string, items: any[], tile: (x: any) => string, cls: string): string {
  if (!items.length) return "";
  const running = items.filter((x) => x.state === "running").length;
  const count = ` <span class="chip">${running} running${items.length > running ? ` · ${items.length - running} recent` : ""}</span>`;
  return `<div class="live-group"><h5>${esc(title)}${count}</h5><div class="${cls}" tabindex="0" role="region" aria-label="${esc(title)}; scroll sideways for more">${items.map(tile).join("")}</div></div>`;
}

export function liveHtml(c: Card): string {
  const sets = liveSets(c),
    { agents, flows, runs } = sets,
    shell = (a: any) => a.label.startsWith("shell");
  const lead = (s: any) =>
    `<div class="live-lead"><span class="pill ${s.state === "working" ? "live" : ""}">${esc(STATE_TEXT[s.state] || s.state)}</span> <b>${esc(s.name)}</b>${s.action ? `<div class="s lead-act" title="${esc(toolLine(s))}">${esc(toolLine(s).replace(/\\n|\s+/g, " "))}</div>` : ""}${s.question ? `<div class="ask-q">Question for you (it keeps working meanwhile): ${esc(s.question)}</div>` : ""}</div>`;
  const groups = [
    liveGroup(
      "Implementer runs",
      runs.map((r: any) => ({ ...r, state: LIVE(r) ? "running" : r.state })),
      runCard(c),
      "live-shells runs",
    ),
    liveGroup("Workflow runs", flows, flowCard(c), "live-shells flows"),
    liveGroup(
      "Subagents",
      agents.filter((a: any) => !shell(a)),
      agentCard,
      "live-shells agents",
    ),
    liveGroup("Background shells", agents.filter(shell), shellCard(c), "live-shells shells"),
  ].join("");
  const done = [...runs, ...flows, ...agents].filter(isDone).length;
  return infoSection(
    c,
    "live",
    "Running now",
    `<div class="live-top"><div>${c.now.map(lead).join("")}</div>${done ? `<button class="action-button" data-dismiss-all="1">Dismiss all done (${done})</button>` : ""}</div>\n    ${groups || '<div class="s">Nothing running or recently finished.</div>'}`,
    `<span class="chip">${liveTotal(sets)} running</span>`,
    true,
  );
}
