// @vitest-environment jsdom
import { act } from "react-dom/test-utils";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { Card, DashState } from "../lib/types";
import { store, type View } from "../store";
import { AgentsView } from "../views/AgentsView";
import { HerdrView } from "../views/HerdrView";
import { HistoryView } from "../views/HistoryView";

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

const VIEWS = [
  ["agents", AgentsView],
  ["herdr", HerdrView],
  ["history", HistoryView],
] as const;

let root: Root;
let host: HTMLDivElement;

function render(view: View, ViewComponent: () => React.ReactNode): HTMLElement {
  act(() => {
    store.set({ view });
    root.render(<ViewComponent />);
  });
  return host;
}

describe("shared view layout", () => {
  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
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
    host.remove();
  });

  it.each(VIEWS)("renders the shared tabs and status on %s", (view, ViewComponent) => {
    const result = render(view, ViewComponent);
    const tabs = result.querySelectorAll('[role="tab"]');
    expect(Array.from(tabs, (tab) => tab.getAttribute("aria-label"))).toEqual(["Agents", "Herdr", "History"]);
    expect(result.querySelector(`#view-${view}`)?.getAttribute("aria-selected")).toBe("true");
    expect(result.querySelector("#view-agents .viewtab-count")?.textContent).toBe("2");
    expect(result.querySelector("#fwall")).not.toBeNull();
    expect(result.querySelector("#meta")).not.toBeNull();
  });

  it.each(VIEWS)("only renders Agents actions on %s", (view, ViewComponent) => {
    const result = render(view, ViewComponent);
    const expected = view === "agents" ? 1 : 0;
    expect(result.querySelectorAll("#newsess")).toHaveLength(expected);
    expect(result.querySelectorAll("#favsw")).toHaveLength(expected);
    expect(result.querySelectorAll("#ffeed")).toHaveLength(expected);
  });
});
