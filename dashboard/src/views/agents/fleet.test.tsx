// @vitest-environment jsdom
import { act } from "react-dom/test-utils";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fleetCompare, fleetMatches } from "../../lib/cards";
import type { Card, DashState } from "../../lib/types";
import { store } from "../../store";
import { FleetTiles } from "./FleetTiles";
import { OrcCard } from "./OrcCard";
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

function renderPlan(plan: Record<string, unknown>): string {
  const state = dash();
  state.plan = plan;
  store.set({ state });
  return render(<FleetTiles />).innerHTML;
}

describe("fleet UI Python parity", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(Date, "now").mockReturnValue(2_000_000_000_000);
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

  it("orchestrator_card_shows_context_compactions_cost_and_git", () => {
    const usage = {
      fill: 0.93,
      context: 930_000,
      window: 1_000_000,
      model: "claude-opus-5-5",
      compactions: 2,
      cost: 12.5,
      tokens: 3_000_000,
      blowout: true,
    };
    const html = render(
      <OrcCard
        card={card({ usage, tree: { branch: "feat/search", dirty: 4 }, worktree: "/home/u/wt", phase: "Build" })}
      />,
    ).innerHTML;
    for (const text of [
      "orc st-idle blowout",
      '<span class="bad">93%</span>',
      ">2×<",
      "$12.50",
      "feat/search",
      "4 modified",
      ">worktree<",
      "orchestrator · claude",
    ])
      expect(html).toContain(text);
  });

  it("waiting_orchestrator_offers_respond", () => {
    const waiting = card({
      needs_you: ["stalled"],
      sessions: [{ id: "s1", name: "lead", state: "waiting", branch: "main" }],
      now: [{ id: "s1", name: "lead", state: "waiting" }],
    });
    const html = render(<OrcCard card={waiting} />).innerHTML;
    expect(html).toContain("Waiting · needs you");
    expect(html).toContain('data-respond="k"');
  });

  it("unknown_price_renders_dash_not_zero", () => {
    const usage = { fill: 0.1, context: 1, window: 10, model: "gpt-x", compactions: 0, cost: null, tokens: 5 };
    const html = render(<OrcCard card={card({ usage })} />).innerHTML;
    expect(html).toContain("<b>—</b>");
    expect(html).not.toContain("$0");
  });

  it("plan_progress_comes_from_task_file", () => {
    const task = { title: "Ship search", completed: 2, total: 5, items: [{ status: "in_progress", title: "Index" }] };
    const html = render(
      <OrcCard card={card({ sessions: [{ id: "s1", name: "lead", state: "working", task_tracking: task }] })} />,
    ).innerHTML;
    expect(html).toContain("Ship search · Index");
    expect(html).toContain("<b>2/5</b>");
  });

  it("sidebar_counts_and_selection", () => {
    const cards = [card({ key: "a", phase: "review" }), card({ key: "b" })];
    store.set({ state: dash(cards), openKey: "b" });
    const html = render(<Orchestrators cards={cards} total={2} />).innerHTML;
    expect(html).toContain("0 running · 1 waiting · 0 stale");
    expect(host.querySelector('[data-orc="b"]')?.getAttribute("aria-current")).toBe("true");
  });

  it("squares_colour_by_model_and_mark_failures", () => {
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
    expect(html.match(/class="sq /g)?.length).toEqual(4);
    expect(html).toContain("sq m-gpt failed");
    expect(html).toContain("sq m-sonnet running");
    expect(html).toContain("error: x");
  });

  it("plan_tile_shows_each_window_and_warns_when_high", () => {
    let html = renderPlan({
      claude: {
        plan: "team",
        windows: [
          { name: "5 h", pct: 14, resets_at: "" },
          { name: "week", pct: 92, resets_at: "" },
        ],
      },
    });
    expect(html).toContain("ft plan bad");
    expect(html).toContain("<b>14%</b>");
    expect(html).toContain("<b>92%</b>");
    expect(html).toContain("Claude team");
    html = renderPlan({ claude: { error: "no Claude login found" } });
    expect(html).toContain("no Claude login");
    html = renderPlan({
      codex: {
        plan: "plus",
        windows: [{ name: "week", pct: 100, resets_at: "" }],
        credits: { balance: 59210.4, unlimited: false },
      },
    });
    expect(html).toContain("plan-credits on");
    expect(html).toContain("on credits · 59,210 left");
    html = renderPlan({ claude: { plan: "team", windows: [{ name: "5 h", pct: null, resets_at: "" }] } });
    expect(html).toContain("<b>—</b>");
  });

  it("shows the remaining Codex balance on the first line", () => {
    renderPlan({
      codex: {
        plan: "plus",
        windows: [{ name: "week", pct: 80, resets_at: "" }],
        credits: { balance: 59210, unlimited: false },
      },
    });
    const balance = host.querySelector(".ft.plan .usage-frame > .ft-l .credit-balance");
    expect(balance?.textContent).toBe("59k left");
    expect(balance?.getAttribute("aria-label")).toBe("Remaining credits: 59,210");
  });

  it("grok_tile_shows_spend_without_percentages", () => {
    renderPlan({
      grok: {
        plan: "xAI",
        spend: [
          { name: "today", cost: 0, tokens: 0 },
          { name: "7 days", cost: 13.12, tokens: 19_537_829 },
        ],
        last_at: 0,
      },
    });
    const grokTile = [...host.querySelectorAll<HTMLElement>(".ft.plan")].find(
      (tile) => tile.querySelector(".ft-l")?.textContent === "Grok · xAI",
    );
    const html = grokTile?.outerHTML ?? "";
    expect(html).toContain("Grok · xAI");
    expect(html).toContain("19.5M");
    expect(html).toContain("$13.12");
    expect(html).toContain('href="https://grok.com" target="_blank" rel="noopener noreferrer"');
    expect(grokTile?.textContent).not.toContain("%");
  });

  it("summary_cards_collapse_behind_a_toggle_at_the_strip_end", () => {
    const state = dash();
    state.totals = { live: 2 };
    store.set({ state });
    let html = render(<Orchestrators cards={[]} total={0} />).innerHTML;
    expect(html).toContain('id="fleet-tiles"');
    expect(host.querySelector(".fleet-toolbar > #ftiles:last-child")).not.toBeNull();
    expect(html).toContain('aria-expanded="true" aria-controls="fleet-tiles"');
    expect(html).toContain("Hide summary");
    act(() => host.querySelector<HTMLButtonElement>("#ftiles")!.click());
    html = host.innerHTML;
    expect(html).not.toContain("fleet-tiles");
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain("Show summary");
  });

  it("squares_empty_without_workers", () => {
    expect(render(<WorkerSquares card={card()} />).innerHTML).toEqual("");
  });

  it("filters_select_blowouts_and_text", () => {
    const hot = card({ key: "hot", usage: { blowout: true, model: "claude-opus-5-5" } });
    const cold = card({ key: "cold", title: "Other", usage: { blowout: false, model: "x" } });
    expect(
      [hot, cold]
        .filter((value) => fleetMatches(value, { filter: "blowouts", sort: "stage", text: "" }))
        .map(({ key }) => key),
    ).toEqual(["hot"]);
    expect(
      [hot, cold]
        .filter((value) => fleetMatches(value, { filter: "all", sort: "stage", text: "oth" }))
        .map(({ key }) => key),
    ).toEqual(["cold"]);
  });

  it("cost_sort_puts_most_expensive_first", () => {
    const cards = [card({ key: "a", usage: { cost: 1 } }), card({ key: "b", usage: { cost: 9 } }), card({ key: "c" })];
    expect(
      cards.sort((a, b) => fleetCompare(a, b, { filter: "all", text: "", sort: "cost" })).map(({ key }) => key),
    ).toEqual(["b", "a", "c"]);
  });
});
