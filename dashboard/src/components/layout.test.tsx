// @vitest-environment jsdom
import { act } from "react-dom/test-utils";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { Card, DashState } from "../lib/types";
import { store, viewFromPath, type View } from "../store";

function card(key: string, favourite = false): Card {
  return {
    key,
    updated: 1,
    runs: [],
    now: [],
    sessions: [],
    needs_you: [],
    phase: "implement",
    favourite,
  };
}

function dash(): DashState {
  return {
    cards: [card("one", true), card("two")],
    waiting: [],
    still_open: [],
    history: [],
    session_panes: {},
    repo: "/repo",
    locks: {},
    generated: 1,
  };
}

const VIEWS: View[] = ["agents", "herdr", "history"];

let root: Root;
let host: HTMLElement;

function render(view: View): HTMLElement {
  act(() => {
    store.set({ view });
    root.render(<App />);
  });
  return host;
}

describe("shared view layout", () => {
  it("uses page URLs and follows browser navigation", () => {
    const result = render("agents");
    for (const view of VIEWS) {
      const link = result.querySelector<HTMLAnchorElement>(`#view-${view}`)!;
      expect(link.getAttribute("href")).toBe(`/next/${view}`);
      act(() => link.click());
      expect(window.location.pathname).toBe(`/next/${view}`);
      expect(store.get().view).toBe(view);
    }
    act(() => {
      window.history.replaceState(null, "", "/next/herdr");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(store.get().view).toBe("herdr");
    expect(result.querySelector("#view-herdr")?.getAttribute("aria-selected")).toBe("true");
  });

  it.each(VIEWS)("recognizes direct %s links", (view) => {
    expect(viewFromPath(`/next/${view}`)).toBe(view);
    expect(viewFromPath(`/next/${view}/`)).toBe(view);
  });

  beforeEach(() => {
    host = document.body;
    root = createRoot(host);
    localStorage.clear();
    store.set({
      state: dash(),
      herdrData: { running: false, workspaces: [], tabs: [], panes: [], focused_pane_id: null },
      favOnly: false,
      wall: false,
      offline: false,
      fleet: { filter: "all", sort: "stage", text: "", feed: true, tilesHidden: false, tpm: [] },
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    host.replaceChildren();
    vi.unstubAllGlobals();
  });

  it.each(VIEWS)("renders the shared tabs and status on %s", (view) => {
    const result = render(view);
    const tabs = result.querySelectorAll('[role="tab"]');
    expect(Array.from(tabs, (tab) => tab.getAttribute("aria-label"))).toEqual(["Agents", "Herdr", "History"]);
    expect(result.querySelector(`#view-${view}`)?.getAttribute("aria-selected")).toBe("true");
    expect(result.querySelector("#view-agents .viewtab-count")?.textContent).toBe("2");
    expect(result.querySelector("#fwall")).not.toBeNull();
    expect(result.querySelector("#meta")).not.toBeNull();
  });

  it.each(VIEWS)("only renders Agents actions on %s", (view) => {
    const result = render(view);
    const expected = view === "agents" ? 1 : 0;
    expect(result.querySelectorAll("#newsess")).toHaveLength(expected);
    expect(result.querySelectorAll("#favsw")).toHaveLength(expected);
    expect(result.querySelectorAll("#ffeed")).toHaveLength(expected);
  });

  it("keeps the layout mounted while switching views with an inline card open", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => ({ matches: true })),
    );
    const result = render("agents");
    const header = result.querySelector("header");
    const main = result.querySelector("main");

    act(() => result.querySelector<HTMLButtonElement>('[data-orc="one"]')!.click());
    expect(result.querySelector("#orc-detail > #panel")).not.toBeNull();
    expect(() => act(() => result.querySelector<HTMLButtonElement>("#view-herdr")!.click())).not.toThrow();
    expect(result.querySelector("header")).toBe(header);
    expect(result.querySelector("main")).toBe(main);
    expect(() => act(() => result.querySelector<HTMLButtonElement>("#view-history")!.click())).not.toThrow();
    expect(result.querySelector("header")).toBe(header);
    expect(result.querySelector("main")).toBe(main);
  });
});
