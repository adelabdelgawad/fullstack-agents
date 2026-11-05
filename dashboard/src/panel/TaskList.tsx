import { retroCardHtml } from "../components/retroMarkup";
import { esc } from "../lib/format";
import type { Card } from "../lib/types";
import { infoSection } from "./panelLib";

export const taskStatusLabel = (status: string): string =>
  (
    ({
      pending: "Pending",
      in_progress: "In progress",
      running: "In progress",
      verifying: "Verifying",
      blocked: "Blocked",
      done: "Done",
      skipped: "Skipped",
      canceled: "Canceled",
    }) as Record<string, string>
  )[status] || "Unknown";
export const taskIsActive = (item: any): boolean =>
  item.is_active === true && Date.parse(item.active_until) > Date.now();

export function taskStatusIcon(status: string, active = false): string {
  const paths: Record<string, string> = {
    pending: '<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/>',
    in_progress: '<path d="M20 12a8 8 0 1 1-3-6.2M20 4v5h-5"/>',
    verifying: '<path d="M4 12.5 9 17l11-11"/><path d="M4 6h7"/>',
    blocked: '<path d="m8 3-5 5v8l5 5h8l5-5V8l-5-5ZM12 8v5m0 3h.01"/>',
    done: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    skipped: '<path d="m5 5 9 7-9 7ZM18 5v14"/>',
    canceled: '<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6m0-6-6 6"/>',
  };
  const canonical = status === "running" ? "in_progress" : status;
  const label = taskStatusLabel(status) + (active ? " — actively executing (agent-reported)" : "");
  return (
    `<span class="task-status-icon ${esc(canonical)}${active ? " executing" : ""}" role="img" ` +
    `aria-label="${esc(label)}" title="${esc(label)}"><svg viewBox="0 0 24 24" width="18" height="18" ` +
    `fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" ` +
    `aria-hidden="true" focusable="false">${paths[canonical] || paths.pending}</svg></span>`
  );
}

const SESSION_STATE_LABELS: Record<string, string> = {
  executable: "Executable",
  waiting_worker: "Waiting on worker",
  waiting_user: "Waiting on you",
  waiting_external: "Waiting on capacity or external",
  done: "Done",
};
function sessionStateHtml(state: any): string {
  if (!state) return "";
  const rows = (r: string[]) => r.join(", ");
  const lines = [
    ...state.questions.map((q: any) => `${q.id}: ${q.text} — blocks ${rows(q.rows)}: ${q.why}`),
    ...state.workers.map((w: any) =>
      w.id ? `${w.id}: ${w.text} — blocks ${rows(w.rows)}` : `${w.row}: running (${w.owner})`,
    ),
    ...state.external.map((e: any) =>
      e.class === "capacity"
        ? `waiting for ${e.engine} capacity${e.until ? ` until ${e.until}` : ""}${e.offer ? ` — ${e.offer}` : ""}`
        : `${e.id}: ${e.text} — blocks ${rows(e.rows)}`,
    ),
  ];
  return (
    `<div class="task-state"><span class="pill">${esc(SESSION_STATE_LABELS[state.state] || state.state)}</span></div>` +
    `${lines.length ? `<ul class="task-blockers">${lines.map((line) => `<li>${esc(line)}</li>`).join("")}</ul>` : ""}`
  );
}

export function taskProgressHtml(c: Card, compact = false): string {
  const sessions = c.sessions.filter((s) => s.task_tracking && Object.keys(s.task_tracking).length);
  return sessions
    .map((s) => {
      const t: any = s.task_tracking;
      if (t.error)
        return `<div class="task-overview task-error" role="alert">Task list needs attention: ${esc(t.error)}</div>`;
      const active = t.items.filter(taskIsActive),
        percent = t.total ? Math.round((t.completed / t.total) * 100) : 0;
      const counts =
        `${active.length} actively executing · ${t.counts.in_progress ?? t.counts.running ?? 0} in progress` +
        `${t.format === "v2" ? ` · ${t.counts.verifying || 0} verifying` : ""} · ${t.counts.pending || 0} pending` +
        ` · ${t.counts.blocked || 0} blocked`;
      const timeline = compact
        ? ""
        : `<ol class="task-stage-timeline" aria-label="Task stage timeline">${t.items
            .map(
              (item: any) =>
                `<li class="${esc(item.status)}" title="${esc(`${item.id}: ${item.title} — ${taskStatusLabel(item.status)}`)}" ` +
                `aria-label="${esc(`${item.id}: ${item.title} — ${taskStatusLabel(item.status)}`)}">` +
                `<span aria-hidden="true">${taskStatusIcon(item.status, taskIsActive(item))}</span>` +
                `<small>${esc(item.id)}</small></li>`,
            )
            .join("")}</ol>`;
      const unrecorded = t.format === "v2" ? t.deliverables?.completion?.unrecorded || 0 : 0;
      const title =
        t.format === "v2"
          ? `${t.completed}/${t.total} deliverables done` +
            `${t.steps?.total ? ` · steps ${t.steps.completed}/${t.steps.total}` : ""}` +
            `${unrecorded ? ` · ${unrecorded} without evidence` : ""}`
          : `${t.completed}/${t.total} tasks done`;
      return retroCardHtml(
        `<section class="task-overview ${compact ? "compact" : "session-task-overview"}" aria-label="Task progress">` +
          `<div class="task-progress-title"><b>${esc(title)}</b><span>${percent}%</span></div>` +
          `<progress max="${esc(Math.max(t.total, 1))}" value="${esc(t.completed)}" aria-label="Completed tasks"></progress>` +
          `<div class="s">${esc(counts)}</div>` +
          `${compact && active.length ? `<div class="s task-current">${esc(`${active[0].id}: ${active[0].title}`)}` : ""}` +
          `${compact && active.length > 1 ? ` · +${active.length - 1} active` : ""}` +
          `${compact && active.length ? "</div>" : ""}` +
          `${timeline}${t.format === "v2" ? sessionStateHtml(t.session_state) : ""}</section>`,
        "task-progress-frame",
      );
    })
    .join("");
}

function taskRow(t: any, x: any): string {
  const state = x.status === "running" ? "in_progress" : x.status,
    live = taskIsActive(x);
  const completion =
    t.format === "v2" && x.status === "done" && x.completion === "unrecorded"
      ? '<span class="tt-badge unrecorded" title="Marked done before evidence tracking, or upgraded from a legacy ledger">' +
        "no recorded evidence</span>"
      : t.format === "v2" && x.status === "done" && x.completion === "evidence_with_baseline"
        ? '<span class="tt-badge baseline" title="Completed using an attributed baseline failure">baseline failures</span>'
        : "";
  return (
    `<li class="tracked-task ${esc(state)}${live ? " executing" : ""}">${taskStatusIcon(x.status, live)}` +
    `<div class="tt-main"><div class="tt-top"><b>${esc(x.id)}</b><span class="tt-title">${esc(x.title)}` +
    `${t.format === "v2" && x.parent ? ` <span class="s">(step of ${esc(x.parent)})</span>` : ""}</span>` +
    `<span class="tt-badges">` +
    `${live ? '<span class="tt-badge live" title="Agent-reported activity expires automatically; ' : ""}` +
    `${live ? 'it is separate from process detection">Actively executing</span>' : ""}` +
    `<span class="tt-badge ${esc(state)}">${esc(taskStatusLabel(x.status))}</span>${completion}</span></div>\n        ` +
    `<div class="s task-activity"><span class="tt-owner">${esc(x.owner || "Unassigned")}</span>` +
    `${x.activity ? ` · ${esc(x.activity)}` : ""}</div>${x.note ? `<div class="s tt-note">${esc(x.note)}</div>` : ""}` +
    `</div></li>`
  );
}

export function taskListHtml(c: Card): string {
  const sessions = c.sessions.filter((s) => s.task_tracking && Object.keys(s.task_tracking).length);
  if (!sessions.length) return "";
  const body = sessions
    .map((s) => {
      const t: any = s.task_tracking;
      if (t.error) return `<div role="alert" class="snip"><b>${esc(s.name || s.id)}</b>: ${esc(t.error)}</div>`;
      const count = (key: string) => t.counts[key] ?? (key === "in_progress" ? t.counts.running : 0) ?? 0;
      const tiles = ["in_progress", "verifying", "blocked", "pending", "done", "skipped", "canceled"]
        .filter((key) => count(key) || ["in_progress", "blocked", "pending", "done"].includes(key))
        .map(
          (key) =>
            `<div class="tt-tile ${esc(key)}" title="${esc(taskStatusLabel(key))}">${taskStatusIcon(key)}` +
            `<div><div class="so-l">${esc(taskStatusLabel(key))}</div>` +
            `<div class="tt-n">${esc(count(key))}</div></div></div>`,
        )
        .join("");
      const order: Record<string, number> = {
        in_progress: 0,
        running: 0,
        verifying: 1,
        blocked: 2,
        pending: 3,
        done: 4,
        skipped: 5,
        canceled: 6,
      };
      const sorted = [...t.items].sort(
        (a, b) => Number(taskIsActive(b)) - Number(taskIsActive(a)) || order[a.status] - order[b.status],
      );
      const source = `/api/doc?sid=${encodeURIComponent(s.id)}&path=${encodeURIComponent(t.file)}`,
        percent = t.total ? Math.round((t.completed / t.total) * 100) : 0;
      return retroCardHtml(
        `<article class="tracked-plan"><div class="tp-head"><div class="tp-title"><b>${esc(t.title)}</b>` +
          `<a class="tp-file" href="${esc(source)}" target="_blank" rel="noopener">${esc(t.relative_file)}</a></div>` +
          `<div class="tp-done"><b>${esc(t.completed)}/${esc(t.total)} done</b><span>${percent}%</span></div></div>` +
          `${t.format === "v2" ? sessionStateHtml(t.session_state) : ""}\n      ` +
          `<progress max="${esc(Math.max(t.total, 1))}" value="${esc(t.completed)}" aria-label="Completed tasks"></progress>` +
          `<div class="task-counts">${tiles}</div><ul class="tracked-tasks" tabindex="0" aria-label="Tasks; scroll for more">` +
          `${sorted.map((item) => taskRow(t, item)).join("")}</ul></article>`,
        "tracked-plan-frame",
      );
    })
    .join("");
  const ok: any[] = sessions.map((s) => s.task_tracking).filter((t: any) => !t.error),
    done = ok.reduce((n, t) => n + (t.completed || 0), 0),
    all = ok.reduce((n, t) => n + (t.total || 0), 0);
  return infoSection(c, "task-list", "Tasks", body, all ? `<span class="chip">${done}/${all} done</span>` : "");
}
