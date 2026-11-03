import type { IDisposable, Terminal } from "@xterm/xterm";
import type { FitAddon } from "@xterm/addon-fit";
import { LIVE_UPLOAD_MAX_BYTES, filesFromPaste, uploadFiles, uploadingText, wireFileDrop } from "./files";
import { copySelection } from "./copy";
import { applyPendingTerminalText, pollTerminal, startSnapshotPolling, stopSnapshotPolling, updateTerminalCaption } from "./snapshotTerminal";

declare global {
  interface Window {
    Terminal?: typeof Terminal;
    FitAddon?: { FitAddon: typeof FitAddon };
  }
}

export interface ScrollState {
  session: string | null;
  scrollLines: number;
  scrollFrame: number;
  scrollSending: boolean;
}

export interface TerminalState extends ScrollState {
  root: HTMLElement;
  pane: string;
  mode: "live" | "history";
  text: string | null;
  hash: string | null;
  pending: string | null;
  polling: boolean;
  pollAgain: boolean;
  term: Terminal | null;
  fit: FitAddon | null;
  stream: EventSource | null;
  resizeObserver: ResizeObserver | null;
  resizeTimer: ReturnType<typeof setTimeout> | null;
  reconnectTimer: ReturnType<typeof setTimeout> | null;
  retries: number;
  inputQueue: Uint8Array[];
  inputFrame: number;
  inputSending: boolean;
  postChain: Promise<void>;
  postAbort: AbortController | null;
  liveEpoch: number;
  liveDisposables: IDisposable[];
  imageStatus: string;
  imageStatusTimer: ReturnType<typeof setTimeout> | null;
  started: boolean;
  lagging?: boolean;
  rtt?: number;
}

let terminal: TerminalState | null = null;

export const getTerminal = (): TerminalState | null => terminal;

export function terminalSelection(current = terminal): string {
  if (!current) return "";
  if (current.mode === "live") return current.term?.hasSelection() ? current.term.getSelection() : "";
  const selection = getSelection();
  const history = current.root.querySelector(".terminal-screen");
  return selection && selection.rangeCount && history?.contains(selection.anchorNode) ? selection.toString() : "";
}

const bytes64 = (bytes: Uint8Array): string => {
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  return btoa(binary);
};

const base64Bytes = (value: string): Uint8Array => Uint8Array.from(atob(value), (char) => char.charCodeAt(0));

function liveStatusText(current: TerminalState): string {
  return `live · ${current.term?.cols ?? 0}×${current.term?.rows ?? 0}${current.lagging ? " · sending…" : current.rtt ? ` · ${Math.round(current.rtt)} ms` : ""}`;
}

function liveTerminalStatus(current: TerminalState, reason: string | null): void {
  const status = current.root.querySelector<HTMLElement>("[data-terminal-status]");
  const actions = current.root.querySelector<HTMLElement>("[data-terminal-reconnect]");
  const disconnected = current.root.querySelector<HTMLElement>(".terminal-disconnected");
  if (!status || !actions || !disconnected || !current.term) return;
  if (reason === null) {
    status.textContent = current.imageStatus || liveStatusText(current);
    status.classList.toggle("lagging", Boolean(current.lagging));
    actions.hidden = true;
    disconnected.hidden = true;
    return;
  }
  clearTimeout(current.imageStatusTimer ?? undefined);
  current.imageStatus = "";
  status.classList.remove("lagging");
  status.textContent = `${reason} · ${current.term.cols}×${current.term.rows}`;
  const reasonEl = current.root.querySelector<HTMLElement>("[data-terminal-reason]");
  if (reasonEl) reasonEl.textContent = /already has an attached client/.test(reason) ? "This pane is open live in another view" : reason;
  actions.hidden = false;
  disconnected.hidden = false;
}

function closeLiveStream(current: TerminalState): void {
  current.liveEpoch += 1;
  current.postAbort?.abort();
  current.postAbort = null;
  clearTimeout(current.reconnectTimer ?? undefined);
  current.reconnectTimer = null;
  current.stream?.close();
  current.stream = null;
  current.session = null;
}

async function postLiveTerminal(current: TerminalState, body: unknown): Promise<void> {
  if (!current.session || terminal !== current) return;
  const session = current.session;
  const epoch = current.liveEpoch;
  current.postChain = current.postChain.then(async () => {
    if (current.liveEpoch !== epoch || terminal !== current) return;
    const started = performance.now();
    const response = await fetch("/api/herdr/live/input", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session, ...body as object }),
      signal: current.postAbort?.signal,
    });
    current.rtt = current.rtt ? current.rtt * 0.7 + (performance.now() - started) * 0.3 : performance.now() - started;
    if (!response.ok) throw new Error((await response.text()) || `terminal input error ${response.status}`);
  }).catch((error: Error) => {
    if (error.name !== "AbortError" && terminal === current) {
      const target = current.root.querySelector<HTMLElement>(".terminal-error");
      if (target) target.textContent = error.message || "Could not write to the pane";
    }
  });
  return current.postChain;
}

function flushTerminalInput(current: TerminalState): void {
  current.inputFrame = 0;
  if (!current.session || !current.inputQueue.length || current.inputSending) return;
  const joined = new Uint8Array(current.inputQueue.reduce((sum, bytes) => sum + bytes.length, 0));
  let offset = 0;
  current.inputQueue.forEach((bytes) => {
    joined.set(bytes, offset);
    offset += bytes.length;
  });
  current.inputQueue.length = 0;
  current.inputSending = true;
  void postLiveTerminal(current, { type: "input", bytes: bytes64(joined) }).finally(() => {
    current.inputSending = false;
    if (current.inputQueue.length) flushTerminalInput(current);
  });
}

function queueTerminalInput(current: TerminalState, bytes: Uint8Array): void {
  current.inputQueue.push(bytes);
  if (!current.inputFrame) current.inputFrame = requestAnimationFrame(() => flushTerminalInput(current));
}

export function queueTerminalScroll(current: ScrollState, lines: number, frame = requestAnimationFrame): void {
  current.scrollLines = (current.scrollLines || 0) + lines;
  if (!current.scrollFrame) current.scrollFrame = frame(() => flushTerminalScroll(current));
}

export function flushTerminalScroll(
  current: ScrollState,
  post: (state: ScrollState, body: unknown) => Promise<void> = (state, body) => postLiveTerminal(state as TerminalState, body),
): void {
  current.scrollFrame = 0;
  if (!current.session) {
    current.scrollLines = 0;
    return;
  }
  if (current.scrollSending || !current.scrollLines) return;
  const lines = Math.max(-100, Math.min(100, current.scrollLines));
  current.scrollLines -= lines;
  current.scrollSending = true;
  void post(current, { type: "scroll", direction: lines < 0 ? "up" : "down", lines: Math.abs(lines) }).finally(() => {
    current.scrollSending = false;
    if (current.scrollLines) flushTerminalScroll(current, post);
  });
}

const reconnectDelay = (attempt: number): number => Math.min(10_000, 1_000 * 2 ** Math.max(0, attempt - 1));

export function liveTerminalClosed(
  current: Pick<TerminalState, "retries" | "reconnectTimer">,
  reason: string,
  show: (reason: string) => void = (message) => liveTerminalStatus(current as TerminalState, message),
  schedule: typeof setTimeout = setTimeout,
): void {
  if ("stream" in current) closeLiveStream(current as TerminalState);
  if (/ownership|owner|conflict|already.*control|attached client|in use/i.test(reason)) {
    show(reason);
    return;
  }
  current.retries = (current.retries || 0) + 1;
  const delay = reconnectDelay(current.retries);
  if (current.retries > 3) show(reason);
  else if ("root" in current) {
    const status = (current as TerminalState).root.querySelector<HTMLElement>("[data-terminal-status]");
    status?.classList.add("lagging");
    if (status) status.textContent = `reconnecting in ${Math.round(delay / 1_000)}s · ${reason}`;
  }
  current.reconnectTimer = schedule(() => {
    const live = current as TerminalState;
    if (terminal === live && live.mode === "live") openLiveStream(live);
  }, delay);
}

function openLiveStream(current: TerminalState, takeover = false): void {
  closeLiveStream(current);
  current.postAbort = new AbortController();
  const cols = current.term?.cols ?? 0;
  const rows = current.term?.rows ?? 0;
  const stream = new EventSource(`/api/herdr/live?pane=${encodeURIComponent(current.pane)}&cols=${cols}&rows=${rows}${takeover ? "&takeover=1" : ""}`);
  current.stream = stream;
  stream.addEventListener("ready", (event) => {
    if (terminal !== current || current.stream !== stream) return;
    try {
      current.session = (JSON.parse((event as MessageEvent<string>).data) as { session: string }).session;
    } catch {
      return liveTerminalClosed(current, "Invalid terminal session");
    }
    current.retries = 0;
    liveTerminalStatus(current, null);
    flushTerminalInput(current);
  });
  stream.addEventListener("frame", (event) => {
    if (terminal !== current || current.stream !== stream || !current.term) return;
    try {
      current.term.write(base64Bytes((JSON.parse((event as MessageEvent<string>).data) as { bytes: string }).bytes));
    } catch {
      liveTerminalClosed(current, "Invalid terminal frame");
    }
  });
  stream.addEventListener("closed", (event) => {
    let reason = "Terminal closed";
    try { reason = (JSON.parse((event as MessageEvent<string>).data) as { reason?: string }).reason || reason; } catch {}
    if (terminal === current && current.stream === stream) liveTerminalClosed(current, reason);
  });
  stream.onerror = () => terminal === current && current.stream === stream && liveTerminalClosed(current, "Connection closed");
}

function terminalTheme(root: HTMLElement, foreground: string): Record<string, string> {
  const css = getComputedStyle(root);
  const colour = (name: string) => css.getPropertyValue(name).trim();
  return { background: colour("--herdr-panel-bg"), foreground, cursor: colour("--herdr-accent"), selectionBackground: colour("--herdr-selection-bg"), black: "#282c34", red: "#e06c75", green: "#98c379", yellow: "#e5c07b", blue: "#61afef", magenta: "#c678dd", cyan: "#56b6c2", white: "#abb2bf", brightBlack: "#5c6370", brightRed: "#e06c75", brightGreen: "#98c379", brightYellow: "#e5c07b", brightBlue: "#61afef", brightMagenta: "#c678dd", brightCyan: "#56b6c2", brightWhite: "#ffffff" };
}

function startLiveTerminal(current: TerminalState, restoreFocus = false): void {
  const host = current.root.querySelector<HTMLElement>(".terminal-live");
  const box = current.root.querySelector<HTMLElement>(".terminal-screen-box");
  if (!host || !box || !window.Terminal || !window.FitAddon?.FitAddon) return liveTerminalStatus(current, "Terminal assets unavailable");
  current.term = new window.Terminal({ scrollback: 0, fontFamily: getComputedStyle(document.documentElement).getPropertyValue("--mono").trim(), fontSize: 12, cursorBlink: true, theme: terminalTheme(current.root, getComputedStyle(current.root).getPropertyValue("--herdr-text").trim()) });
  current.fit = new window.FitAddon.FitAddon();
  current.term.loadAddon(current.fit);
  current.term.open(host);
  current.fit.fit();
  current.liveDisposables = [
    current.term.onData((data) => queueTerminalInput(current, new TextEncoder().encode(data))),
    current.term.onBinary((data) => queueTerminalInput(current, Uint8Array.from(data, (char) => char.charCodeAt(0) & 255))),
  ];
  current.term.attachCustomWheelEventHandler((event) => {
    if (!event.deltaY) return false;
    const px = Math.abs(event.deltaY) * (event.deltaMode === 1 ? 40 : event.deltaMode === 2 ? 400 : 1);
    queueTerminalScroll(current, Math.sign(event.deltaY) * Math.max(1, Math.round(px / 40)));
    return false;
  });
  current.resizeObserver = new ResizeObserver(() => current.fit?.fit());
  current.resizeObserver.observe(box);
  box.onclick = () => current.term?.focus();
  openLiveStream(current);
  if (restoreFocus) current.term.focus();
}

async function attachLiveFiles(current: TerminalState, files: File[]): Promise<void> {
  if (terminal !== current || current.mode !== "live" || !current.session || !current.term) return;
  if (files.some((file) => file.size > LIVE_UPLOAD_MAX_BYTES)) return showStatus(current, "file is too large (50 MB maximum)");
  showStatus(current, uploadingText(files));
  try {
    const paths = await uploadFiles(files, `/api/herdr/live/file?session=${encodeURIComponent(current.session)}&`);
    current.term.paste(paths.join(" ") + " ");
    showStatus(current, paths.length === 1 ? "file attached" : `${paths.length} files attached`);
  } catch (error) {
    showStatus(current, error instanceof Error ? error.message : "upload failed");
  }
  current.term.focus();
}

function showStatus(current: TerminalState, message: string): void {
  current.imageStatus = message;
  const status = current.root.querySelector<HTMLElement>("[data-terminal-status]");
  if (status) status.textContent = message;
}

function wireTerminalExtras(current: TerminalState): void {
  const host = current.root.querySelector<HTMLElement>(".terminal-live");
  const history = current.root.querySelector<HTMLElement>(".terminal-screen");
  const box = current.root.querySelector<HTMLElement>(".terminal-screen-box");
  const picker = current.root.querySelector<HTMLInputElement>("[data-attach-input]");
  if (!host || !history || !box || !picker) return;
  const paste = (event: ClipboardEvent) => {
    const files = filesFromPaste(event);
    if (files.length) void attachLiveFiles(current, files);
  };
  host.addEventListener("paste", paste, true);
  history.addEventListener("paste", paste, true);
  current.root.querySelector<HTMLElement>("[data-attach]")!.onclick = () => picker.click();
  picker.onchange = () => {
    const files = [...(picker.files ?? [])];
    picker.value = "";
    if (files.length) void attachLiveFiles(current, files);
  };
  wireFileDrop(box, (files) => void attachLiveFiles(current, files));
  host.addEventListener("mouseup", () => setTimeout(() => {
    if (current.term?.hasSelection()) void copySelection(current.term.getSelection(), () => current.term?.focus());
  }));
  history.addEventListener("mouseup", () => setTimeout(() => {
    const selection = getSelection();
    if (!selection?.rangeCount || !history.contains(selection.anchorNode)) return;
    const range = selection.getRangeAt(0).cloneRange();
    const text = selection.toString();
    if (text.trim()) void copySelection(text, () => { selection.removeAllRanges(); selection.addRange(range); });
  }));
  const jump = current.root.querySelector<HTMLElement>(".terminal-jump")!;
  jump.onclick = () => applyPendingTerminalText(current);
  history.onscroll = () => {
    if (current.pending !== null && history.scrollHeight - history.scrollTop - history.clientHeight < 40) applyPendingTerminalText(current);
  };
}

export function switchTerminalMode(current: TerminalState, mode: "live" | "history", restoreFocus = false): void {
  if (terminal !== current) return;
  stopSnapshotPolling();
  if (current.mode === "live" && mode !== "live") disposeLiveTerminal(current);
  current.mode = mode;
  current.mode = mode;
  current.root.querySelectorAll<HTMLElement>("[data-mode]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.mode === mode)));
  const history = current.root.querySelector<HTMLElement>(".terminal-screen");
  const host = current.root.querySelector<HTMLElement>(".terminal-live");
  if (!history || !host) return;
  if (mode === "live") {
    history.hidden = true;
    current.root.querySelector<HTMLElement>(".terminal-jump")!.hidden = true;
    host.hidden = false;
    startLiveTerminal(current, restoreFocus);
  }
  else {
    host.hidden = true;
    history.hidden = false;
    updateTerminalCaption(current);
    void pollTerminal();
    startSnapshotPolling();
    if (restoreFocus) history.focus();
  }
  current.started = true;
}

function disposeLiveTerminal(current: TerminalState): void {
  closeLiveStream(current);
  clearTimeout(current.resizeTimer ?? undefined);
  current.resizeObserver?.disconnect();
  current.liveDisposables.forEach((disposable) => disposable.dispose());
  current.term?.dispose();
  current.term = null;
  current.fit = null;
  current.inputQueue.length = 0;
  current.scrollLines = 0;
}

export function stopTerminal(): void {
  stopSnapshotPolling();
  if (terminal) disposeLiveTerminal(terminal);
  terminal = null;
}

export function mountTerminal(root: HTMLElement, pane: string, mode: "live" | "history" = "live"): void {
  stopTerminal();
  terminal = { root, pane, mode, text: null, hash: null, pending: null, polling: false, pollAgain: false, term: null, fit: null, stream: null, session: null, resizeObserver: null, resizeTimer: null, reconnectTimer: null, retries: 0, inputQueue: [], inputFrame: 0, inputSending: false, postChain: Promise.resolve(), postAbort: null, liveEpoch: 0, liveDisposables: [], imageStatus: "", imageStatusTimer: null, started: false, scrollLines: 0, scrollFrame: 0, scrollSending: false };
  const current = terminal;
  current.root.querySelectorAll<HTMLElement>("[data-mode]").forEach((button) => {
    button.onclick = () => switchTerminalMode(current, button.dataset.mode === "history" ? "history" : "live", true);
  });
  current.root.querySelector<HTMLElement>("[data-reconnect]")!.onclick = () => openLiveStream(current);
  current.root.querySelectorAll<HTMLElement>("[data-takeover]").forEach((button) => button.onclick = () => openLiveStream(current, true));
  wireTerminalExtras(current);
  switchTerminalMode(current, mode);
}

addEventListener("online", () => {
  if (terminal?.mode === "live" && terminal.term && !terminal.stream && terminal.reconnectTimer) openLiveStream(terminal);
});
