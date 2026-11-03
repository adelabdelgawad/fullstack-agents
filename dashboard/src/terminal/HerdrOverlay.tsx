import { useEffect, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { saidText } from "../lib/markup";
import { load, loadHerdr, store } from "../store";
import { copySelection } from "./copy";
import { closeHerdrClient, remountHerdrClient } from "./herdrClient";
import { HerdrMenu, type HerdrMenuItem } from "./herdrMenus";
import { getTerminal, mountTerminal, stopTerminal, terminalSelection } from "./liveTerminal";

export interface HerdrConfirmOpts {
  confirm?: string;
  after?: () => void;
}

interface ActionResult {
  ok: boolean;
  error?: unknown;
}
type ModalKind = "prompt" | "confirm" | "new" | "start" | "unavailable";
interface ModalState {
  kind: ModalKind;
  returnFocus: HTMLElement | null;
  title?: string;
  detail?: string;
  action?: string;
  params?: Record<string, unknown>;
  value?: string;
  confirm?: string;
  after?: () => void;
  pane?: Record<string, unknown>;
}
interface MenuState {
  kind: "menu";
  returnFocus: HTMLElement | null;
  items: HerdrMenuItem[];
  x: number;
  y: number;
}
type OverlayState = ModalState | MenuState | null;

let overlay: OverlayState = null;
let actionError = "";
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((listener) => listener());
const subscribe = (listener: () => void) => (listeners.add(listener), () => listeners.delete(listener));
const getSnapshot = () => overlay;
const field = (record: Record<string, unknown>, key: string): string => String(record[key] ?? "");

function setOverlay(next: OverlayState): void {
  overlay = next;
  emit();
}

function herdrErrorMessage(error: unknown): string {
  const text = typeof error === "string" ? error : JSON.stringify(error || "");
  try {
    const parsed = JSON.parse(text) as { error?: { message?: string }; message?: string };
    return parsed.error?.message || parsed.message || text || "Herdr action failed";
  } catch {
    return text || "Herdr action failed";
  }
}

function setHerdrError(error: unknown, ownerRoot: HTMLElement | null): void {
  actionError = herdrErrorMessage(error);
  document.querySelectorAll<HTMLElement>(".herdr-page-error").forEach((element) => {
    element.textContent = actionError;
  });
  ownerRoot?.querySelectorAll<HTMLElement>(".herdr-modal-error").forEach((element) => {
    element.textContent = actionError;
  });
}

export async function herdrAction(
  action: string,
  params: Record<string, unknown> = {},
  ownerRoot: HTMLElement | null = null,
): Promise<ActionResult> {
  actionError = "";
  document.querySelectorAll<HTMLElement>(".herdr-page-error").forEach((element) => {
    element.textContent = "";
  });
  ownerRoot?.querySelectorAll<HTMLElement>(".herdr-modal-error").forEach((element) => {
    element.textContent = "";
  });
  let data: ActionResult;
  try {
    const response = await fetch("/api/herdr/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, ...params }),
    });
    data = response.headers.get("Content-Type")?.includes("application/json")
      ? ((await response.json()) as ActionResult)
      : { ok: false, error: await response.text() };
    if (!response.ok || !data.ok) setHerdrError(data.error || `Herdr action failed (${response.status})`, ownerRoot);
  } catch (error) {
    data = { ok: false, error: error instanceof Error ? error.message : "Herdr action failed" };
    setHerdrError(data.error, ownerRoot);
  }
  await loadHerdr(true);
  return data;
}

export function closeHerdrOverlay(restoreFocus = true): void {
  if (!overlay) return;
  const returnFocus = overlay.returnFocus;
  setOverlay(null);
  if (restoreFocus && returnFocus && document.contains(returnFocus)) returnFocus.focus();
}

function openMenu(items: HerdrMenuItem[], x: number, y: number, returnFocus: HTMLElement | null): void {
  closeHerdrOverlay(false);
  setOverlay({ kind: "menu", items, x, y, returnFocus });
}

function openPrompt(
  title: string,
  value: string,
  action: string,
  params: Record<string, unknown>,
  returnFocus: HTMLElement | null,
): void {
  closeHerdrOverlay(false);
  setOverlay({ kind: "prompt", title, value, action, params, returnFocus });
}

export function openHerdrConfirm(
  title: string,
  detail: string,
  action: string,
  params: Record<string, unknown>,
  returnFocus: HTMLElement | null,
  opts: HerdrConfirmOpts = {},
): void {
  closeHerdrOverlay(false);
  setOverlay({
    kind: "confirm",
    title,
    detail,
    action,
    params,
    returnFocus,
    confirm: opts.confirm || "close",
    after: opts.after,
  });
}

export async function openNewSession(returnFocus: HTMLElement): Promise<void> {
  if (!store.get().herdrData) await loadHerdr();
  const data = store.get().herdrData;
  const workspaces = (data?.workspaces || []) as Record<string, unknown>[];
  closeHerdrOverlay(false);
  setOverlay({ kind: !data?.running || !workspaces.length ? "unavailable" : "new", returnFocus });
}

function openStartAgent(pane: Record<string, unknown>, returnFocus: HTMLElement): void {
  closeHerdrOverlay(false);
  setOverlay({ kind: "start", pane, returnFocus });
}

function paneSaid(paneId: string): string | null {
  const state = store.get().state;
  const sid = Object.keys(state?.session_panes || {}).find((id) => state?.session_panes[id] === paneId);
  return sid ? saidText(sid, state) : null;
}

function workspaceItems(record: Record<string, unknown>, returnFocus: HTMLElement): HerdrMenuItem[] {
  const panes = store.get().herdrData?.panes || [];
  const id = field(record, "workspace_id");
  const label = field(record, "label") || id;
  const count = panes.filter((pane) => field(pane, "workspace_id") === id).length;
  return [
    {
      label: "Rename",
      run: () => openPrompt("rename workspace", label, "workspace.rename", { workspace_id: id }, returnFocus),
    },
    {
      label: "Close",
      run: () =>
        openHerdrConfirm(
          "Close workspace?",
          `${label} — ${count} ${count === 1 ? "pane" : "panes"}`,
          "workspace.close",
          { workspace_id: id },
          returnFocus,
        ),
    },
  ];
}

function tabItems(record: Record<string, unknown>, returnFocus: HTMLElement): HerdrMenuItem[] {
  const data = store.get().herdrData;
  const id = field(record, "tab_id");
  const workspaceId = field(record, "workspace_id");
  const label = field(record, "label") || `Tab ${field(record, "number")}`;
  const count = (data?.panes || []).filter((pane) => field(pane, "tab_id") === id).length;
  const number = (data?.tabs || []).filter((tab) => field(tab, "workspace_id") === workspaceId).length + 1;
  return [
    {
      label: "New tab",
      run: () => openPrompt("new tab", String(number), "tab.create", { workspace_id: workspaceId }, returnFocus),
    },
    { label: "Rename", run: () => openPrompt("rename tab", label, "tab.rename", { tab_id: id }, returnFocus) },
    {
      label: "Close",
      run: () =>
        openHerdrConfirm(
          "Close tab?",
          `${label} — ${count} ${count === 1 ? "pane" : "panes"}`,
          "tab.close",
          { tab_id: id },
          returnFocus,
        ),
    },
  ];
}

function paneItems(record: Record<string, unknown>, returnFocus: HTMLElement): HerdrMenuItem[] {
  const id = field(record, "pane_id");
  const name = field(record, "title") || field(record, "agent") || id;
  const focused = store.get().herdrData?.focused_pane_id;
  const selected = getTerminal()?.pane === id ? terminalSelection() : "";
  const said = paneSaid(id);
  return [
    ...(selected ? [{ label: "Copy", run: () => void copySelection(selected) }] : []),
    ...(said ? [{ label: "Copy last message", run: () => void copySelection(said) }] : []),
    { label: "Rename pane", run: () => openPrompt("rename pane", name, "pane.rename", { pane_id: id }, returnFocus) },
    { label: "Clear pane name", run: () => void herdrAction("pane.clear_name", { pane_id: id }) },
    ...(focused && focused !== id
      ? [
          {
            label: "Swap with focused pane",
            run: () => void herdrAction("pane.swap", { source_pane_id: id, target_pane_id: focused }),
          },
        ]
      : []),
    { label: "Split right", run: () => void herdrAction("pane.split", { pane_id: id, direction: "right" }) },
    { label: "Split down", run: () => void herdrAction("pane.split", { pane_id: id, direction: "down" }) },
    { label: "Zoom", run: () => void herdrAction("pane.zoom", { pane_id: id }) },
    { label: "Start agent…", run: () => openStartAgent(record, returnFocus) },
    {
      label: "Close pane",
      run: () => openHerdrConfirm("Close pane?", name, "pane.close", { pane_id: id }, returnFocus),
    },
  ];
}

export function openHerdrContextMenu(kind: string, item: unknown, x: number, y: number, anchor: HTMLElement): void {
  const record = item as Record<string, unknown>;
  const items =
    kind === "workspace"
      ? workspaceItems(record, anchor)
      : kind === "tab"
        ? tabItems(record, anchor)
        : paneItems(record, anchor);
  openMenu(items, x, y, anchor);
}

function ModalFrame({ children, submit }: { children: React.ReactNode; submit?: (form: HTMLFormElement) => void }) {
  return (
    <div className="herdr-modal-backdrop">
      <div className="herdr-modal" role="dialog" aria-modal="true">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            submit?.(event.currentTarget);
          }}
        >
          {children}
        </form>
      </div>
    </div>
  );
}

function PromptModal({ state }: { state: ModalState }) {
  const submit = async (form: HTMLFormElement) => {
    const input = form.elements.namedItem("label") as HTMLInputElement;
    if (!input.value || input.value.length > 80 || input.value.startsWith("-"))
      return setHerdrError(
        'Name must be 1–80 characters and not start with "-"',
        form.closest<HTMLElement>(".herdr-modal-backdrop"),
      );
    const result = await herdrAction(
      state.action || "",
      { ...state.params, label: input.value },
      form.closest<HTMLElement>(".herdr-modal-backdrop"),
    );
    if (result.ok) closeHerdrOverlay(false);
  };
  return (
    <ModalFrame submit={(form) => void submit(form)}>
      <h2>{state.title}</h2>
      <label>
        name
        <input name="label" defaultValue={state.value} maxLength={80} autoComplete="off" autoFocus />
      </label>
      <div className="herdr-modal-error" aria-live="polite"></div>
      <div className="herdr-modal-actions">
        <button type="button" data-herdr-cancel="" onClick={() => closeHerdrOverlay()}>
          cancel
        </button>
        <button type="submit" className="primary">
          save
        </button>
      </div>
    </ModalFrame>
  );
}

function ConfirmModal({ state }: { state: ModalState }) {
  const submit = async (form: HTMLFormElement) => {
    const button = form.querySelector<HTMLButtonElement>('[type="submit"]')!;
    button.disabled = true;
    const result = await herdrAction(
      state.action || "",
      state.params,
      form.closest<HTMLElement>(".herdr-modal-backdrop"),
    );
    button.disabled = false;
    if (result.ok) {
      closeHerdrOverlay(false);
      state.after?.();
    }
  };
  return (
    <ModalFrame submit={(form) => void submit(form)}>
      <h2>{state.title}</h2>
      <p className="herdr-modal-detail">{state.detail}</p>
      <div className="herdr-modal-error" aria-live="polite"></div>
      <div className="herdr-modal-actions">
        <button type="submit" className="danger">
          {state.confirm}
        </button>
        <button type="button" data-herdr-cancel="" onClick={() => closeHerdrOverlay()}>
          cancel
        </button>
      </div>
    </ModalFrame>
  );
}

const engines = {
  claude: ["Claude", "Opens a new tab in the space and runs cc -n '<name>'"],
  codex: ["Codex", "Opens a new tab in the space, named <name>, and runs codex"],
  grok: ["Grok", "Opens a new tab in the space, named <name>, and runs opencode -m xai/grok-4.7"],
};

function NewSessionModal() {
  const data = store.get().herdrData!;
  const workspaces = data.workspaces as Record<string, unknown>[];
  const focused = (data.panes as Record<string, unknown>[]).find(
    (pane) => field(pane, "pane_id") === data.focused_pane_id,
  );
  const current = focused ? field(focused, "workspace_id") : field(workspaces[0], "workspace_id");
  const submit = async (form: HTMLFormElement) => {
    const name = (form.elements.namedItem("name") as HTMLInputElement).value.trim();
    if (!name || name.length > 80 || name.startsWith("-"))
      return setHerdrError(
        'Name must be 1–80 characters and not start with "-"',
        form.closest<HTMLElement>(".herdr-modal-backdrop"),
      );
    const button = form.querySelector<HTMLButtonElement>('[type="submit"]')!;
    button.disabled = true;
    button.textContent = "starting…";
    const result = await herdrAction(
      "session.create",
      {
        workspace_id: (form.elements.namedItem("space") as HTMLSelectElement).value,
        name,
        engine: (form.elements.namedItem("engine") as HTMLSelectElement).value,
      },
      form.closest<HTMLElement>(".herdr-modal-backdrop"),
    );
    if (result.ok) {
      closeHerdrOverlay();
      void load();
    } else {
      button.disabled = false;
      button.textContent = "start";
    }
  };
  return (
    <ModalFrame submit={(form) => void submit(form)}>
      <h2>new session</h2>
      <label>
        agent
        <select
          name="engine"
          defaultValue="claude"
          onChange={(event) => {
            const note = event.currentTarget.form?.querySelector<HTMLElement>("[data-engine-note]");
            if (note) note.textContent = engines[event.currentTarget.value as keyof typeof engines][1];
          }}
        >
          {Object.entries(engines).map(([key, value]) => (
            <option key={key} value={key}>
              {value[0]}
            </option>
          ))}
        </select>
      </label>
      <label>
        name
        <input name="name" maxLength={80} autoComplete="off" required autoFocus />
      </label>
      <label>
        space
        <select name="space" defaultValue={current}>
          {workspaces.map((workspace) => (
            <option key={field(workspace, "workspace_id")} value={field(workspace, "workspace_id")}>
              {field(workspace, "label") || field(workspace, "workspace_id")}
            </option>
          ))}
        </select>
      </label>
      <p className="herdr-modal-note" data-engine-note="">
        {engines.claude[1]}
      </p>
      <div className="herdr-modal-error" aria-live="polite"></div>
      <div className="herdr-modal-actions">
        <button type="button" data-herdr-cancel="" onClick={() => closeHerdrOverlay()}>
          cancel
        </button>
        <button type="submit" className="primary">
          start
        </button>
      </div>
    </ModalFrame>
  );
}

function StartAgentModal({ state }: { state: ModalState }) {
  const kinds = (store.get().herdrData?.agent_kinds as string[] | undefined) || [];
  const initial = kinds.includes("claude") ? "claude" : kinds[0] || "claude";
  const submit = async (form: HTMLFormElement) => {
    const name = (form.elements.namedItem("name") as HTMLInputElement).value;
    if (!name || name.length > 80 || name.startsWith("-"))
      return setHerdrError(
        'Name must be 1–80 characters and not start with "-"',
        form.closest<HTMLElement>(".herdr-modal-backdrop"),
      );
    const kind = (form.elements.namedItem("kind") as HTMLSelectElement).value;
    const result = await herdrAction(
      "agent.start",
      { pane_id: field(state.pane || {}, "pane_id"), kind, name },
      form.closest<HTMLElement>(".herdr-modal-backdrop"),
    );
    if (result.ok || String(result.error || "").includes("agent_not_ready")) closeHerdrOverlay(false);
  };
  return (
    <ModalFrame submit={(form) => void submit(form)}>
      <h2>start agent</h2>
      <label>
        kind
        <select name="kind" defaultValue={initial}>
          {(kinds.length ? kinds : [initial]).map((kind) => (
            <option key={kind} value={kind}>
              {kind}
            </option>
          ))}
        </select>
      </label>
      <label>
        name
        <input name="name" defaultValue={initial} maxLength={80} autoComplete="off" />
      </label>
      <p className="herdr-modal-note">The pane must be at a shell prompt</p>
      <div className="herdr-modal-error" aria-live="polite"></div>
      <div className="herdr-modal-actions">
        <button type="button" data-herdr-cancel="" onClick={() => closeHerdrOverlay()}>
          cancel
        </button>
        <button type="submit" className="primary">
          start
        </button>
      </div>
    </ModalFrame>
  );
}

function OverlayPortal({ state }: { state: Exclude<OverlayState, null> }) {
  if (state.kind === "menu") return createPortal(<HerdrMenu {...state} close={closeHerdrOverlay} />, document.body);
  if (state.kind === "prompt") return createPortal(<PromptModal state={state} />, document.body);
  if (state.kind === "confirm") return createPortal(<ConfirmModal state={state} />, document.body);
  if (state.kind === "new") return createPortal(<NewSessionModal />, document.body);
  if (state.kind === "start") return createPortal(<StartAgentModal state={state} />, document.body);
  return createPortal(
    <ModalFrame>
      <h2>new session</h2>
      <p className="herdr-modal-note">herdr is not running or has no spaces</p>
      <div className="herdr-modal-actions">
        <button type="button" data-herdr-cancel="" onClick={() => closeHerdrOverlay()}>
          close
        </button>
      </div>
    </ModalFrame>,
    document.body,
  );
}

function useLifecycle(): void {
  useEffect(() => {
    let view = store.get().view;
    const unsubscribe = store.subscribe(() => {
      const next = store.get().view;
      if (next === view) return;
      view = next;
      closeHerdrOverlay(false);
      stopTerminal();
      if (next !== "herdr") closeHerdrClient();
    });
    const hide = () => {
      stopTerminal();
      closeHerdrClient();
    };
    const show = (event: PageTransitionEvent) => {
      if (!event.persisted || getTerminal()) return;
      const state = store.get();
      if (state.view === "herdr") remountHerdrClient();
      else if (state.openKey && state.tab2 === "terminal") {
        const root = document.querySelector<HTMLElement>(".terminal[data-terminal-pane]");
        if (root?.dataset.terminalPane) mountTerminal(root, root.dataset.terminalPane);
      }
    };
    addEventListener("pagehide", hide);
    addEventListener("pageshow", show);
    return () => {
      unsubscribe();
      removeEventListener("pagehide", hide);
      removeEventListener("pageshow", show);
    };
  }, []);
}

export function HerdrOverlay() {
  const state = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  useLifecycle();
  useEffect(() => {
    const pointer = (event: PointerEvent) => {
      if (
        overlay?.kind === "menu" &&
        !(event.target instanceof Node && document.querySelector(".herdr-menu")?.contains(event.target))
      )
        closeHerdrOverlay(false);
    };
    const key = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || !overlay) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      closeHerdrOverlay();
    };
    const resize = () => closeHerdrOverlay(false);
    document.addEventListener("pointerdown", pointer, true);
    document.addEventListener("keydown", key, true);
    addEventListener("resize", resize);
    return () => {
      document.removeEventListener("pointerdown", pointer, true);
      document.removeEventListener("keydown", key, true);
      removeEventListener("resize", resize);
    };
  }, []);
  return state ? <OverlayPortal state={state} /> : null;
}
