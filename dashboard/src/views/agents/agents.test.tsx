import { act } from "react-dom/test-utils";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { Card, DashState } from "../../lib/types";
import { store } from "../../store";
import { FleetTiles } from "./FleetTiles";
import { OrcCard, orcPlan } from "./OrcCard";
import { Orchestrators } from "./Orchestrators";
import { WorkerSquares } from "./Workers";

function card(patch: Partial<Card> = {}): Card {
  return {
    key: "k",
    title: "Search",
    label: "",
    tree: null,
    updated: 100,
    runs: [],
    now: [],
    sessions: [{ id: "s1", name: "lead", state: "idle", branch: "main" }],
    usage: null,
    needs_you: [],
    phase: "implement",
    steps: [],
    rounds: [],
    repo: "/home/u/repo",
    worktree: "",
    ...patch,
  };
}

function dash(cards: Card[] = []): DashState {
  return { cards, waiting: [], still_open: [], history: [], session_panes: {}, repo: "/repo", locks: {}, generated: 1 };
}

let root: Root;
let host: HTMLDivElement;

function render(node: React.ReactNode): HTMLElement {
  act(() => root.render(node));
  return host;
}

beforeEach(() => {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  localStorage.clear();
  store.set({
    state: dash(),
    openKey: null,
    tab2: "info",
    fleet: { filter: "all", sort: "stage", text: "", feed: true, tilesHidden: false, tpm: [] },
  });
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

describe("agents view renderers", () => {
  it("renders orchestrator usage, git, and unknown prices", () => {
    const usage = {
      fill: 0.93,
      context: 930000,
      window: 1000000,
      model: "claude-opus-5-5",
      compactions: 2,
      cost: 12.5,
      tokens: 3000000,
      blowout: true,
    };
    const html = render(
      <OrcCard
        card={card({ usage, tree: { branch: "feat/search", dirty: 4 }, worktree: "/home/u/wt", phase: "Build" })}
      />,
    ).innerHTML;
    expect(html).toContain("card orc st-idle blowout");
    expect(html).toContain('<span class="bad">93%</span>');
    expect(html).toContain("2×");
    expect(html).toContain("$12.50");
    expect(html).toContain("feat/search");
    expect(html).toContain("4 modified");
    expect(html).toContain("worktree");
    expect(html).toContain("orchestrator · claude");
    act(() => root.render(<OrcCard card={card({ usage: { fill: 0.1, cost: null, tokens: 5 } })} />));
    expect(host.innerHTML).toContain("<b>—</b>");
    expect(host.innerHTML).not.toContain("$0");
  });

  it("offers respond and preserves terminal choice", () => {
    const waiting = card({
      now: [{ id: "s1", name: "lead", state: "waiting", need: "answer" }],
      sessions: [{ id: "s1", name: "lead", state: "waiting" }],
    });
    store.set({ state: { ...dash([waiting]), session_panes: { s1: "pane" } } });
    render(<OrcCard card={waiting} />)
      .querySelector<HTMLButtonElement>("[data-respond]")!
      .click();
    expect(store.get().openKey).toBe("k");
    expect(store.get().tab2).toBe("terminal");
  });

  it("uses task tracking for plan progress", () => {
    const task = { title: "Ship search", completed: 2, total: 5, items: [{ status: "in_progress", title: "Index" }] };
    expect(orcPlan(card({ sessions: [{ id: "s1", name: "lead", state: "working", task_tracking: task }] }))).toEqual({
      title: "Ship search · Index",
      done: 2,
      total: 5,
    });
  });

  it("renders sidebar counts and selection", () => {
    const cards = [card({ key: "a", phase: "review" }), card({ key: "b" })];
    store.set({ state: dash(cards), openKey: "b" });
    const html = render(<Orchestrators cards={cards} total={2} />).innerHTML;
    expect(html).toContain("0 running · 1 waiting · 0 stale");
    expect(html).toContain('class="orc-row sel st-idle" data-orc="b"');
  });

  it("colours worker squares and marks failures", () => {
    const runs = ["done", "failed", "running"].map((state, index) => ({
      id: `implement-${index}`,
      mode: "implement",
      unit: `u${index}`,
      state,
      model: "gpt-5.6-sol",
      cause: state === "failed" ? "error: x" : "",
    }));
    const current = [
      {
        id: "s1",
        name: "lead",
        state: "working",
        agents: [{ id: "a1", state: "running", model: "claude-sonnet-5-5", label: "reviewer" }],
      },
    ];
    const html = render(<WorkerSquares card={card({ runs, now: current })} />).innerHTML;
    expect(html.match(/class="sq /g)).toHaveLength(4);
    expect(html).toContain("sq m-gpt failed");
    expect(html).toContain("sq m-sonnet running");
    expect(html).toContain("error: x");
  });

  it("renders summary plans, spend, toggle, and empty squares", () => {
    const state = dash();
    state.totals = { live: 2 };
    state.plan = {
      claude: {
        plan: "team",
        windows: [
          { name: "5 h", pct: 14, resets_at: "" },
          { name: "week", pct: 92, resets_at: "" },
        ],
      },
      codex: {
        plan: "plus",
        windows: [{ name: "week", pct: 100, resets_at: "" }],
        credits: { balance: 59210.4, unlimited: false },
      },
      grok: {
        plan: "xAI",
        spend: [
          { name: "today", cost: 0, tokens: 0 },
          { name: "7 days", cost: 13.12, tokens: 19537829 },
        ],
        last_at: 0,
      },
    };
    store.set({ state });
    const summary = render(<FleetTiles />);
    const html = summary.innerHTML;
    expect(summary.querySelector("#fleet-tiles > #ftiles")).not.toBeNull();
    expect(html).toContain('aria-expanded="true"');
    expect(html).toContain("Claude plan · team");
    expect(html).toContain("on credits · 59,210 left");
    expect(html).toContain("19.5M");
    expect(html).toContain("$13.12");
    expect(html).not.toContain(
      'Grok · xAI</div><div class="plan-row spend"><span>today</span><b>0</b><em>$0.00</em><em>%',
    );
    act(() => host.querySelector<HTMLButtonElement>("#ftiles")!.click());
    expect(host.innerHTML).not.toContain("fleet-tiles");
    expect(host.innerHTML).toContain("Show summary");
    expect(render(<WorkerSquares card={card()} />).innerHTML).toBe("");
  });
});
