import { describe, expect, it, vi } from "vitest";
import { copySelection } from "./copy";

describe("copySelection", () => {
  it("offers a retry with the same text when browser copy is blocked", async () => {
    const writes: string[] = [];
    const restore = vi.fn();
    const offers: Array<{ message: string; action?: { label: string; run: () => Promise<void> } }> = [];
    let allowed = false;
    const write = async (text: string) => (writes.push(text), allowed);
    const show = (message: string, action?: { label: string; run: () => Promise<void> }) => offers.push({ message, action });

    await copySelection("x".repeat(40_000), restore, write, show);
    allowed = true;
    await offers[0].action?.run();

    expect(offers.map(({ message, action }) => [message, action?.label])).toEqual([
      ["copy blocked by the browser", "copy 40000 chars"],
      ["copied 40000 chars", undefined],
    ]);
    expect(writes.map((text) => text.length)).toEqual([40_000, 40_000]);
    expect(restore).toHaveBeenCalledTimes(2);
  });
});
