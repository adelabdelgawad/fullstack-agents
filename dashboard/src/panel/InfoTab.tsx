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
  return `<div class="detail"><div><b>End of task</b> ${stateChip(r)} ${flags}</div>${live ? '<div class="s">Still running — the result lands here when it finishes.</div>' : r.summary ? `<pre>${esc(r.summary)}</pre>` : '<div class="s">No result text was recorded.</div>'}${(r.open_risks || []).length ? `<div class="s"><b>Open risks:</b> ${esc(r.open_risks.join(" · "))}</div>` : ""}<div class="row" style="margin:6px 0 0"><button class="action-button" data-log="1" style="margin-left:0">${showLog ? "Hide log" : "Show log"}</button></div>${showLog ? `<pre class="log" id="log">${esc(logSeen || "loading…")}</pre>` : ""}<div class="endbar ${tone}"><button class="action-button" data-collapse="1" title="Collapse this task">Hide ▴</button></div></div>`;
}

function stepsHtml(c: any): string {
  if (!c.steps.length)
    return c.sessions.length
      ? '<div class="s">The lead has not listed its steps for this task yet; “Session” above shows what it is doing.</div>'
      : "";
  return `<ul class="steps">${c.steps.map((x: any) => `<li class="${esc(x.state)}"><span class="mk" aria-label="${esc(x.state)}">${STEP_MARK[x.state] || "○"}</span><span class="tx">${esc(x.text)}</span>${x.note ? `<span class="nt">${esc(x.note)}</span>` : ""}</li>`).join("")}</ul>`;
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
    `<tr class="${["failed", "abandoned"].includes(r.state) ? "bad" : ""}"><td>${r.lead ? `<b>${esc(r.name)}</b>` : esc(r.name)}<div class="s">${esc(r.kind)}${r.cause ? ` · ${esc(r.cause)}` : ""}</div></td><td><span class="mchip m-${modelFamily(r.u.model)}">${esc(modelShort(r.u.model) || "?")}</span></td><td>${esc(STATE_TEXT[r.state] || r.state || "")}</td><td class="num">${r.u.fill !== undefined ? `${Math.round(r.u.fill * 100)}%<span class="orc-bar"><span style="width:${Math.round(r.u.fill * 100)}%"></span></span>` : "—"}</td><td class="num">${num(r.u.tokens, fmtTokens)}</td><td class="num">${fmtCost(r.u.cost)}</td><td class="num">${r.at ? ago(r.at) : ""}</td></tr>`;
  return infoSection(
    c,
    "workers",
    `Orchestrator and workers (${rows.length})`,
    `<table class="usage-table"><thead><tr><th>Agent</th><th>Model</th><th>State</th><th>Context</th><th>Tokens</th><th>Est. cost</th><th>Age</th></tr></thead><tbody>${rows.map(tr).join("")}</tbody></table><div class="s">Cost is an estimate from token counts and a price table, not a bill.</div>`,
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
    ? `<ol class="detail-feed">${items.map((e) => `<li class="${esc(e.tone)}"><time>${time(e.at)}</time> ${esc(e.text)}</li>`).join("")}</ol>`
    : '<div class="s">No activity recorded since the dashboard started.</div>';
  return infoSection(c, "activity", "Recent activity", body, "", true);
}

export function infoHtml(c: Card, state: DashState, openRun: string | null): string {
  const tasks = c.runs
    .map((r: any) => {
      const open = openRun === r.id;
      return `<li class="task${open ? " open" : ""}" data-run="${esc(r.id)}"><input type="checkbox" disabled ${r.state === "done" ? "checked" : ""} aria-label="${esc(r.state)}"><div class="th"><span class="tn">${esc(r.unit || r.id)}</span> ${stateChip(r)} <span class="s">${LIVE(r) ? `<span class="live-dot"></span>running ${duration(r)}` : `took ${duration(r)} · ${ago(r.updated)} ago`}</span><span class="caret">${open ? "▾" : "▸"}</span></div>${r.goal ? `<div class="snip tg">${esc(r.goal)}</div>` : ""}${open ? detailHtml(r) : ""}</li>`;
    })
    .join("");
  const sessions: any[] = c.sessions || [],
    now: any[] = c.now || [],
    lead: any = sessions.find((s) => s.name === c.title) || sessions[0] || now[0] || {};
  const engineName = (e: string) => (e === "codex" ? "Codex" : e === "claude" ? "Claude" : e || "Agent");
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
  const stamp = (t: number) => (t ? new Date(t * 1000).toLocaleString() : "Time not recorded"),
    history = sessions.flatMap((s) => s.workflow_history || []).sort((a: any, b: any) => a.timestamp - b.timestamp);
  const auditor = audit
    ? [engineName(audit.engine), audit.model || "model not recorded"].join(" · ")
    : lead.workflow_auditor
      ? `Claude · ${lead.workflow_auditor} (selected; no audit recorded)`
      : "No audit recorded";
  const timeline = (events: any[]) =>
    `<ol class="info-timeline">${events.map((e) => `<li><b>${esc(e.phase)}</b> <time>${esc(stamp(e.timestamp))}</time>${e.note ? `<div class="s">${esc(e.note)}</div>` : ""}</li>`).join("")}</ol>`;
  const leadChecks = lead.workflow_checks?.length
      ? `<div class="snip"><b>Lead-reported checks</b><pre>${esc(lead.workflow_checks.join("\n"))}</pre></div>`
      : "",
    desc = (c as any).desc || (c as any).goal;
  const registered = runs
    .map(
      (r) =>
        `<article class="info-run"><b>${esc(r.role)}</b> · ${esc(engineName(r.engine))} · ${esc(r.model || "model not recorded")} <span class="chip">${esc(r.state)}</span>${r.verdict ? ` · ${esc(r.verdict)}` : ""}<div class="s">${esc(stamp(r.updated))}</div>${r.summary ? `<div class="snip">${esc(r.summary.slice(0, 320))}</div>${infoDisclosure(c, `run-${r.run_id}`, "Full run summary", `<pre>${esc(r.summary)}</pre>`)}` : ""}${r.brief ? infoDisclosure(c, `brief-${r.run_id}`, "Brief", `<pre>${esc(r.brief)}</pre>`) : ""}<div class="s">Run ${esc(r.run_id)}</div></article>`,
    )
    .join("");
  const checks =
    ((c as any).chips || [])
      .filter((x: any) => x.kind === "tests")
      .map(
        (x: any) =>
          `<div class="snip"><b>Worker-reported checks</b> ${esc(x.verdict)}${x.label ? ` · ${esc(x.label)}` : ""}</div>`,
      )
      .join("") +
    [...runs, ...c.runs]
      .filter((r: any) => r.tests?.length)
      .map(
        (r: any) =>
          `<div class="snip"><b>Worker-reported checks</b><pre>${esc(JSON.stringify(r.tests, null, 2))}</pre></div>`,
      )
      .join("");
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
  const tile = (label: string, value: any, cls = "", extra = "") =>
      `<div class="so-tile ${cls}"><div class="so-l">${esc(label)}</div><div class="so-v">${esc(value)}</div>${extra}</div>`,
    usage: any = c.usage,
    context = usage ? `${Math.round(usage.fill * 100)}%${usage.compactions ? ` · ${usage.compactions}×` : ""}` : "—";
  const tones: Record<string, string> = { working: "live", blocked: "bad", done: "done" };
  const overview = `<section class="session-overview" aria-label="Session overview"><div class="so-head"><span class="so-ico" aria-hidden="true"></span><b>Session health</b><span class="pill ${tones[status] || ""}">${esc(status)}</span><span class="so-right">${need ? `<span class="pill bad">${need} need${need === 1 ? "s" : ""} you</span>` : ""}<span class="pill">${esc(phase)}</span></span></div><div class="so-tiles">${tile("Phase", phase)}${tile("Tasks done", all ? `${done}/${all}` : "—", "", all ? `<div class="so-bar" aria-hidden="true"><span style="width:${Math.round((done / all) * 100)}%"></span></div>` : "")}${tile("Running now", liveTotal(liveSets(c)), "live")}${tile("Needs you", need, need ? "bad" : "")}${tile("Context", context, usage?.blowout ? "bad" : "", usage ? `<div class="so-bar" aria-hidden="true"><span style="width:${Math.round(usage.fill * 100)}%"></span></div>` : "")}${tile("Est. cost", fmtCost(usage?.cost))}${tile("Tokens / min", fmtTokens(usage?.tpm))}${tile("Latest activity", stamp(activity.updated || c.updated), "time")}</div></section>`;
  return `<div class="info-grid">${overview}${taskProgressHtml(c)}${workersSection(c)}${activitySection(c, state)}<div class="session-activity">${liveHtml(c)}</div>${infoSection(c, "summary", "Summary", `<b>${esc(c.title)}</b><dl class="info-facts"><dt>State</dt><dd>${esc(status)}</dd><dt>Phase</dt><dd>${esc(phase)}</dd><dt>Lead</dt><dd>${esc(engineName(lead.engine))}${lead.model ? ` · ${esc(lead.model)}` : ""}</dd><dt>Auditor</dt><dd>${esc(auditor)}</dd><dt>Latest activity</dt><dd>${esc(stamp(activity.updated || c.updated))}</dd></dl>`)}${infoSection(c, "progress", "Progress", `${history.length ? timeline(history.slice(-8)) + (history.length > 8 ? infoDisclosure(c, "history", "Earlier phase history", timeline(history.slice(0, -8))) : "") : '<div class="s">No phase history recorded.</div>'}${activity.action ? `<div class="snip"><b>${activity.action_running ? "Running now" : "Latest action"}</b> ${esc(activity.action)}</div>` : ""}${c.steps?.length ? stepsHtml(c) : ""}${(c as any).declared?.note ? `<div class="snip">${esc((c as any).declared.note)}</div>` : ""}`)}${infoSection(c, "result", "Result", `${lead.workflow_summary ? `<div class="snip"><b>Lead-reported summary</b><pre>${esc(lead.workflow_summary)}</pre></div>` : message ? `<div class="snip">${esc(lastPara(message.said || message.said_full).slice(0, 400))}</div>${infoDisclosure(c, "message", `Full message from ${engineName(message.engine)}`, `<button class="copy-ico" data-said="${esc(message.id)}" aria-label="Copy the last message">${COPY_ICON}</button>${saidHtml(message)}`)}` : '<div class="s">No agent update recorded.</div>'}<div class="snip"><b>Audit</b> ${audit ? esc(audit.state) + (audit.verdict ? ` · ${esc(audit.verdict)}` : " · no verdict recorded") : "No registered audit result."}</div>${leadChecks}${checks}${blockers.length ? `<div class="snip"><b>Blockers / needs you</b><ul>${[...new Set(blockers)].map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>` : ""}`)}${infoDisclosure(c, "session", "Session details", (now.length ? now : sessions).map((s) => resumeHtml(s, state)).join("") + runs.map((r) => `<div class="mono">${esc(r.run_id)} · ${esc(r.root || "")} · ${esc(r.artifact || "")}</div>`).join("") + `<div class="mono">${esc(c.worktree || c.repo || "")}</div>` + now.map((s) => `<div class="s">Pane: ${esc(state.session_panes[s.id] || "not recorded")}</div>`).join(""))}${infoDisclosure(c, "runs", "Worker and audit runs", (desc ? infoDisclosure(c, "task-brief", "Task brief", `<pre>${esc(desc)}</pre>`) : "") + registered + (tasks ? `<ul class="tasks">${tasks}</ul>` : "") + (!runs.length && !tasks ? '<div class="s">No run records available.</div>' : ""))}${taskListHtml(c)}</div>`;
}

function fitTaskLists(root: HTMLElement): void {
  root.querySelectorAll<HTMLElement>(".tracked-tasks").forEach((list) => {
    const height = [...list.children].slice(0, 10).reduce((n, row) => n + row.getBoundingClientRect().height, 0);
    if (height > 0) list.style.maxHeight = `${Math.ceil(height)}px`;
  });
}

export function InfoTab({ card, state, openRun }: { card: Card; state: DashState; openRun: string | null }) {
  const root = useRef<HTMLDivElement>(null),
    [tick, update] = useState(0);
  repaint = () => update((n) => n + 1);
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    if (el.dataset.card === card.key)
      infoOpen.set(
        card.key,
        new Map(
          [...el.querySelectorAll<HTMLDetailsElement>("[data-info-section]")].map((d) => [
            d.dataset.infoSection || "",
            d.open,
          ]),
        ),
      );
    keepScroll(el, () => {
      el.innerHTML = infoHtml(card, state, openRun);
    });
    el.dataset.card = card.key;
    fitTaskLists(el);
  }, [card, state, openRun, tick]);
  useEffect(() => {
    const r: any = openRun && card.runs.find((x) => x.id === openRun);
    if (!r || !showLog) {
      stopLog();
      return;
    }
    if (LIVE(r)) {
      wasLive = true;
      if (!logTimer) {
        void pollLog(r.id);
        logTimer = setInterval(() => void pollLog(r.id), 2500);
      }
    } else {
      stopLog();
      if (wasLive || !logSeen) {
        wasLive = false;
        void pollLog(r.id);
      }
    }
    return stopLog;
  }, [card, openRun]);
  useEffect(() => {
    const node = root.current;
    if (!node) return;
    const toggle = (event: Event) => {
      const el = event.target as HTMLDetailsElement;
      if (!el.dataset.infoSection) return;
      const keys = infoOpen.get(card.key) || new Map();
      keys.set(el.dataset.infoSection, el.open);
      infoOpen.set(card.key, keys);
      fitTaskLists(node);
    };
    node.addEventListener("toggle", toggle, true);
    return () => node.removeEventListener("toggle", toggle, true);
  }, [card.key]);
  const click = (event: React.MouseEvent) => {
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
          .map((x) => x.id),
      );
      repaint?.();
    } else if (button.dataset.openRun) {
      prepareRunLog(button.dataset.openRun, card.key);
      store.set({ openRun: button.dataset.openRun });
    } else if (button.dataset.openFlow)
      root.current?.querySelector<HTMLDetailsElement>('[data-info-section="runs"]')?.setAttribute("open", "");
    else if (button.dataset.doc || button.dataset.said) void copyDoc(button as HTMLButtonElement, state);
  };
  return <div id="info" ref={root} onClick={click}></div>;
}
