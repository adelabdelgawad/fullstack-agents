// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Card, DashState } from "../lib/types";
import { infoHtml } from "./InfoTab";
import { dismissed, infoOpen } from "./panelLib";

const now = 2_000_000_000;
const state = (card: Card): DashState => ({
  cards: [card],
  waiting: [],
  still_open: [],
  history: [],
  session_panes: { lead: "pane-1" },
  repo: "/repo",
  locks: {},
  generated: now,
  activity: [],
});
const fixture = (): Card => ({
  key: "card",
  title: "Implement search",
  phase: "review",
  updated: now,
  runs: [],
  steps: [],
  needs_you: [],
  sessions: [
    {
      id: "lead",
      name: "Implement search",
      engine: "codex",
      model: "configured-codex",
      state: "working",
      updated: now,
      workflow_phase: "audit",
    },
  ],
  now: [
    {
      id: "lead",
      name: "Implement search",
      engine: "codex",
      state: "working",
      updated: now,
      said: "Search now works.",
    },
  ],
  usage: null,
});

describe("information panel", () => {
  beforeEach(() => {
    vi.spyOn(Date, "now").mockReturnValue(now * 1000);
    infoOpen.clear();
    dismissed.clear();
    localStorage.clear();
  });

  it("renders task statuses, badges, overview, and session state", () => {
    const card = fixture();
    card.sessions[0].task_tracking = {
      format: "v2",
      title: "Plan",
      file: "/r/t.md",
      relative_file: "t.md",
      total: 2,
      completed: 1,
      deliverables: { completion: { unrecorded: 1 } },
      steps: { total: 1, completed: 0 },
      counts: { done: 1, verifying: 1 },
      items: [
        { id: "S1", status: "verifying", title: "Review", parent: "T1" },
        { id: "T1", status: "done", title: "Feature", completion: "unrecorded" },
      ],
      session_state: {
        state: "waiting_user",
        questions: [{ id: "Q1", text: "Use <REST>?", why: "blocks work", rows: ["S1"] }],
        workers: [],
        external: [],
      },
    };
    const html = infoHtml(card, state(card), null);
    expect(html).toContain('aria-label="Session overview"');
    expect(html).toContain('data-info-section="task-list"');
    expect(html).toContain("1/2 deliverables done · steps 0/1 · 1 without evidence");
    expect(html).toContain("Waiting on you");
    expect(html).toContain("Use &lt;REST&gt;?");
  });

  it("restores disclosures per card", () => {
    const card = fixture();
    infoOpen.set(
      card.key,
      new Map([
        ["result", true],
        ["live", false],
      ]),
    );
    const html = infoHtml(card, state(card), null);
    expect(html).toContain('data-info-section="result" open');
    expect(html).toContain('data-info-section="live"><summary');
  });

  it("separates current runs, agents, and shells and absorbs launchers", () => {
    const card = fixture();
    card.runs = [{ id: "implement-1", unit: "p1", state: "running", session: "lead", root: "/wt/p1", updated: now }];
    card.now[0].agents = [
      {
        id: "launch",
        label: "shell · Dispatch",
        state: "completed",
        at: now,
        shell: { run: "implement-1", description: "Dispatch" },
      },
      { id: "agent", label: "test-runner · tests", state: "running", at: now },
    ];
    const html = infoHtml(card, state(card), null);
    expect(html).toContain("Implementer runs");
    expect(html).toContain("Subagents");
    expect(html).toContain("via launch");
    expect(html).not.toContain('data-agent="launch"');
  });

  it("hides dismissed done items but retains running items", () => {
    const card = fixture();
    card.now[0].agents = [
      { id: "done", label: "test-runner · done", state: "completed", at: now },
      { id: "live", label: "test-runner · live", state: "running", at: now },
    ];
    dismissed.add("done");
    dismissed.add("live");
    const html = infoHtml(card, state(card), null);
    expect(html).not.toContain('data-agent="done"');
    expect(html).toContain('data-agent="live"');
  });
});
