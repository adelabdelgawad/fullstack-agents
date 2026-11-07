import { describe, expect, it } from "vitest";
import { wireTouchScroll } from "./touchScroll";

function setup() {
  const host = document.createElement("div");
  const screen = document.createElement("div");
  screen.className = "xterm-screen";
  const row = document.createElement("span");
  screen.append(row);
  host.append(screen);
  const wheels: WheelEvent[] = [];
  screen.addEventListener("wheel", (event) => wheels.push(event));
  const binding = wireTouchScroll(host);
  const touch = (type: string, y: number, count = 1, x = 50) => {
    const event = new Event(type, { bubbles: true, cancelable: true });
    Object.defineProperty(event, "touches", {
      value: Array.from({ length: count }, (_, identifier) => ({ identifier, clientX: x, clientY: y })),
    });
    row.dispatchEvent(event);
    return event;
  };
  return { touch, wheels, binding, row };
}

describe("terminal touch scrolling", () => {
  it("continues a swipe when terminal output replaces the touched text", () => {
    const { touch, wheels, row } = setup();
    touch("touchstart", 100);
    touch("touchmove", 140);
    row.remove();
    touch("touchmove", 180);
    expect(wheels.map((event) => event.deltaY)).toEqual([-1, -1]);
    touch("touchend", 180, 0);
    touch("touchmove", 220);
    expect(wheels).toHaveLength(2);
  });
  it("accumulates small moves and routes wheel events at the touched pane", () => {
    const { touch, wheels } = setup();
    touch("touchstart", 100);
    for (let y = 110; y <= 180; y += 10) expect(touch("touchmove", y).defaultPrevented).toBe(true);
    expect(wheels.map((event) => [event.deltaY, event.deltaMode, event.clientX, event.clientY])).toEqual([
      [-1, 1, 50, 100],
      [-1, 1, 50, 100],
    ]);
    touch("touchmove", 140);
    expect(wheels.at(-1)?.deltaY).toBe(1);
  });

  it("preserves taps and ignores horizontal and multi-touch gestures", () => {
    const { touch, wheels } = setup();
    expect(touch("touchstart", 100).defaultPrevented).toBe(false);
    expect(touch("touchmove", 102).defaultPrevented).toBe(false);
    touch("touchend", 102, 0);
    touch("touchstart", 100);
    expect(touch("touchmove", 110, 1, 150).defaultPrevented).toBe(false);
    touch("touchstart", 100, 2);
    expect(touch("touchmove", 200, 2).defaultPrevented).toBe(false);
    touch("touchmove", 300);
    expect(wheels).toHaveLength(0);
  });

  it("clears partial movement on cancellation and removes listeners on disposal", () => {
    const { touch, wheels, binding } = setup();
    touch("touchstart", 100);
    touch("touchmove", 130);
    touch("touchcancel", 130, 0);
    touch("touchstart", 100);
    touch("touchmove", 120);
    expect(wheels).toHaveLength(0);
    binding.dispose();
    touch("touchmove", 200);
    touch("touchstart", 100);
    touch("touchmove", 200);
    expect(wheels).toHaveLength(0);
  });
});
