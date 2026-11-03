import { ansiHtml } from "../lib/markup";
import { getTerminal, type TerminalState } from "./liveTerminal";

let timer: ReturnType<typeof setInterval> | null = null;

const atEnd = (pre: HTMLElement): boolean => pre.scrollHeight - pre.scrollTop - pre.clientHeight < 40;

function applyText(current: TerminalState, text: string): void {
  const pre = current.root.querySelector<HTMLElement>(".terminal-screen");
  if (!pre) return;
  current.text = text;
  current.pending = null;
  pre.innerHTML = ansiHtml(text) || "&nbsp;";
  pre.scrollTop = pre.scrollHeight;
  const jump = current.root.querySelector<HTMLElement>(".terminal-jump");
  if (jump) jump.hidden = true;
}

export function applyPendingTerminalText(current: TerminalState): void {
  if (current.pending !== null) applyText(current, current.pending);
}

export function updateTerminalCaption(current: TerminalState): void {
  const status = current.root.querySelector<HTMLElement>("[data-terminal-status]");
  if (status && current.mode === "history") status.textContent = "Showing the last 1000 lines from herdr";
}

export async function pollTerminal(): Promise<void> {
  const current = getTerminal();
  if (!current || document.hidden || !document.contains(current.root) || current.mode !== "history") return;
  if (current.polling) {
    current.pollAgain = true;
    return;
  }
  current.polling = true;
  try {
    const since = current.hash ? `&since=${encodeURIComponent(current.hash)}` : "";
    const response = await fetch(`/api/herdr/screen?pane=${encodeURIComponent(current.pane)}&source=recent${since}`, {
      cache: "no-store",
    });
    if (getTerminal() !== current || current.mode !== "history") return;
    current.hash = response.headers.get("X-Screen-Hash") || current.hash;
    if (response.status === 204) return;
    const text = await response.text();
    if (!response.ok) throw new Error(text || `screen error ${response.status}`);
    const pre = current.root.querySelector<HTMLElement>(".terminal-screen");
    if (!pre || (text === current.text && current.pending === null)) return;
    if (current.text === null || atEnd(pre)) applyText(current, text);
    else {
      current.pending = text;
      current.root.querySelector<HTMLElement>(".terminal-jump")!.hidden = false;
    }
  } catch (error) {
    const target = current.root.querySelector<HTMLElement>(".terminal-error");
    if (target) target.textContent = error instanceof Error ? error.message : "Could not read the pane";
  } finally {
    current.polling = false;
    if (current.pollAgain) {
      current.pollAgain = false;
      void pollTerminal();
    }
  }
}

export function startSnapshotPolling(): void {
  stopSnapshotPolling();
  timer = setInterval(() => void pollTerminal(), 1_500);
}

export function stopSnapshotPolling(): void {
  if (timer) clearInterval(timer);
  timer = null;
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) void pollTerminal();
});
