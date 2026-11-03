import { describe, expect, it, vi } from "vitest";
import { flushTerminalScroll, liveTerminalClosed, queueTerminalScroll, type ScrollState } from "./liveTerminal";

const current = (): ScrollState => ({ session: "s1", scrollLines: 0, scrollFrame: 0, scrollSending: false });

describe("terminal scroll queue", () => {
  it("coalesces bursts and sends one request at a time", async () => {
    const state = current();
    const releases: Array<() => void> = [];
    const posts: unknown[] = [];
    const post = (_state: ScrollState, body: unknown) =>
      new Promise<void>((resolve) => (posts.push(body), releases.push(resolve)));
    for (let index = 0; index < 30; index++) queueTerminalScroll(state, -1, () => 1);
    flushTerminalScroll(state, post);
    for (let index = 0; index < 20; index++) queueTerminalScroll(state, -1, () => 1);
    flushTerminalScroll(state, post);
    expect(posts).toHaveLength(1);
    releases.shift()?.();
    await Promise.resolve();
    expect(posts).toEqual([
      { type: "scroll", direction: "up", lines: 30 },
      { type: "scroll", direction: "up", lines: 20 },
    ]);
  });

  it("cancels opposite directions, caps requests, and drops unconnected input", () => {
    const state = current();
    const posts: unknown[] = [];
    const post = (_state: ScrollState, body: unknown) => (posts.push(body), Promise.resolve());
    queueTerminalScroll(state, 5, () => 1);
    queueTerminalScroll(state, -5, () => 1);
    flushTerminalScroll(state, post);
    expect(posts).toEqual([]);
    state.session = "";
    queueTerminalScroll(state, 3, () => 1);
    flushTerminalScroll(state, post);
    expect(state.scrollLines).toBe(0);
  });

  it("caps each server request at 100 lines", async () => {
    const state = current();
    const posts: Array<{ lines: number }> = [];
    const post = (_state: ScrollState, body: unknown) => (posts.push(body as { lines: number }), Promise.resolve());
    state.scrollLines = 250;
    flushTerminalScroll(state, post);
    await Promise.resolve();
    await Promise.resolve();
    expect(posts.map(({ lines }) => lines)).toEqual([100, 100, 50]);
  });
});

describe("terminal reconnect", () => {
  it("backs off indefinitely and keeps ownership conflicts terminal", () => {
    const delays: number[] = [];
    const status = vi.fn();
    const state = { retries: 0, reconnectTimer: null as ReturnType<typeof setTimeout> | null };
    for (let index = 0; index < 6; index++)
      liveTerminalClosed(state, "Connection closed", status, (_fn, delay) => (delays.push(delay ?? 0), 1 as never));
    expect(delays).toEqual([1000, 2000, 4000, 8000, 10000, 10000]);
    expect(status).toHaveBeenCalledTimes(3);
    liveTerminalClosed(
      state,
      "pane already has an attached client",
      status,
      (_fn, delay) => (delays.push(delay ?? 0), 1 as never),
    );
    expect(delays).toHaveLength(6);
    expect(status).toHaveBeenLastCalledWith("pane already has an attached client");
  });
});
