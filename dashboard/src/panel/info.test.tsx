// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Card, DashState } from "../lib/types";
import { infoHtml } from "./InfoTab";
import { dismissed, infoOpen } from "./panelLib";

const now = 2_000_000_000;

function fixture(): Card {
  return {
    key: "card",
    title: "Implement search",
    phase: "review",
    updated: 1_700_000_100,
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
        updated: 1_700_000_100,
        workflow_phase: "audit",
        workflow_history: [
          { phase: "implement", timestamp: 1_700_000_000 },
          { phase: "audit", timestamp: 1_700_000_100 },
        ],
      },
    ],
    now: [
      {
        id: "lead",
        engine: "codex",
        updated: 1_700_000_100,
        said_at: 1_700_000_090,
        said: "Search now works.",
        action: "Inspect diff",
        action_running: true,
      },
    ],
    workflow_runs: [],
  } as unknown as Card;
}

function state(card: Card): DashState {
  return {
    cards: [card],
    waiting: [],
    still_open: [],
    history: [],
    session_panes: { lead: "pane-1" },
    repo: "/repo",
    locks: {},
    generated: now,
    activity: [],
  };
}

function render(card: Card, opened: Record<string, boolean> = {}): string {
  infoOpen.set(card.key, new Map(Object.entries(opened)));
  return infoHtml(card, state(card), null);
}

function livePart(card: Card): string {
  const html = render(card);
  return html.slice(html.indexOf('data-info-section="live"'), html.indexOf('data-info-section="summary"'));
}

function dismissFixture(): Card {
  const card = fixture();
  card.runs = [
    { id: "implement-9", unit: "p9", engine: "grok", state: "running", session: "lead", updated: 9e12 },
    { id: "implement-8", unit: "p8", engine: "grok", state: "done", session: "lead", updated: 9e12 },
  ];
  card.now[0].agents = [
    { id: "a1", label: "test-runner · t", state: "completed", at: 1 },
    { id: "b1", label: "shell · Build", state: "completed", at: 2, shell: { description: "Build", command: "make" } },
    { id: "b2", label: "shell · Watch", state: "running", at: 3, shell: { description: "Watch", command: "tail" } },
  ];
  return card;
}

function launcherFixture(): Card {
  const card = fixture();
  card.now[0].name = "omni lead";
  card.runs = [
    {
      id: "implement-20261014-125741-1",
      unit: "p4-api",
      engine: "grok",
      model: "grok-4",
      state: "running",
      session: "lead",
      root: "/wt/p4",
      mode: "implement",
      started: 1,
      updated: 2,
      touched: ["src/a.rs"],
      open_risks: ["needs <db>"],
      desc: "Ship the <p4> API",
    },
  ];
  card.now[0].agents = [
    {
      id: "b9",
      label: "shell · Dispatch P4",
      state: "completed",
      at: 3,
      shell: {
        description: "Dispatch P4",
        command: "cd /wt/p4 && run",
        started: 1,
        exit: 0,
        cwd: "/wt/p4",
        brief: "p4-api",
        run: "implement-20261014-125741-1",
      },
    },
  ];
  return card;
}

describe("information UI Python parity", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(Date, "now").mockReturnValue(now * 1000);
    infoOpen.clear();
    dismissed.clear();
    localStorage.clear();
  });

  it("registered_task_list_shows_counts_source_and_live_statuses", () => {
    const card = fixture();
    card.sessions[0].task_tracking = {
      title: "Canvas work",
      file: "/repo/docs/tasks/canvas.md",
      relative_file: "docs/tasks/canvas.md",
      total: 3,
      completed: 1,
      counts: { done: 1, running: 1, pending: 1 },
      items: [
        { id: "T01", status: "done", title: "Reference", note: "Verified pin" },
        { id: "T02", status: "running", title: "Canvas", note: "Browser pending" },
        { id: "T03", status: "pending", title: "Engine", note: "" },
      ],
    };
    const html = render(card);
    expect(html).toContain('data-info-section="task-list"><summary><h4>Tasks</h4><span class="chip">1/3 done</span>');
    expect(render(card, { "task-list": true })).toContain('data-info-section="task-list" open');
    const tasks = html.slice(html.indexOf('data-info-section="task-list"'));
    expect(tasks).not.toContain("session-task-overview");
    expect(html.slice(0, html.indexOf('data-info-section="task-list"'))).toContain("session-task-overview");
    expect(html.indexOf('data-info-section="runs"')).toBeLessThan(html.indexOf('data-info-section="task-list"'));
    for (const text of [
      "1/3 done",
      "1/3 tasks done",
      'aria-label="Task stage timeline"',
      "T02: Canvas — In progress",
      "0 actively executing · 1 in progress",
      'aria-label="In progress"',
      'aria-label="Pending"',
      "Browser pending",
      'tabindex="0" aria-label="Tasks; scroll for more"',
      "/api/doc?sid=lead&amp;path=",
    ])
      expect(html).toContain(text);
    expect(html.indexOf("session-task-overview")).toBeLessThan(html.indexOf("<h4>Summary"));
    expect(html.indexOf("<b>T02</b>")).toBeLessThan(html.indexOf("<b>T03</b>"));
    expect(html.indexOf("<b>T03</b>")).toBeLessThan(html.indexOf("<b>T01</b>"));
    expect(html.indexOf("<h4>Result")).toBeLessThan(html.indexOf("<h4>Tasks"));
    const tracking = card.sessions[0].task_tracking as { items: Array<{ status: string }> };
    tracking.items[1].status = "done";
    expect(render(card)).toMatch(/task-status-icon done[^>]*role="img"[^>]*aria-label="Done"/);
  });

  it("task_icons_owners_activity_and_expiring_execution_are_separate", () => {
    const card = fixture();
    card.sessions[0].task_tracking = {
      title: "Tasks",
      file: "/repo/TASKS.md",
      relative_file: "TASKS.md",
      total: 3,
      completed: 1,
      counts: { done: 1, in_progress: 2 },
      items: [
        {
          id: "T1",
          status: "in_progress",
          title: "Waiting review",
          owner: "lead",
          activity: "Awaiting audit",
          is_active: false,
        },
        {
          id: "T2",
          status: "in_progress",
          title: "Live implementation",
          owner: "agent:<worker>",
          activity: "Fix <script>draft</script>",
          is_active: true,
          active_until: "2030-01-01T00:00:00Z",
        },
        { id: "T3", status: "done", title: "Complete" },
      ],
    };
    vi.spyOn(Date, "now").mockReturnValue(Date.parse("2026-01-01T00:00:00Z"));
    const html = render(card);
    expect(html).toContain("1 actively executing · 2 in progress");
    expect(html).toContain('aria-label="In progress — actively executing (agent-reported)"');
    expect(html.indexOf("<b>T2</b>")).toBeLessThan(html.indexOf("<b>T1</b>"));
    expect(html).toContain("agent:&lt;worker&gt;");
    expect(html).toContain("Fix &lt;script&gt;draft&lt;/script&gt;");
    expect(html).not.toContain("<script>draft</script>");
    expect(html).not.toMatch(/>in_progress<\/span>|>done<\/span>|>pending<\/span>/);
    vi.spyOn(Date, "now").mockReturnValue(Date.parse("2031-01-01T00:00:00Z"));
    const expired = render(card);
    expect(expired).toContain("0 actively executing · 2 in progress");
    expect(expired).not.toContain("actively executing (agent-reported)");
  });

  it("task_rows_show_id_title_status_badge_and_status_tiles", () => {
    const card = fixture();
    card.sessions[0].task_tracking = {
      title: "Plan",
      file: "/r/t.md",
      relative_file: "t.md",
      total: 2,
      completed: 0,
      counts: { blocked: 1, pending: 1 },
      items: [
        { id: "T1", status: "pending", title: "Later" },
        { id: "T2", status: "blocked", title: "Stuck", owner: "lead" },
      ],
    };
    const html = render(card);
    expect(html).toContain('<li class="tracked-task blocked"');
    expect(html).toContain('<b>T2</b><span class="tt-title">Stuck</span>');
    expect(html).toContain('<span class="tt-badge blocked">Blocked</span>');
    expect(html).toMatch(/tt-tile blocked[\s\S]*?Blocked<\/div><div class="tt-n">1<\/div>/);
    expect(html).toMatch(/tt-tile done[\s\S]*?<div class="tt-n">0<\/div>/);
    expect(html).not.toContain("tt-tile skipped");
    expect(html).toContain("0/2 done</b><span>0%</span>");
  });

  it("v2_progress_verifying_and_step_parent", () => {
    const card = fixture();
    card.sessions[0].task_tracking = {
      format: "v2",
      title: "Plan",
      file: "/r/t.md",
      relative_file: "t.md",
      total: 2,
      completed: 1,
      deliverables: { total: 2, completed: 1 },
      steps: { total: 1, completed: 0 },
      counts: { done: 1, verifying: 1, pending: 1 },
      items: [
        { id: "T1", status: "done", title: "Feature" },
        { id: "S1", status: "verifying", title: "Review", parent: "T1" },
        { id: "T2", status: "pending", title: "Later" },
      ],
    };
    const html = render(card);
    expect(html).toContain("1/2 deliverables done · steps 0/1");
    expect(html).toContain('aria-label="Verifying"');
    expect(html).toMatch(/tt-tile verifying[\s\S]*?Verifying<\/div><div class="tt-n">1<\/div>/);
    expect(html).toContain('Review <span class="s">(step of T1)</span>');
    expect(html).toContain('<span class="chip">1/2 done</span>');
  });

  it("v2_done_deliverable_shows_completion_badges_and_unrecorded_count", () => {
    const card = fixture();
    card.sessions[0].task_tracking = {
      format: "v2",
      title: "Plan",
      file: "/r/t.md",
      relative_file: "t.md",
      total: 3,
      completed: 3,
      deliverables: { total: 3, completed: 3, completion: { evidence: 1, evidence_with_baseline: 1, unrecorded: 1 } },
      steps: { total: 0, completed: 0 },
      counts: { done: 3 },
      items: [
        { id: "T1", status: "done", title: "Clean", completion: "evidence" },
        { id: "T2", status: "done", title: "Flaky", completion: "evidence_with_baseline" },
        { id: "T3", status: "done", title: "Old", completion: "unrecorded" },
      ],
    };
    const html = render(card);
    expect(html).toContain(
      '<span class="tt-badge baseline" title="Completed using an attributed baseline failure">baseline failures</span>',
    );
    expect(html).toContain(
      '<span class="tt-badge unrecorded" title="Marked done before evidence tracking, or upgraded from a legacy ledger">no recorded evidence</span>',
    );
    const t1 = html.slice(html.indexOf("<b>T1</b>"), html.indexOf("<b>T2</b>"));
    expect(t1).not.toContain("tt-badge baseline");
    expect(t1).not.toContain("tt-badge unrecorded");
    expect(html).toContain("3/3 deliverables done · 1 without evidence");
  });

  it("legacy_done_items_never_show_completion_badges_or_suffix", () => {
    const card = fixture();
    card.sessions[0].task_tracking = {
      title: "Canvas work",
      file: "/repo/docs/tasks/canvas.md",
      relative_file: "docs/tasks/canvas.md",
      total: 1,
      completed: 1,
      counts: { done: 1 },
      items: [{ id: "T01", status: "done", title: "Reference", note: "Verified pin" }],
    };
    const html = render(card);
    expect(html).not.toContain("tt-badge unrecorded");
    expect(html).not.toContain("tt-badge baseline");
    expect(html).not.toContain("without evidence");
    expect(html).toContain("1/1 tasks done");
  });

  it("task_list_escapes_untrusted_content_and_reports_bound_errors", () => {
    const card = fixture();
    card.sessions[0].task_tracking = { error: "Missing <script>alert(1)</script>" };
    const html = render(card);
    expect(html).toContain('role="alert"');
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).not.toContain("0/0 done");
  });

  it("unregistered_session_does_not_show_fabricated_task_progress", () => {
    expect(render(fixture())).not.toContain('data-info-section="task-list"');
  });

  it("lead_and_real_auditor_are_distinct", () => {
    const card = fixture();
    card.workflow_runs = [
      {
        role: "auditor",
        engine: "claude",
        model: "opus",
        state: "completed",
        verdict: "CHANGES",
        run_id: "audit-1",
        updated: 1_700_000_200,
        summary: "Fix escaping",
      },
    ];
    const html = render(card);
    for (const text of ["Codex · configured-codex", "Claude · opus", "completed · CHANGES", "<dd>working</dd>"])
      expect(html).toContain(text);
    expect(html).not.toContain("<dd>done</dd>");
  });

  it("progress_and_neutral_absence_of_runs", () => {
    const html = render(fixture());
    expect(html).toContain("No run records available.");
    expect(html).not.toContain("no code has been handed");
    expect(html).toContain("<dd>audit</dd>");
    expect(html).toMatch(/<b>implement<\/b> <time>[^<]+<\/time>/);
    expect(html).toContain("Running now</b> Inspect diff");
    expect(html.indexOf("<h4>Summary")).toBeLessThan(html.indexOf("<h4>Progress"));
    expect(html.indexOf("<h4>Progress")).toBeLessThan(html.indexOf("<h4>Result"));
  });

  it("disclosures_default_closed_and_restore_per_card", () => {
    const card = fixture();
    const html = render(card);
    for (const key of ["session", "runs", "message"]) expect(html).toContain(`data-info-section="${key}"><summary>`);
    const restored = render(card, { session: true });
    expect(restored).toContain('data-info-section="session" open>');
    expect(restored).toContain('data-info-section="runs"><summary>');
    const other = fixture();
    other.key = "other";
    expect(render(other)).toContain('data-info-section="session"><summary>');
  });

  it("top_sections_default_closed_live_open_and_restore_per_card", () => {
    const card = fixture();
    const html = render(card);
    expect(html).toContain('data-info-section="live" open><summary><h4>Running now');
    for (const key of ["summary", "progress", "result"])
      expect(html).toContain(`data-info-section="${key}"><summary><h4>`);
    const restored = render(card, { result: true, live: false });
    expect(restored).toContain('data-info-section="result" open><summary><h4>Result');
    expect(restored).toContain('data-info-section="live"><summary><h4>Running now');
    expect(restored).toContain('data-info-section="summary"><summary>');
  });

  it("overview_strip_leads_with_state_counts_and_needs", () => {
    const card = fixture();
    card.needs_you = ["stalled", "stalled"];
    card.runs = [{ id: "implement-1", unit: "p1", state: "running" }];
    card.sessions[0].task_tracking = {
      title: "T",
      file: "/r/t.md",
      relative_file: "t.md",
      total: 4,
      completed: 1,
      counts: { done: 1 },
      items: [],
    };
    const html = render(card);
    const strip = html.slice(html.indexOf('class="session-overview"'), html.indexOf('data-info-section="live"'));
    for (const text of [
      '<span class="pill live">working</span>',
      '<span class="pill bad">1 needs you</span>',
      'Tasks done</div><div class="so-v">1/4</div>',
      'Running now</div><div class="so-v">1</div>',
      'style="width:25%"',
    ])
      expect(strip).toContain(text);
    expect(html.indexOf("session-overview")).toBeLessThan(html.indexOf("session-task-overview"));
    expect(html.indexOf("session-task-overview")).toBeLessThan(html.indexOf('data-info-section="live"'));
    expect(html.indexOf("session-task-overview")).toBeLessThan(html.indexOf('data-info-section="summary"'));
    expect(html.match(/aria-label="Task stage timeline"/g)?.length).toEqual(1);
  });

  it("v2_session_state_shows_label_and_escaped_blockers", () => {
    const card = fixture();
    card.sessions[0].task_tracking = {
      format: "v2",
      title: "Plan",
      file: "/r/t.md",
      relative_file: "t.md",
      total: 2,
      completed: 0,
      deliverables: { total: 2, completed: 0 },
      steps: { total: 0, completed: 0 },
      counts: { blocked: 2 },
      items: [
        { id: "S3", status: "blocked", title: "Client" },
        { id: "S4", status: "blocked", title: "Server" },
      ],
      session_state: {
        state: "waiting_user",
        executable: [],
        workers: [],
        questions: [
          { id: "Q1", text: "Use REST or <b>GraphQL</b>?", why: "blocks the client work", rows: ["S3", "S4"] },
        ],
        external: [
          { id: "B1", class: "capacity", engine: "codex", until: "2026-10-21T18:00:00Z", text: "", rows: ["S4"] },
        ],
      },
    };
    const html = render(card);
    expect(html).toContain('<div class="task-state"><span class="pill">Waiting on you</span></div>');
    expect(html).toContain(
      "<li>Q1: Use REST or &lt;b&gt;GraphQL&lt;/b&gt;? — blocks S3, S4: blocks the client work</li>",
    );
    expect(html).toContain("<li>waiting for codex capacity until 2026-10-21T18:00:00Z</li>");
    expect(html).not.toContain("<b>GraphQL</b>");
  });

  it("legacy_and_sessionless_v2_ledgers_render_without_state_label", () => {
    const card = fixture();
    card.sessions[0].task_tracking = {
      title: "Canvas work",
      file: "/repo/docs/tasks/canvas.md",
      relative_file: "docs/tasks/canvas.md",
      total: 1,
      completed: 0,
      counts: { pending: 1 },
      items: [{ id: "T01", status: "pending", title: "Reference" }],
    };
    expect(render(card)).not.toContain("task-state");
    const card2 = fixture();
    card2.sessions[0].task_tracking = {
      format: "v2",
      title: "Plan",
      file: "/r/t.md",
      relative_file: "t.md",
      total: 1,
      completed: 0,
      deliverables: { total: 1, completed: 0 },
      steps: { total: 0, completed: 0 },
      counts: { pending: 1 },
      items: [{ id: "T1", status: "pending", title: "Later" }],
    };
    expect(render(card2)).not.toContain("task-state");
  });

  it("running_now_separates_runs_subagents_and_shells", () => {
    const card = fixture();
    card.runs = [
      { id: "implement-1", unit: "p1-api", engine: "grok", model: "grok-4", state: "running" },
      { id: "implement-0", unit: "p0-old", engine: "grok", state: "done" },
    ];
    card.now[0].agents = [
      { id: "a1", label: "test-runner · run <tests>", state: "running", at: 2 },
      { id: "b1", label: "shell · Dispatch P1 with Grok", state: "running", at: 3 },
      { id: "b2", label: "shell · b2", state: "completed", at: 1 },
    ];
    const live = livePart(card);
    expect(live).toContain('<span class="chip">3 running</span>');
    expect(live).toContain('data-open-run="implement-1"');
    expect(live).not.toContain("implement-0");
    expect(live.indexOf("<h5>Subagents")).toBeLessThan(live.indexOf('data-agent="a1"'));
    expect(live.indexOf("<h5>Background shells")).toBeLessThan(live.indexOf('data-agent="b1"'));
    expect(live).toContain("1 running · 1 recent");
    expect(live).toContain("run &lt;tests&gt;");
    expect(live).not.toContain("<tests>");
  });

  it("run_card_absorbs_its_launcher_shell", () => {
    const live = livePart(launcherFixture());
    for (const text of [
      '<b class="ls-title" title="Ship the &lt;p4&gt; API">Ship the &lt;p4&gt; API</b>',
      "<b>p4-api</b>",
      "<dt>Target</dt><dd>/wt/p4</dd>",
      "<dt>Brief</dt><dd>p4-api</dd>",
      "<dt>Agent</dt><dd>grok · grok-4</dd>",
      "<dt>Launched by</dt><dd>Dispatch P4 · b9 · completed · exit 0</dd>",
      'data-asid="lead" data-agent="implement-20261014-125741-1"',
      'data-open-run="implement-20261014-125741-1">Panel',
      "1 file<",
      "1 risk<",
      "Files touched (1)",
      "needs &lt;db&gt;",
    ])
      expect(live).toContain(text);
    expect(live).not.toContain('data-agent="b9"');
    expect(live).not.toContain("<dt>Session</dt>");
    expect(live).not.toContain("<db>");
  });

  it("unlinked_shell_card_names_session_target_and_console", () => {
    const card = fixture();
    card.now[0].name = "omni lead";
    card.now[0].agents = [
      {
        id: "b7",
        label: "shell · Commit",
        state: "running",
        at: 3,
        shell: {
          description: "Commit",
          command: "git commit -m <x>",
          started: 1,
          exit: null,
          cwd: "/wt/p7",
          brief: "",
          run: "",
          moved: true,
        },
      },
    ];
    const live = render(card);
    for (const text of [
      '<b class="ls-title" title="Commit">Commit</b>',
      "<dt>Target</dt><dd>/wt/p7</dd>",
      "<dt>Agent</dt><dd>none</dd>",
      "started in the foreground",
      'data-asid="lead" data-agent="b7"',
      "git commit -m &lt;x&gt;",
    ])
      expect(live).toContain(text);
  });

  it("run_card_offers_git_changes_only_with_a_worktree", () => {
    const card = fixture();
    card.runs = [
      { id: "implement-5", unit: "p5", engine: "grok", state: "running", session: "lead", root: "/wt/p5" },
      { id: "implement-6", unit: "p6", engine: "grok", state: "running", session: "lead" },
    ];
    const live = render(card);
    expect(live).toContain('data-asid="lead" data-run-changes="implement-5" aria-haspopup="dialog">Git changes');
    expect(live).not.toContain('data-run-changes="implement-6"');
  });

  it("done_items_get_dismiss_and_running_items_do_not", () => {
    const live = render(dismissFixture());
    for (const id of ["implement-8", "a1", "b1"]) expect(live).toContain(`data-dismiss="${id}"`);
    for (const id of ["implement-9", "b2"]) expect(live).not.toContain(`data-dismiss="${id}"`);
    expect(live).toContain('data-dismiss-all="1">Dismiss all done (3)');
  });

  it("dismissed_done_items_are_hidden_but_running_ones_stay", () => {
    for (const id of ["implement-8", "a1", "b1", "b2", "implement-9"]) dismissed.add(id);
    const live = livePart(dismissFixture());
    for (const text of ['data-agent="implement-8"', 'data-agent="a1"', 'data-agent="b1"', "data-dismiss-all"])
      expect(live).not.toContain(text);
    for (const text of ['data-agent="implement-9"', 'data-agent="b2"']) expect(live).toContain(text);
  });

  it("workflow_runs_are_cards_and_hide_their_duplicate_agents", () => {
    const card = fixture();
    card.workflow_runs = [
      {
        run_id: "fsa-audit-1",
        role: "auditor",
        engine: "claude",
        model: "opus",
        state: "completed",
        verdict: "CHANGES",
        root: "/wt/dev",
        summary: "Fix the <race>",
        updated: 9e12,
        started: 1,
      },
    ];
    card.now[0].agents = [
      { id: "fsa-audit-1", label: "claude · auditor · opus", state: "completed", at: 2 },
      { id: "kid", label: "codex · Harvey", state: "running", at: 3, task: "chatbot readiness" },
    ];
    const live = livePart(card);
    expect(live).toContain("<h5>Workflow runs");
    expect(live).toContain('title="Fix the &lt;race&gt;">Fix the &lt;race&gt;</b>');
    expect(live).toContain('<span class="pill warn">CHANGES</span>');
    expect(live).not.toContain('data-agent="fsa-audit-1"');
    expect(live).toContain('title="chatbot readiness">chatbot readiness</b>');
    expect(live).toContain("<b>Harvey</b>");
    expect(live).not.toContain("<h5>Implementer runs");
  });

  it("agent_text_and_title_are_escaped", () => {
    const card = fixture();
    card.title = "<img src=x onerror=alert(1)>";
    card.now[0].said = '<script>alert("x")</script>';
    const html = render(card);
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;script&gt;");
    expect(html).toContain("&lt;img");
    expect(html).toContain("Full message from Codex");
  });

  it("historical_claude_and_recorded_checks", () => {
    const card = fixture();
    card.sessions[0].engine = "claude";
    card.sessions[0].model = null;
    card.now[0].engine = "claude";
    card.chips = [{ kind: "tests", verdict: "PASS", label: "unit checks" }];
    const html = render(card);
    for (const text of [
      "<dd>Claude</dd>",
      "Full message from Claude",
      "Worker-reported checks</b> PASS · unit checks",
      "No registered audit result.",
    ])
      expect(html).toContain(text);
    expect(html).not.toContain("opus");
  });

  it("lead_evidence_is_escaped_and_preferred", () => {
    const card = fixture();
    card.sessions[0].workflow_checks = ["<script>check</script>"];
    card.sessions[0].workflow_summary = "<img>Result";
    card.sessions[0].workflow_auditor = "sonnet";
    card.chips = [{ kind: "tests", verdict: "PASS" }];
    const html = render(card);
    for (const text of [
      "Lead-reported checks",
      "Worker-reported checks",
      "&lt;script&gt;check&lt;/script&gt;",
      "&lt;img&gt;Result",
      "sonnet (selected; no audit recorded)",
    ])
      expect(html).toContain(text);
    expect(html).not.toContain("Search now works.");
    expect(html).not.toContain("opus");
    expect(render(fixture())).not.toContain("configured; no audit");
    expect(render(fixture())).toContain("No audit recorded");
  });

  it("old_events_are_collapsed_and_disclosure_is_restored", () => {
    const card = fixture();
    card.sessions[0].workflow_history = Array.from({ length: 12 }, (_, index) => ({
      phase: `event-${index}`,
      timestamp: 1_700_000_000 + index,
    }));
    const html = render(card);
    expect(html).toContain('data-info-section="history"><summary>');
    expect(html.match(/<li><b>event-/g)?.length).toEqual(12);
    const [recent, older] = html.split('data-info-section="history"', 2);
    expect(recent).not.toContain("<b>event-0</b>");
    expect(recent).toContain("<b>event-4</b>");
    expect(older).toContain("<b>event-0</b>");
    expect(render(card, { history: true })).toContain('data-info-section="history" open>');
  });

  it("blocked_and_incomplete_audit_do_not_claim_pass", () => {
    const card = fixture();
    card.sessions[0].state = "waiting";
    card.now[0].need = "Choose a search scope";
    card.workflow_runs = [
      { role: "auditor", engine: "claude", model: "opus", state: "incomplete", run_id: "a1", updated: 1_700_000_200 },
    ];
    const html = render(card);
    expect(html).toContain("<dd>blocked</dd>");
    expect(html).toContain("incomplete · no verdict recorded");
    expect(html).toContain("Choose a search scope");
    expect(html).not.toContain("PASS");
  });
});
