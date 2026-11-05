import { retroCardHtml } from "../components/retroMarkup";
import { esc } from "../lib/format";
import type { Card, Run } from "../lib/types";

export const LIVE = (r: any): boolean => r.state === "running" || r.state === "stalled";
export const STEP_MARK: Record<string, string> = { done: "✓", active: "▸", skipped: "–", pending: "○" };
export const AGENT_NAMES: Record<string, string> = {
  shell: "bg shell",
  "bounded-extractor": "haiku scan",
  "test-runner": "test-runner",
  "diff-reviewer": "diff-review",
  "general-purpose": "general",
  Explore: "explore",
};
export const enc = encodeURIComponent;

export const infoOpen = new Map<string, Map<string, boolean>>();
export const infoShown = (c: Card, key: string, open: boolean): boolean => infoOpen.get(c.key)?.get(key) ?? open;

export function infoDisclosure(c: Card, key: string, title: string, body: string): string {
  return retroCardHtml(
    `<details class="info-card" data-info-section="${esc(key)}"${infoShown(c, key, false) ? " open" : ""}>` +
      `<summary>${esc(title)}</summary>${body}</details>`,
    "info-frame info-disclosure",
  );
}

export function infoSection(c: Card, key: string, title: string, body: string, extra = "", open = false): string {
  return retroCardHtml(
    `<details class="info-card info-top ${esc(key)}" data-info-section="${esc(key)}"` +
      `${infoShown(c, key, open) ? " open" : ""}><summary><h4>${esc(title)}</h4>${extra}</summary>${body}</details>`,
    `info-frame info-top ${key}`,
  );
}

const scrollKey = (el: Element): string =>
  `${(el.closest("[data-info-section]") as HTMLElement | null)?.dataset.infoSection || ""}|${el.tagName}.${(el as HTMLElement).className}`;

export function keepScroll(root: HTMLElement, apply: () => void): void {
  const boxes = () =>
    root.querySelectorAll<HTMLElement>(
      "pre:not(.log), .flist, .shell-facts, .goal, .live-shells, .tracked-tasks, .task-stage-timeline",
    );
  const saved = new Map(
    [...boxes()].filter((e) => e.scrollTop || e.scrollLeft).map((e) => [scrollKey(e), [e.scrollTop, e.scrollLeft]]),
  );
  const own = root.scrollTop;
  apply();
  boxes().forEach((e) => {
    const at = saved.get(scrollKey(e));
    if (at) [e.scrollTop, e.scrollLeft] = at;
  });
  root.scrollTop = own;
}

export const stateChip = (r: any): string =>
  `<span class="chip ${(r.flags || []).length ? "bad" : r.state === "done" ? "ok" : ""}">${esc(r.state)}</span>`;

export function duration(r: any): string {
  const seconds = Math.max(0, Math.round((LIVE(r) ? Date.now() / 1000 : r.updated) - (r.started || r.updated)));
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s`;
  return `${Math.floor(seconds / 3600)}h ${String(Math.floor((seconds % 3600) / 60)).padStart(2, "0")}m`;
}

export const stc = (s: string): string => (s === "?" ? "U" : s);
export const diffHtml = (text: string): string =>
  (text || "")
    .split("\n")
    .map((line) => {
      const tone =
        line.startsWith("+") && !line.startsWith("+++")
          ? "a"
          : line.startsWith("-") && !line.startsWith("---")
            ? "d"
            : line.startsWith("@@")
              ? "h"
              : "";
      return `<span class="${tone}">${esc(line) || "&#8203;"}</span>`;
    })
    .join("");

export const dismissed = (() => {
  try {
    return new Set<string>(JSON.parse(localStorage.getItem("fsa-dismissed") || "[]"));
  } catch {
    return new Set<string>();
  }
})();

export const isDone = (x: any): boolean => !["running", "stalled"].includes(x.state);
export const notDismissed = (x: any): boolean => !(isDone(x) && dismissed.has(x.id));
export function dismiss(ids: string[]): void {
  ids.forEach((id) => dismissed.add(id));
  try {
    localStorage.setItem("fsa-dismissed", JSON.stringify([...dismissed].slice(-500)));
  } catch {}
}
export const dismissButton = (x: any): string =>
  x && isDone(x)
    ? `<button class="action-button dismiss" data-dismiss="${esc(x.id)}" ` +
      `aria-label="Dismiss ${esc(x.unit || x.label || x.id)}">Dismiss</button>`
    : "";
export const factRow = (key: string, value: unknown): string =>
  value ? `<dt>${esc(key)}</dt><dd>${esc(value)}</dd>` : "";
export const RECENT_S = 900;
export const recentRuns = (c: Card | null, sid?: string): any[] =>
  ((c && c.runs) || []).filter(
    (r: any) =>
      (!sid || !r.session || r.session === sid) && (LIVE(r) || Date.now() / 1000 - (r.updated || 0) < RECENT_S),
  );
export const runSession = (r: any, c: Card): string => r.session || ((c.now || [])[0] || {}).id || "";
export const shortPath = (p: unknown): string =>
  String(p || "")
    .split("/")
    .filter(Boolean)
    .slice(-2)
    .join("/");

export function factList(c: Card | null, key: string, title: string, items: unknown[]): string {
  if (!items?.length) return "";
  return (
    `<details data-info-section="${esc(key)}"${c && infoShown(c, key, false) ? " open" : ""}>` +
    `<summary>${esc(title)} (${items.length})</summary><pre>${esc(items.join("\n"))}</pre></details>`
  );
}

export function shellRun(a: any, c: Card | null): Run | null {
  const x = a.shell || {},
    runs = (c && c.runs) || [];
  return (
    (x.run && runs.find((r) => r.id === x.run)) ||
    (x.brief && runs.filter((r: any) => r.unit === x.brief).slice(-1)[0]) ||
    null
  );
}
