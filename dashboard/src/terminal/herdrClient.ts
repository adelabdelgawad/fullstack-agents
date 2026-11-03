import type { Terminal } from "@xterm/xterm";
import type { FitAddon } from "@xterm/addon-fit";
import type { WebglAddon } from "@xterm/addon-webgl";
import { copySelection } from "./copy";
import { filesFromPaste, LIVE_UPLOAD_MAX_BYTES, uploadFiles, uploadingText, wireFileDrop } from "./files";
import { createOsc52Scanner } from "./osc52";

declare global {
  interface Window {
    Terminal?: typeof Terminal;
    FitAddon?: { FitAddon: typeof FitAddon };
    WebglAddon?: { WebglAddon: typeof WebglAddon };
  }
}

interface HerdrClientState {
  root: HTMLElement;
  term?: Terminal;
  fit?: FitAddon;
  renderer?: string;
  ws?: WebSocket;
  resizeObserver?: ResizeObserver;
  size?: string;
  scanOsc52?: (bytes: Uint8Array) => void;
  setStatus?: (text: string) => void;
}

let herdrClient: HerdrClientState | null = null;

function webglRendererOk(): boolean {
  try {
    const gl = document.createElement("canvas").getContext("webgl2");
    if (!gl) return false;
    const info = gl.getExtension("WEBGL_debug_renderer_info");
    return !/SwiftShader/i.test(info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)) : "");
  } catch {
    return false;
  }
}

export function closeHerdrClient(): void {
  if (!herdrClient) return;
  herdrClient.ws?.close();
  herdrClient.resizeObserver?.disconnect();
  herdrClient.term?.dispose();
  herdrClient = null;
}

function liveStatus(client: HerdrClientState): string {
  return `live · ${client.renderer} · ${client.term?.cols}×${client.term?.rows}`;
}

function flashStatus(client: HerdrClientState, text: string): void {
  client.setStatus?.(text);
  setTimeout(() => {
    if (herdrClient === client && client.ws?.readyState === WebSocket.OPEN) client.setStatus?.(liveStatus(client));
  }, 2_000);
}

function wireAttach(client: HerdrClientState): void {
  const host = client.root.querySelector<HTMLElement>(".herdr-client-host");
  const picker = client.root.querySelector<HTMLInputElement>("[data-herdr-client-attach-input]");
  if (!host || !picker) return;
  const attach = async (files: File[]) => {
    if (files.some((file) => file.size > LIVE_UPLOAD_MAX_BYTES))
      return flashStatus(client, "file is too large (50 MB maximum)");
    client.setStatus?.(uploadingText(files));
    try {
      const paths = await uploadFiles(files, "/api/herdr/file?");
      if (herdrClient !== client) return;
      client.term?.paste(paths.join(" ") + " ");
      flashStatus(client, paths.length === 1 ? "file attached" : `${paths.length} files attached`);
    } catch (error) {
      flashStatus(client, error instanceof Error ? error.message : "upload failed");
    }
    if (!matchMedia("(pointer: coarse)").matches) client.term?.focus();
  };
  client.root.querySelector<HTMLElement>("[data-herdr-client-attach]")!.onclick = () => picker.click();
  picker.onchange = () => {
    const files = [...(picker.files ?? [])];
    picker.value = "";
    if (files.length) void attach(files);
  };
  host.addEventListener(
    "paste",
    (event) => {
      const files = filesFromPaste(event);
      if (files.length) void attach(files);
    },
    true,
  );
  wireFileDrop(host, (files) => void attach(files));
}

function fullscreenElement(): Element | null {
  return (
    document.fullscreenElement ||
    (document as Document & { webkitFullscreenElement?: Element }).webkitFullscreenElement ||
    null
  );
}

function wireFullscreen(client: HerdrClientState): void {
  const button = client.root.querySelector<HTMLButtonElement>("[data-herdr-client-fullscreen]");
  if (!button) return;
  const root = client.root as HTMLElement & { webkitRequestFullscreen?: () => Promise<void> };
  const sync = () => {
    const on = fullscreenElement() === root || root.classList.contains("herdr-fill");
    button.textContent = on ? "exit full screen" : "full screen";
    button.setAttribute("aria-pressed", String(on));
    if (!on && !matchMedia("(pointer: coarse)").matches) client.term?.focus();
  };
  root.addEventListener("fullscreenchange", sync);
  root.addEventListener("webkitfullscreenchange", sync);
  button.onclick = async () => {
    if (root.classList.contains("herdr-fill")) {
      root.classList.remove("herdr-fill");
      return sync();
    }
    try {
      const request = root.requestFullscreen || root.webkitRequestFullscreen;
      if (!request) throw new Error("no element fullscreen");
      await request.call(root);
    } catch {
      root.classList.add("herdr-fill");
      sync();
    }
  };
}

function connectHerdrClient(client: HerdrClientState): void {
  const term = client.term;
  if (!term) return;
  client.root.querySelector<HTMLElement>("[data-herdr-client-reconnect]")!.hidden = true;
  client.size = `${term.cols}x${term.rows}`;
  client.setStatus?.(`connecting · ${client.renderer} · ${term.cols}×${term.rows}`);
  const query = new URLSearchParams({ cols: String(term.cols), rows: String(term.rows) });
  const ws = new WebSocket(
    `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/herdr/client?${query}`,
  );
  ws.binaryType = "arraybuffer";
  client.ws = ws;
  ws.onopen = () => client.setStatus?.(liveStatus(client));
  ws.onmessage = (event) => {
    if (typeof event.data === "string") return;
    const bytes = new Uint8Array(event.data as ArrayBuffer);
    client.scanOsc52?.(bytes);
    term.write(bytes);
  };
  ws.onclose = (event) => {
    client.setStatus?.(`disconnected${event.reason ? `: ${event.reason}` : ""} (code ${event.code})`);
    client.root.querySelector<HTMLElement>("[data-herdr-client-reconnect]")!.hidden = false;
  };
}

async function prepareHerdrClient(client: HerdrClientState, status: HTMLElement): Promise<void> {
  client.setStatus = (text) => {
    status.textContent = text;
    status.title = text;
    status.classList.toggle("is-live", text.startsWith("live"));
  };
  client.root.oncontextmenu = (event) => event.preventDefault();
  await Promise.all(
    ["400", "700"].flatMap((weight) =>
      ["normal", "italic"].map((style) =>
        document.fonts.load(`${style === "italic" ? "italic " : ""}${weight} 14.5px "JetBrains Mono Web"`),
      ),
    ),
  );
}

function createHerdrTerminal(client: HerdrClientState, host: HTMLElement): { term: Terminal; fit: FitAddon } {
  const root = client.root;
  const mono = getComputedStyle(document.documentElement).getPropertyValue("--mono").trim();
  const TerminalCtor = window.Terminal!,
    FitAddonCtor = window.FitAddon!.FitAddon;
  const term = new TerminalCtor({
    fontFamily: `"JetBrains Mono Web", ${mono}`,
    fontSize: 14.5,
    letterSpacing: 1,
    scrollback: 0,
    cursorBlink: true,
    theme: { background: getComputedStyle(root).getPropertyValue("--herdr-panel-bg").trim(), foreground: "#ffffff" },
  });
  const fit = new FitAddonCtor();
  term.loadAddon(fit);
  term.open(host);
  client.term = term;
  client.fit = fit;
  client.renderer = "dom";
  return { term, fit };
}

function loadHerdrRenderer(client: HerdrClientState, term: Terminal, fit: FitAddon): void {
  if (window.WebglAddon && webglRendererOk()) {
    const addon = new window.WebglAddon.WebglAddon();
    addon.onContextLoss(() => {
      addon.dispose();
      client.renderer = "dom";
      fit.fit();
    });
    term.loadAddon(addon);
    client.renderer = "webgl";
  }
  fit.fit();
}

function wireHerdrTerminal(
  client: HerdrClientState,
  host: HTMLElement,
  status: HTMLElement,
  term: Terminal,
  fit: FitAddon,
): void {
  const onCopyText = (text: string) => {
    if (text) void copySelection(text, () => term.focus());
  };
  client.scanOsc52 = createOsc52Scanner(onCopyText);
  host.addEventListener("mouseup", () =>
    setTimeout(() => {
      if (term.hasSelection()) onCopyText(term.getSelection());
    }),
  );
  wireFullscreen(client);
  wireAttach(client);
  client.root.querySelector<HTMLElement>("[data-herdr-client-reconnect]")!.onclick = () => connectHerdrClient(client);
  client.resizeObserver = new ResizeObserver(() => {
    fit.fit();
    const next = `${term.cols}x${term.rows}`;
    if (next === client.size) return;
    client.size = next;
    if (status.textContent?.startsWith("live")) client.setStatus?.(liveStatus(client));
    if (client.ws?.readyState === WebSocket.OPEN)
      client.ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
  });
  client.resizeObserver.observe(host);
  term.onData((data) => {
    if (client.ws?.readyState === WebSocket.OPEN) client.ws.send(new TextEncoder().encode(data));
  });
  term.onBinary((data) => {
    if (client.ws?.readyState === WebSocket.OPEN)
      client.ws.send(Uint8Array.from(data, (char) => char.charCodeAt(0) & 255));
  });
  connectHerdrClient(client);
  term.focus();
}

export async function mountHerdrClient(root: HTMLElement): Promise<void> {
  closeHerdrClient();
  const client: HerdrClientState = { root };
  herdrClient = client;
  const host = root.querySelector<HTMLElement>(".herdr-client-host");
  const status = root.querySelector<HTMLElement>("[data-herdr-client-status]");
  if (!host || !status || !window.Terminal || !window.FitAddon?.FitAddon) return;
  await prepareHerdrClient(client, status);
  if (herdrClient !== client) return;
  const { term, fit } = createHerdrTerminal(client, host);
  loadHerdrRenderer(client, term, fit);
  wireHerdrTerminal(client, host, status, term, fit);
}

export function remountHerdrClient(): void {
  const root = document.querySelector<HTMLElement>(".herdr-client");
  if (root) void mountHerdrClient(root);
}
