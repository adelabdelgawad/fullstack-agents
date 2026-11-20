import { describe, expect, it } from "vitest";
import type { Card } from "../lib/types";
import { taskListHtml, taskProgressHtml } from "./TaskList";

function card(items: any[], counts: Record<string, number>): Card {
  return {
    key: "card",
    updated: 1,
    runs: [],
    now: [],
    needs_you: [],
    phase: "working",
    sessions: [
      {
        id: "lead",
        name: "lead",
        state: "working",
        task_tracking: {
          title: "Plan",
          file: "/r/t.md",
          relative_file: "t.md",
          total: items.length,
          completed: 0,
          counts,
          items,
        },
      },
    ],
  } as unknown as Card;
}

describe("task status tiles show the ledger behind each count on hover", () => {
  it("lists tasks in ledger order, capped at 12, with 'and N more'", () => {
    const items = Array.from({ length: 13 }, (_, i) => ({
      id: `T${i + 1}`,
      status: "pending",
      title: `Task ${i + 1}`,
    }));
    const html = taskListHtml(card(items, { pending: 13 }));
    const expected =
      "Pending (13)\n" + items.slice(0, 12).map((i) => `${i.id}: ${i.title}`).join("\n") + "\nand 1 more";
    expect(html).toContain(`<div class="tt-tile pending" title="${expected}" aria-label="${expected}">`);
  });

  it("keeps '<label> (0)' for an empty status and escapes titles like neighbouring attributes", () => {
    const items = [{ id: "T1", status: "pending", title: 'Fix <script>&"\'' }];
    const html = taskListHtml(card(items, { pending: 1 }));
    expect(html).toContain('title="Blocked (0)" aria-label="Blocked (0)"');
    expect(html).toContain("T1: Fix &lt;script&gt;&amp;&quot;&#39;");
    expect(html).not.toContain("<script>");
  });
});

describe("a row waiting on a live worker reads as waiting, not blocked", () => {
  const items = [{ id: "T1", status: "blocked", display_status: "waiting_worker", title: "Ship it", owner: "lead" }];
  const counts = { in_progress: 1 };

  it("renders the row as in-progress with the 'Waiting on worker' label, not its stored status", () => {
    const html = taskListHtml(card(items, counts));
    expect(html).toContain('<li class="tracked-task in_progress">');
    expect(html).not.toContain('class="tracked-task blocked"');
    expect(html).toContain('<span class="tt-badge in_progress">Waiting on worker</span>');
    const row = html.slice(html.indexOf('<li class="tracked-task'), html.indexOf("</li>"));
    expect(row).not.toContain("Blocked");
  });

  it("lists the row under the in-progress tile, not the blocked tile", () => {
    const html = taskListHtml(card(items, counts));
    expect(html).toContain('<div class="tt-tile in_progress" title="In progress (1)\nT1: Ship it"');
    expect(html).toContain('<div class="tt-tile blocked" title="Blocked (0)"');
  });

  it("renders the stage timeline entry as in-progress, never blocked", () => {
    const html = taskProgressHtml(card(items, counts));
    expect(html).toContain('<li class="in_progress" title="T1: Ship it\nWaiting on worker"');
    expect(html).toContain('aria-label="T1: Ship it\nWaiting on worker"');
    expect(html).not.toContain('<li class="blocked"');
  });
});

describe("timeline item hover", () => {
  it("is two lines: '<id>: <title>' then the status label, matching the aria-label", () => {
    const items = [{ id: "T02", status: "in_progress", title: "Canvas" }];
    const html = taskProgressHtml(card(items, { in_progress: 1 }));
    expect(html).toContain('title="T02: Canvas\nIn progress"');
    expect(html).toContain('aria-label="T02: Canvas\nIn progress"');
  });

  it("items without display_status render exactly as before", () => {
    const items = [{ id: "T1", status: "running", title: "Live" }];
    const html = taskProgressHtml(card(items, { in_progress: 1 }));
    expect(html).toContain('<li class="running" title="T1: Live\nIn progress"');
  });

  it("carries exactly one title= attribute, the <li>'s own, not the icon's", () => {
    const items = [{ id: "T02", status: "in_progress", title: "Canvas" }];
    const html = taskProgressHtml(card(items, { in_progress: 1 }));
    const li = html.slice(html.indexOf('<li class="in_progress"'), html.indexOf("</li>") + 5);
    expect((li.match(/title="/g) || []).length).toBe(1);
    expect(li).toMatch(/^<li class="in_progress" title="T02: Canvas\n/);
  });
});

describe("status count tile hover", () => {
  it("carries exactly one title= attribute, the tile's own, not the icon's", () => {
    const items = [{ id: "T1", status: "pending", title: "Fix it" }];
    const html = taskListHtml(card(items, { pending: 1 }));
    const start = html.indexOf('<div class="tt-tile pending"');
    const tile = html.slice(start, html.indexOf('<div class="tt-tile', start + 1));
    expect((tile.match(/title="/g) || []).length).toBe(1);
  });
});
