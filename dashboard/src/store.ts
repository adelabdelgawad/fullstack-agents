import { useSyncExternalStore } from "react";
import { getJson, postJson } from "./lib/api";
import { favKeys, needsHuman } from "./lib/cards";
import { esc } from "./lib/format";
import type { DashState, HerdrState, WaitingEntry } from "./lib/types";

const ls = {
  get(key: string, fallback: string): string {
    try {
      const v = localStorage.getItem(`fsa-${key}`);
      return v === null ? fallback : v;
    } catch {
      return fallback;
    }
  },
  set(key: string, value: string): void {
    try {
      localStorage.setItem(`fsa-${key}`, value);
    } catch {
      /* storage unavailable */
    }
  },
};

export type View = "agents" | "herdr" | "history";
export type Tab2 = "info" | "git" | "terminal";

export interface FleetSlice {
  filter: string;
  sort: string;
  text: string;
  feed: boolean;
  tilesHidden: boolean;
  tpm: number[];
}

export interface Toast {
  id: number;
  html: string;
  tone: string;
  target?: string;
  session?: unknown;
}

export interface CtxState {
  cardEl: HTMLElement;
  x: number;
  y: number;
}

export interface StoreState {
  state: DashState | null;
  herdrData: HerdrState | null;
  view: View;
  favOnly: boolean;
  wall: boolean;
  fleet: FleetSlice;
  openKey: string | null;
  openRun: string | null;
  tab2: Tab2;
  offline: boolean;
  toasts: Toast[];
  ctx: CtxState | null;
}

type Patch = Partial<StoreState> | ((s: StoreState) => Partial<StoreState>);
type Listener = () => void;

export function viewFromPath(path: string): View {
  const name = path.replace(/\/$/, "").split("/").pop();
  return name === "herdr" || name === "history" ? name : "agents";
}

const initialView = viewFromPath(window.location.pathname);

let current: StoreState = {
  state: null,
  herdrData: null,
  view: initialView,
  favOnly: ls.get("fav-only", "0") === "1",
  wall: ls.get("wall", "0") === "1",
  fleet: {
    filter: ls.get("filter", "all"),
    sort: ls.get("sort", "stage"),
    text: "",
    feed: ls.get("feed", "1") === "1",
    tilesHidden: ls.get("tiles", "1") === "0",
    tpm: [],
  },
  openKey: null,
  openRun: null,
  tab2: "info",
  offline: false,
  toasts: [],
  ctx: null,
};

const listeners = new Set<Listener>();

export const store = {
  get(): StoreState {
    return current;
  },
  set(patch: Patch): void {
    const next = typeof patch === "function" ? patch(current) : patch;
    current = { ...current, ...next };
    listeners.forEach((fn) => fn());
  },
  subscribe(fn: Listener): () => void {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
};

export function useStore<T>(selector: (s: StoreState) => T): T {
  return useSyncExternalStore(store.subscribe, () => selector(store.get()));
}

let toastId = 0;

export function toast(html: string, tone = "", target?: string, session?: unknown): void {
  const id = ++toastId;
  store.set((s) => ({ toasts: [...s.toasts, { id, html, tone, target, session }] }));
  setTimeout(() => dismissToast(id), 15000);
}

export function dismissToast(id: number): void {
  store.set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
}

export function openCtx(cardEl: HTMLElement, x: number, y: number): void {
  store.set({ ctx: { cardEl, x, y } });
}

export function closeCtx(): boolean {
  const prev = store.get().ctx;
  if (!prev) return false;
  if (document.contains(prev.cardEl)) prev.cardEl.focus();
  store.set({ ctx: null });
  return true;
}

export function openCard(key: string, keepTab = false): void {
  store.set((s) => ({ openKey: key, openRun: null, tab2: keepTab ? s.tab2 : "info" }));
  document.documentElement.classList.add("lock");
  document.documentElement.classList.toggle("split", store.get().view === "agents");
}

export function closePanel(): void {
  store.set({ openKey: null, openRun: null });
  document.documentElement.classList.remove("lock", "split");
}

export function setView(next: string, navigate = true): void {
  const view: View = next === "herdr" || next === "history" ? next : "agents";
  if (navigate && window.location.pathname !== `/next/${view}`) {
    window.history.pushState(null, "", `/next/${view}`);
  }
  ls.set("view", view);
  closePanel();
  store.set({ view });
}

export function setFavOnly(on: boolean): void {
  ls.set("fav-only", on ? "1" : "0");
  store.set({ favOnly: on });
}

export function setWall(on: boolean): void {
  ls.set("wall", on ? "1" : "0");
  store.set({ wall: on });
}

export function setFleet(patch: Partial<FleetSlice>): void {
  if ("filter" in patch) ls.set("filter", String(patch.filter));
  if ("sort" in patch) ls.set("sort", String(patch.sort));
  if ("feed" in patch) ls.set("feed", patch.feed ? "1" : "0");
  if ("tilesHidden" in patch) ls.set("tiles", patch.tilesHidden ? "0" : "1");
  store.set((s) => ({ fleet: { ...s.fleet, ...patch } }));
}

export async function toggleFavourite(key: string): Promise<void> {
  const s = store.get().state;
  const c = s?.cards.find((x) => x.key === key);
  if (!s || !c) return;
  const favourite = !c.favourite;
  const cards = s.cards.map((x) => (x.key === key ? { ...x, favourite } : x));
  store.set({ state: { ...s, cards } });
  await postJson("/api/favourite", { keys: favKeys({ ...c, favourite }), on: favourite });
  await load();
}

const stateLoadedCallbacks = new Set<() => void>();

export function onStateLoaded(fn: () => void): () => void {
  stateLoadedCallbacks.add(fn);
  return () => stateLoadedCallbacks.delete(fn);
}

let uiSeen: string | null = null;
let seen: { waiting: Set<string>; still_open: Set<string> } | null = null;

function notify(data: DashState): void {
  const ids = {
    waiting: new Set(data.waiting.map((s) => s.key + s.updated)),
    still_open: new Set(data.still_open.map((s) => s.key + s.updated)),
  };
  if (seen) {
    const notifyNew = (list: WaitingEntry[], seenSet: Set<string>, fmt: (s: WaitingEntry) => [string, string]) =>
      list
        .filter((s) => !seenSet.has(s.key + s.updated))
        .forEach((s) => {
          const [html, tone] = fmt(s);
          toast(html, tone, s.card, s);
        });
    notifyNew(data.waiting, seen.waiting, (s) => [
      `<b>Needs you:</b> ${esc(s.name)}<div class="s">${esc(s.snippet.slice(-140))}</div>`,
      "",
    ]);
    notifyNew(data.still_open, seen.still_open, (s) => [`<b>Stopped:</b> ${esc(s.name)}`, "blue"]);
  }
  seen = ids;
  const n = data.cards.filter(needsHuman).length;
  document.title = n ? `(${n}) Agents` : "Agents";
}

export async function load(): Promise<void> {
  try {
    const data = await getJson<DashState>("/api/state");
    if (uiSeen && data.ui && uiSeen !== data.ui) {
      location.reload();
      return;
    }
    uiSeen = data.ui ?? null;
    notify(data);
    store.set({ state: data, offline: false });
    stateLoadedCallbacks.forEach((fn) => fn());
    const s = store.get();
    if (s.view === "herdr" || (s.openKey && s.tab2 === "terminal")) loadHerdr();
  } catch {
    store.set({ offline: true });
  }
}

let herdrLoading: Promise<void> | null = null;

export async function loadHerdr(force = false): Promise<void> {
  if (herdrLoading) {
    if (!force) return herdrLoading;
    await herdrLoading;
  }
  const run = getJson<HerdrState>("/api/herdr")
    .then((data) => {
      store.set({ herdrData: data });
    })
    .catch(() => {
      store.set({ herdrData: { running: false, workspaces: [], tabs: [], panes: [], focused_pane_id: null } });
    })
    .finally(() => {
      herdrLoading = null;
    });
  herdrLoading = run;
  return run;
}
