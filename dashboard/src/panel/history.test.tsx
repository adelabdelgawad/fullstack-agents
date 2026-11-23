// @vitest-environment jsdom
import { act } from "react-dom/test-utils";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Card } from "../lib/types";
import { HistoryTab, type SessionHistory } from "./HistoryTab";

const now = 2_000_000_000;
const card: Card = {
  key: "k",
  title: "Search",
  updated: now,
  runs: [],
  now: [],
  sessions: [{ id: "lead-1", name: "lead", state: "working" }],
  usage: { fill: 0.42 },
  needs_you: [],
  steps: [],
} as unknown as Card;

const payload: SessionHistory = {
  turns: [
    {
      prompt: "Fix the login page",
      model: "claude-opus-5-5",
      state: "answered",
      tokens: 2200,
      cost: 0.012,
      fill: 0.1,
      compactions: 0,
      started: now - 600,
      updated: now - 540,
    },
    {
      prompt: "Long refactor",
      model: "claude-opus-5-5",
      state: "interrupted",
      tokens: 5000,
      cost: 0.03,
      fill: 0.3,
      compactions: 1,
      started: now - 300,
      updated: now - 120,
    },
  ],
  totals: { turns: 2, tokens: 7200, cost: 0.042, compactions: 1, interrupted: 1 },
};

let root: Root;
let host: HTMLDivElement;

beforeEach(() => {
  vi.spyOn(Date, "now").mockReturnValue(now * 1000);
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.restoreAllMocks();
});

async function renderWith(response: Promise<Response>): Promise<ReturnType<typeof vi.fn>> {
  const fetchMock = vi.fn(() => response);
  vi.stubGlobal("fetch", fetchMock);
  await act(async () => {
    root.render(<HistoryTab card={card} />);
    await Promise.resolve();
  });
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
  return fetchMock;
}

describe("session History tab", () => {
  it("asks for this session's history and renders totals and one row per prompt, newest first", async () => {
    const fetchMock = await renderWith(Promise.resolve(new Response(JSON.stringify(payload))));
    expect(fetchMock.mock.calls[0][0]).toBe("/api/session-history?sid=lead-1");
    const tiles = [...host.querySelectorAll(".so-tile")].map((t) => t.textContent);
    expect(tiles).toContain("Prompts2");
    expect(tiles).toContain("Context now42%");
    expect(tiles).toContain("Interrupted1");
    const rows = [...host.querySelectorAll(".history tbody tr")];
    expect(rows.map((r) => r.querySelector("td")?.textContent)).toEqual(["Long refactor", "Fix the login page"]);
    expect(rows[0].textContent).toContain("interrupted");
    expect(rows[1].querySelector("td:last-child")?.getAttribute("title")).toBe("took 1 min");
    expect(host.querySelectorAll(".history th")).toHaveLength(8);
  });

  it("says so when the server cannot read the session", async () => {
    await renderWith(Promise.resolve(new Response("unknown session", { status: 404 })));
    expect(host.textContent).toContain("History is not available");
  });
});

describe("History list", () => {
  it("opens a finished session's prompts under its row when it has no live card", async () => {
    const { store } = await import("../store");
    const { HistoryView } = await import("../views/HistoryView");
    const fetchMock = vi.fn((_url: string) => Promise.resolve(new Response(JSON.stringify(payload))));
    vi.stubGlobal("fetch", fetchMock);
    store.set({
      state: {
        cards: [],
        history: [
          {
            id: "done-1",
            name: "ivr-resource-model-handoff",
            model: "claude-opus-5-5",
            state: "quiet",
            branch: "dev",
            tokens: 1,
            cost: 1,
            fill: 0.2,
            compactions: 0,
            updated: now,
          },
        ],
      },
    } as never);
    await act(async () => {
      root.render(<HistoryView />);
      await Promise.resolve();
    });
    const row = host.querySelector('tr[data-hsid="done-1"]') as HTMLElement;
    await act(async () => {
      row.click();
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(row.getAttribute("aria-expanded")).toBe("true");
    expect(fetchMock.mock.calls.some((call) => String(call[0]) === "/api/session-history?sid=done-1")).toBe(true);
    expect(host.querySelector(".history-turns")?.textContent).toContain("Fix the login page");
  });
});
