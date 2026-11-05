import { retroCardHtml } from "../components/retroMarkup";
import { RetroCard } from "../components/RetroControls";
import { useEffect, useRef, useState } from "react";
import { cardAgents, FLAG_TEXT, STATE_TEXT } from "../lib/cards";
import { ago, esc, fmtCost, fmtTokens, modelFamily, modelShort } from "../lib/format";
import { lastPara, saidHtml } from "../lib/markup";
import type { Card, DashState } from "../lib/types";
import { store } from "../store";
import { openAgent } from "../components/OutDialog";
import { COPY_ICON, copyDoc, resumeHtml } from "./docs";
import { allLiveItems, liveHtml, liveSets, liveTotal } from "./RunCards";
import { taskListHtml, taskProgressHtml } from "./TaskList";
import {
  dismiss,
  duration,
  infoDisclosure,
  infoOpen,
  infoSection,
  isDone,
  keepScroll,
  LIVE,
  stateChip,
  STEP_MARK,
} from "./panelLib";

let showLog = false,
  logSeen = "",
  wasLive = false,
  preparedRun: string | null = null,
  logTimer: ReturnType<typeof setInterval> | null = null;
let repaint: (() => void) | null = null;
const stopLog = () => {
  if (logTimer) clearInterval(logTimer);
  logTimer = null;
};
export const resetRunEffects = () => {
  showLog = false;
  logSeen = "";
  wasLive = false;
  preparedRun = null;
  stopLog();
};
export const prepareRunLog = (id: string, cardKey: string) => {
  openRunsSection(cardKey);
  showLog = true;
  logSeen = "";
  wasLive = false;
  preparedRun = id;
  stopLog();
};
export const consumePreparedRun = (id: string | null): boolean => {
  if (!preparedRun) return false;
  if (id === null) return true;
  if (id !== preparedRun) return false;
  preparedRun = null;
  return true;
};

function openRunsSection(cardKey: string): void {
  infoOpen.set(cardKey, (infoOpen.get(cardKey) || new Map()).set("runs", true));
  document.querySelector('#info [data-info-section="runs"]')?.setAttribute("open", "");
}

async function pollLog(id: string): Promise<void> {
  if (document.hidden) return;
  try {
    const text = await (await fetch(`/api/log?id=${encodeURIComponent(id)}`, { cache: "no-store" })).text();
    if (store.get().openRun !== id || !showLog || text === logSeen) return;
    logSeen = text || "(log is empty)";
    repaint?.();
  } catch {}
}
export const repollLog = () => {
  const id = store.get().openRun;
  if (id) void pollLog(id);
};

function detailHtml(r: any): string {
  const live = LIVE(r),
    tone = live ? "live" : (r.flags || []).length || r.state !== "done" ? "bad" : "ok";
  const flags = (r.flags || []).map((f: string) => `<span class="chip bad">${esc(FLAG_TEXT[f] || f)}</span>`).join(" ");
  return (
    `<div class="detail"><div><b>End of task</b> ${stateChip(r)} ${flags}</div>` +
    `${live ? '<div class="s">Still running — the result lands here when it finishes.</div>' : ""}` +
    `${!live && r.summary ? `<pre>${esc(r.summary)}</pre>` : ""}` +
    `${!live && !r.summary ? '<div class="s">No result text was recorded.</div>' : ""}` +
    `${(r.open_risks || []).length ? `<div class="s"><b>Open risks:</b> ${esc(r.open_risks.join(" · "))}</div>` : ""}` +
    `<div class="row" style="margin:6px 0 0"><button class="action-button" data-log="1" style="margin-left:0">` +
    `${showLog ? "Hide log" : "Show log"}</button></div>` +
    `${showLog ? `<pre class="log" id="log">${esc(logSeen || "loading…")}</pre>` : ""}` +
    `<div class="endbar ${tone}"><button class="action-button" data-collapse="1" ` +
    `title="Collapse this task">Hide ▴</button></div></div>`
  );
}

function stepsHtml(c: any): string {
  if (!c.steps.length)
    return c.sessions.length
      ? '<div class="s">The lead has not listed its steps for this task yet; “Session” above shows what it is doing.</div>'
      : "";
  return (
    `<ul class="steps">` +
    c.steps
      .map(
        (step: any) =>
          `<li class="${esc(step.state)}"><span class="mk" aria-label="${esc(step.state)}">` +
          `${STEP_MARK[step.state] || "○"}</span><span class="tx">${esc(step.text)}</span>` +
          `${step.note ? `<span class="nt">${esc(step.note)}</span>` : ""}</li>`,
      )
      .join("") +
    `</ul>`
  );
}

function workersSection(c: Card): string {
  const runs = c.runs.map((r: any) => ({
    name: `${r.mode} ${r.unit || r.id}`,
    kind: "implementer run",
    u: { model: r.model || r.engine },
    state: r.state,
    at: r.started,
    cause: r.cause,
  }));
  const rows: any[] = c.sessions
    .flatMap((s: any) => [
      { name: s.name, kind: "orchestrator", u: s.usage || { model: s.model }, state: s.state, lead: true },
      ...Object.entries(s.usage?.agents || {}).map(([id, usage]: any) => {
        const live: any = cardAgents(c).find((x) => x.id === id) || {};
        return {
          name: live.label || usage.label || id,
          kind: "subagent",
          u: usage,
          state: live.state || "completed",
          at: live.at,
        };
      }),
    ])
    .concat(runs);
  if (!rows.length) return "";
  const num = (v: any, fn: (n: number) => string) => (v == null ? "—" : fn(v));
  const tr = (r: any) =>
    `<tr class="${["failed", "abandoned"].includes(r.state) ? "bad" : ""}"><td>` +
    `${r.lead ? `<b>${esc(r.name)}</b>` : esc(r.name)}<div class="s">${esc(r.kind)}` +
    `${r.cause ? ` · ${esc(r.cause)}` : ""}</div></td><td><span class="mchip m-${modelFamily(r.u.model)}">` +
    `${esc(modelShort(r.u.model) || "?")}</span></td><td>${esc(STATE_TEXT[r.state] || r.state || "")}</td>` +
    `<td class="num">${r.u.fill !== undefined ? `${Math.round(r.u.fill * 100)}%` : "—"}` +
    `${r.u.fill !== undefined ? `<span class="orc-bar"><span style="width:${Math.round(r.u.fill * 100)}%"></span></span>` : ""}</td>` +
    `<td class="num">${num(r.u.tokens, fmtTokens)}</td><td class="num">${fmtCost(r.u.cost)}</td>` +
    `<td class="num">${r.at ? ago(r.at) : ""}</td></tr>`;
  return infoSection(
    c,
    "workers",
    `Orchestrator and workers (${rows.length})`,
    `<table class="usage-table"><thead><tr><th>Agent</th><th>Model</th><th>State</th><th>Context</th>` +
      `<th>Tokens</th><th>Est. cost</th><th>Age</th></tr></thead><tbody>${rows.map(tr).join("")}</tbody></table>` +
      `<div class="s">Cost is an estimate from token counts and a price table, not a bill.</div>`,
    "",
    true,
  );
}

function activitySection(c: Card, state: DashState): string {
  const items: any[] = ((state.activity as any[]) || []).filter((e) => e.key === c.key).slice(0, 20);
  const time = (at: number) =>
    new Date(at * 1000).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    });
  const body = items.length
    ? `<ol class="detail-feed">${items
        .map((event) => `<li class="${esc(event.tone)}"><time>${time(event.at)}</time> ${esc(event.text)}</li>`)
        .join("")}</ol>`
    : '<div class="s">No activity recorded since the dashboard started.</div>';
  return infoSection(c, "activity", "Recent activity", body, "", true);
}

const engineName = (engine: string): string =>
  engine === "codex" ? "Codex" : engine === "claude" ? "Claude" : engine || "Agent";
const stamp = (time: number): string => (time ? new Date(time * 1000).toLocaleString() : "Time not recorded");
const timeline = (events: any[]): string =>
  `<ol class="info-timeline">` +
  events
    .map(
      (event) =>
        `<li><b>${esc(event.phase)}</b> <time>${esc(stamp(event.timestamp))}</time>` +
        `${event.note ? `<div class="s">${esc(event.note)}</div>` : ""}</li>`,
    )
    .join("") +
  `</ol>`;

function runTasks(c: Card, openRun: string | null): string {
  return c.runs
    .map((run: any) => {
      const open = openRun === run.id;
      return (
        `<li class="task${open ? " open" : ""}" data-run="${esc(run.id)}">` +
        `<input type="checkbox" disabled ${run.state === "done" ? "checked" : ""} aria-label="${esc(run.state)}">` +
        `<div class="th"><span class="tn">${esc(run.unit || run.id)}</span> ${stateChip(run)} <span class="s">` +
        `${LIVE(run) ? `<span class="live-dot"></span>running ${duration(run)}` : `took ${duration(run)} · ${ago(run.updated)} ago`}` +
        `</span><span class="caret">${open ? "▾" : "▸"}</span></div>` +
        `${run.goal ? `<div class="snip tg">${esc(run.goal)}</div>` : ""}${open ? detailHtml(run) : ""}</li>`
      );
    })
    .join("");
}

function registeredRuns(c: Card, runs: any[]): string {
  return runs
    .map(
      (run) =>
        `<article class="info-run"><b>${esc(run.role)}</b> · ${esc(engineName(run.engine))} · ` +
        `${esc(run.model || "model not recorded")} <span class="chip">${esc(run.state)}</span>` +
        `${run.verdict ? ` · ${esc(run.verdict)}` : ""}<div class="s">${esc(stamp(run.updated))}</div>` +
        `${run.summary ? `<div class="snip">${esc(run.summary.slice(0, 320))}</div>` : ""}` +
        `${run.summary ? infoDisclosure(c, `run-${run.run_id}`, "Full run summary", `<pre>${esc(run.summary)}</pre>`) : ""}` +
        `${run.brief ? infoDisclosure(c, `brief-${run.run_id}`, "Brief", `<pre>${esc(run.brief)}</pre>`) : ""}` +
        `<div class="s">Run ${esc(run.run_id)}</div></article>`,
    )
    .join("");
}

function runChecks(c: Card, runs: any[]): string {
  return (
    ((c as any).chips || [])
      .filter((chip: any) => chip.kind === "tests")
      .map(
        (chip: any) =>
          `<div class="snip"><b>Worker-reported checks</b> ${esc(chip.verdict)}` +
          `${chip.label ? ` · ${esc(chip.label)}` : ""}</div>`,
      )
      .join("") +
    [...runs, ...c.runs]
      .filter((run: any) => run.tests?.length)
      .map(
        (run: any) =>
          `<div class="snip"><b>Worker-reported checks</b><pre>${esc(JSON.stringify(run.tests, null, 2))}</pre></div>`,
      )
      .join("")
  );
}

function overviewHtml(
  c: Card,
  status: string,
  need: number,
  phase: string,
  done: number,
  all: number,
  activity: any,
): string {
  const tile = (label: string, value: any, cls = "", extra = "") =>
      retroCardHtml(
        `<div class="so-l">${esc(label)}</div><div class="so-v">${esc(value)}</div>${extra}`,
        `so-tile ${cls}`,
      ),
    usage: any = c.usage,
    context = usage ? `${Math.round(usage.fill * 100)}%${usage.compactions ? ` · ${usage.compactions}×` : ""}` : "—";
  const tones: Record<string, string> = { working: "live", blocked: "bad", done: "done" };
  return retroCardHtml(
    `<section class="session-overview" aria-label="Session overview"><div class="so-head">` +
      `<span class="so-ico" aria-hidden="true"></span><b>Session health</b>` +
      `<span class="pill ${tones[status] || ""}">${esc(status)}</span><span class="so-right">` +
      `${need ? `<span class="pill bad">${need} need${need === 1 ? "s" : ""} you</span>` : ""}` +
      `<span class="pill">${esc(phase)}</span></span></div><div class="so-tiles">${tile("Phase", phase)}` +
      `${tile(
        "Tasks done",
        all ? `${done}/${all}` : "—",
        "",
        all
          ? `<div class="so-bar" aria-hidden="true"><span style="width:${Math.round((done / all) * 100)}%"></span></div>`
          : "",
      )}` +
      `${tile("Running now", liveTotal(liveSets(c)), "live")}${tile("Needs you", need, need ? "bad" : "")}` +
      `${tile(
        "Context",
        context,
        usage?.blowout ? "bad" : "",
        usage
          ? `<div class="so-bar" aria-hidden="true"><span style="width:${Math.round(usage.fill * 100)}%"></span></div>`
          : "",
      )}` +
      `${tile("Est. cost", fmtCost(usage?.cost))}${tile("Tokens / min", fmtTokens(usage?.tpm))}` +
      `${tile("Latest activity", stamp(activity.updated || c.updated), "time")}</div></section>`,
    "overview-frame",
  );
}

function summarySection(c: Card, status: string, phase: string, lead: any, auditor: string, activity: any): string {
  const body =
    `<b>${esc(c.title)}</b><dl class="info-facts"><dt>State</dt><dd>${esc(status)}</dd>` +
    `<dt>Phase</dt><dd>${esc(phase)}</dd><dt>Lead</dt><dd>${esc(engineName(lead.engine))}` +
    `${lead.model ? ` · ${esc(lead.model)}` : ""}</dd><dt>Auditor</dt><dd>${esc(auditor)}</dd>` +
    `<dt>Latest activity</dt><dd>${esc(stamp(activity.updated || c.updated))}</dd></dl>`;
  return infoSection(c, "summary", "Summary", body);
}

function progressSection(c: Card, history: any[], activity: any): string {
  const body =
    `${history.length ? timeline(history.slice(-8)) : '<div class="s">No phase history recorded.</div>'}` +
    `${history.length > 8 ? infoDisclosure(c, "history", "Earlier phase history", timeline(history.slice(0, -8))) : ""}` +
    `${activity.action ? `<div class="snip"><b>${activity.action_running ? "Running now" : "Latest action"}</b> ` : ""}` +
    `${activity.action ? `${esc(activity.action)}</div>` : ""}` +
    `${c.steps?.length ? stepsHtml(c) : ""}` +
    `${(c as any).declared?.note ? `<div class="snip">${esc((c as any).declared.note)}</div>` : ""}`;
  return infoSection(c, "progress", "Progress", body);
}

function resultSection(
  c: Card,
  lead: any,
  message: any,
  audit: any,
  leadChecks: string,
  checks: string,
  blockers: string[],
): string {
  const update = lead.workflow_summary
    ? `<div class="snip"><b>Lead-reported summary</b><pre>${esc(lead.workflow_summary)}</pre></div>`
    : message
      ? `<div class="snip">${esc(lastPara(message.said || message.said_full).slice(0, 400))}</div>` +
        infoDisclosure(
          c,
          "message",
          `Full message from ${engineName(message.engine)}`,
          `<button class="copy-ico" data-said="${esc(message.id)}" aria-label="Copy the last message">` +
            `${COPY_ICON}</button>${saidHtml(message)}`,
        )
      : '<div class="s">No agent update recorded.</div>';
  const auditText = audit
    ? esc(audit.state) + (audit.verdict ? ` · ${esc(audit.verdict)}` : " · no verdict recorded")
    : "No registered audit result.";
  const risks = blockers.length
    ? `<div class="snip"><b>Blockers / needs you</b><ul>` +
      `${[...new Set(blockers)].map((item) => `<li>${esc(item)}</li>`).join("")}</ul></div>`
    : "";
  return infoSection(
    c,
    "result",
    "Result",
    `${update}<div class="snip"><b>Audit</b> ${auditText}</div>${leadChecks}${checks}${risks}`,
  );
}

function sessionDetails(c: Card, state: DashState, now: any[], sessions: any[], runs: any[]): string {
  const body =
    (now.length ? now : sessions).map((session) => resumeHtml(session, state)).join("") +
    runs
      .map((run) => `<div class="mono">${esc(run.run_id)} · ${esc(run.root || "")} · ${esc(run.artifact || "")}</div>`)
      .join("") +
    `<div class="mono">${esc(c.worktree || c.repo || "")}</div>` +
    now
      .map((session) => `<div class="s">Pane: ${esc(state.session_panes[session.id] || "not recorded")}</div>`)
      .join("");
  return infoDisclosure(c, "session", "Session details", body);
}

function runsDetails(c: Card, desc: string, registered: string, tasks: string, runs: any[]): string {
  const body =
    (desc ? infoDisclosure(c, "task-brief", "Task brief", `<pre>${esc(desc)}</pre>`) : "") +
    registered +
    (tasks ? `<ul class="tasks">${tasks}</ul>` : "") +
    (!runs.length && !tasks ? '<div class="s">No run records available.</div>' : "");
  return infoDisclosure(c, "runs", "Worker and audit runs", body);
}

export function infoHtml(c: Card, state: DashState, openRun: string | null): string {
  const tasks = runTasks(c, openRun);
  const sessions: any[] = c.sessions || [],
    now: any[] = c.now || [],
    lead: any = sessions.find((s) => s.name === c.title) || sessions[0] || now[0] || {};
  const runs: any[] = [...((c as any).workflow_runs || [])].sort((a, b) => a.updated - b.updated),
    audit = runs.filter((r) => r.role === "auditor").slice(-1)[0];
  const activity = [...now].sort((a, b) => b.updated - a.updated)[0] || lead,
    message = [...now]
      .filter((s) => s.said_full || s.said)
      .sort((a, b) => (b.said_at || b.updated) - (a.said_at || a.updated))[0];
  const status = sessions.some((s) => ["waiting", "blocked"].includes(s.state))
    ? "blocked"
    : sessions.some((s) => s.state === "working")
      ? "working"
      : c.phase === "complete"
        ? "done"
        : STATE_TEXT[activity.state] || activity.state || "unknown";
  const history = sessions.flatMap((s) => s.workflow_history || []).sort((a: any, b: any) => a.timestamp - b.timestamp);
  const auditor = audit
    ? [engineName(audit.engine), audit.model || "model not recorded"].join(" · ")
    : lead.workflow_auditor
      ? `Claude · ${lead.workflow_auditor} (selected; no audit recorded)`
      : "No audit recorded";
  const leadChecks = lead.workflow_checks?.length
      ? `<div class="snip"><b>Lead-reported checks</b><pre>${esc(lead.workflow_checks.join("\n"))}</pre></div>`
      : "",
    desc = (c as any).desc || (c as any).goal;
  const registered = registeredRuns(c, runs),
    checks = runChecks(c, runs);
  const blockers = [
      ...c.needs_you.map((f) => FLAG_TEXT[f] || f),
      ...now.filter((s) => s.need).map((s) => s.need),
      ...c.runs.flatMap((r) => r.open_risks || []),
    ],
    need = new Set(blockers).size,
    phase = lead.workflow_phase || c.phase || "unknown";
  const tracked: any[] = sessions.map((s) => s.task_tracking).filter((t) => t && !t.error && t.total),
    done = tracked.reduce((n, t) => n + t.completed, 0),
    all = tracked.reduce((n, t) => n + t.total, 0);
  return (
    `<div class="info-grid">${overviewHtml(c, status, need, phase, done, all, activity)}` +
    `${taskProgressHtml(c)}${workersSection(c)}${activitySection(c, state)}` +
    `<div class="session-activity">${liveHtml(c)}</div>` +
    `${summarySection(c, status, phase, lead, auditor, activity)}${progressSection(c, history, activity)}` +
    `${resultSection(c, lead, message, audit, leadChecks, checks, blockers)}` +
    `${sessionDetails(c, state, now, sessions, runs)}${runsDetails(c, desc, registered, tasks, runs)}` +
    `${taskListHtml(c)}</div>`
  );
}

function fitTaskLists(root: HTMLElement): void {
  root.querySelectorAll<HTMLElement>(".tracked-tasks").forEach((list) => {
    const height = [...list.children].slice(0, 10).reduce((n, row) => n + row.getBoundingClientRect().height, 0);
    if (height > 0) list.style.maxHeight = `${Math.ceil(height)}px`;
  });
}

function paintInfo(root: HTMLDivElement | null, card: Card, state: DashState, openRun: string | null): void {
  if (!root) return;
  if (root.dataset.card === card.key)
    infoOpen.set(
      card.key,
      new Map(
        [...root.querySelectorAll<HTMLDetailsElement>("[data-info-section]")].map((detail) => [
          detail.dataset.infoSection || "",
          detail.open,
        ]),
      ),
    );
  keepScroll(root, () => {
    root.innerHTML = infoHtml(card, state, openRun);
  });
  root.dataset.card = card.key;
  fitTaskLists(root);
}

function syncLog(card: Card, openRun: string | null): (() => void) | undefined {
  const run: any = openRun && card.runs.find((item) => item.id === openRun);
  if (!run || !showLog) {
    stopLog();
    return;
  }
  if (LIVE(run)) {
    wasLive = true;
    if (!logTimer) {
      void pollLog(run.id);
      logTimer = setInterval(() => void pollLog(run.id), 2500);
    }
  } else {
    stopLog();
    if (wasLive || !logSeen) {
      wasLive = false;
      void pollLog(run.id);
    }
  }
  return stopLog;
}

function listenForToggles(root: HTMLDivElement | null, cardKey: string): (() => void) | undefined {
  if (!root) return;
  const toggle = (event: Event) => {
    const detail = event.target as HTMLDetailsElement;
    if (!detail.dataset.infoSection) return;
    const keys = infoOpen.get(cardKey) || new Map();
    keys.set(detail.dataset.infoSection, detail.open);
    infoOpen.set(cardKey, keys);
    fitTaskLists(root);
  };
  root.addEventListener("toggle", toggle, true);
  return () => root.removeEventListener("toggle", toggle, true);
}

function clickInfo(event: React.MouseEvent, card: Card, state: DashState, root: HTMLDivElement | null): void {
  const target = event.target as HTMLElement,
    button = target.closest<HTMLElement>("button"),
    task = target.closest<HTMLElement>(".task");
  if (task && !target.closest(".detail")) {
    resetRunEffects();
    store.set({ openRun: store.get().openRun === task.dataset.run ? null : task.dataset.run || null });
    return;
  }
  if (!button) return;
  if (button.dataset.log) {
    showLog = !showLog;
    logSeen = "";
    stopLog();
    repaint?.();
  } else if (button.dataset.collapse) {
    resetRunEffects();
    store.set({ openRun: null });
  } else if (button.dataset.agent) openAgent(button.dataset.asid || "", button.dataset.agent);
  else if (button.dataset.runChanges) openAgent(button.dataset.asid || "", button.dataset.runChanges, "changes");
  else if (button.dataset.dismiss) {
    dismiss([button.dataset.dismiss]);
    repaint?.();
  } else if (button.dataset.dismissAll) {
    dismiss(
      allLiveItems(card)
        .filter(isDone)
        .map((item) => item.id),
    );
    repaint?.();
  } else if (button.dataset.openRun) {
    prepareRunLog(button.dataset.openRun, card.key);
    store.set({ openRun: button.dataset.openRun });
  } else if (button.dataset.openFlow)
    root?.querySelector<HTMLDetailsElement>('[data-info-section="runs"]')?.setAttribute("open", "");
  else if (button.dataset.doc || button.dataset.said) void copyDoc(button as HTMLButtonElement, state);
}

export function InfoTab({ card, state, openRun }: { card: Card; state: DashState; openRun: string | null }) {
  const root = useRef<HTMLDivElement>(null),
    [tick, update] = useState(0);
  repaint = () => update((n) => n + 1);
  useEffect(() => paintInfo(root.current, card, state, openRun), [card, state, openRun, tick]);
  useEffect(() => syncLog(card, openRun), [card, openRun]);
  useEffect(() => listenForToggles(root.current, card.key), [card.key]);
  return (
    <RetroCard className="info-surface">
      <div id="info" ref={root} onClick={(event) => clickInfo(event, card, state, root.current)}></div>
    </RetroCard>
  );
}
