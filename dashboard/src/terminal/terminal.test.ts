import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushTerminalScroll, liveTerminalClosed, queueTerminalScroll, type ScrollState } from "./liveTerminal";

const current = (): ScrollState => ({ session: "s1", scrollLines: 0, scrollFrame: 0, scrollSending: false });

describe("terminal Python parity", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("burst_of_wheel_ticks_becomes_one_request_then_the_remainder", async () => {
    const state = current();
    const releases: Array<() => void> = [];
    const posts: unknown[] = [];
    const post = (_state: ScrollState, body: unknown) =>
      new Promise<void>((resolve) => (posts.push(body), releases.push(resolve)));
    for (let index = 0; index < 30; index++) queueTerminalScroll(state, -1, () => 1);
    flushTerminalScroll(state, post);
    for (let index = 0; index < 20; index++) queueTerminalScroll(state, -1, () => 1);
    flushTerminalScroll(state, post);
    expect(posts.length).toEqual(1);
    releases.shift()?.();
    await Promise.resolve();
    expect(posts).toEqual([
      { type: "scroll", direction: "up", lines: 30 },
      { type: "scroll", direction: "up", lines: 20 },
    ]);
    releases.shift()?.();
    await Promise.resolve();
    expect(state.scrollLines).toEqual(0);
  });

  it("opposite_directions_cancel_and_large_totals_respect_server_cap", async () => {
    const state = current();
    const posts: Array<{ direction: string; lines: number }> = [];
    const post = (_state: ScrollState, body: unknown) => (
      posts.push(body as { direction: string; lines: number }), Promise.resolve()
    );
    queueTerminalScroll(state, 5, () => 1);
    queueTerminalScroll(state, -5, () => 1);
    flushTerminalScroll(state, post);
    expect(posts.length).toEqual(0);
    queueTerminalScroll(state, 250, () => 1);
    flushTerminalScroll(state, post);
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    expect(posts.map(({ lines }) => lines)).toEqual([100, 100, 50]);
    expect(posts.every(({ direction }) => direction === "down")).toEqual(true);
  });

  it("unconnected_terminal_drops_queued_scroll", () => {
    const state = current();
    state.session = "";
    const posts: unknown[] = [];
    queueTerminalScroll(state, 3, () => 1);
    flushTerminalScroll(state, (_state, body) => (posts.push(body), Promise.resolve()));
    expect({ posts, left: state.scrollLines }).toEqual({ posts: [], left: 0 });
  });

  it("drops_keep_retrying_with_backoff_and_stay_quiet_at_first", () => {
    const timers: number[] = [];
    const shown: string[] = [];
    const state = { retries: 0, reconnectTimer: null as ReturnType<typeof setTimeout> | null };
    for (let index = 0; index < 6; index++) {
      liveTerminalClosed(
        state,
        "Connection closed",
        (reason) => shown.push(reason),
        (_fn, delay) => (timers.push(delay ?? 0), timers.length as never),
      );
    }
    expect(timers).toEqual([1000, 2000, 4000, 8000, 10000, 10000]);
    expect(shown).toEqual(["Connection closed", "Connection closed", "Connection closed"]);
    expect(state.retries).toEqual(6);
  });

  it("ownership_conflict_is_reported_without_retry", () => {
    const timers: number[] = [];
    const shown: string[] = [];
    const state = { retries: 0, reconnectTimer: null as ReturnType<typeof setTimeout> | null };
    liveTerminalClosed(
      state,
      "pane already has an attached client",
      (reason) => shown.push(reason),
      (_fn, delay) => (timers.push(delay ?? 0), timers.length as never),
    );
    expect({ timers, shown }).toEqual({ timers: [], shown: ["pane already has an attached client"] });
  });
});
