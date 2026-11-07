import { describe, expect, it } from "vitest";
import { wireCtrlBackspaceWordErase } from "./wordErase";

function setup() {
  const sent: string[] = [];
  let handler: (event: KeyboardEvent) => boolean = () => true;
  wireCtrlBackspaceWordErase({
    attachCustomKeyEventHandler: (fn) => {
      handler = fn;
    },
    input: (data) => {
      sent.push(data);
    },
  });
  const press = (type: string, init: KeyboardEventInit) => {
    const event = new KeyboardEvent(type, { cancelable: true, ...init });
    return { handled: handler(event), prevented: event.defaultPrevented };
  };
  return { sent, press };
}

describe("Ctrl+Backspace word erase", () => {
  it("sends ^W once per keydown and blocks xterm's own handling", () => {
    const { sent, press } = setup();
    expect(press("keydown", { key: "Backspace", ctrlKey: true })).toEqual({ handled: false, prevented: true });
    expect(press("keyup", { key: "Backspace", ctrlKey: true }).handled).toBe(false);
    expect(sent).toEqual(["\u0017"]);
  });

  it("leaves plain Backspace and other Ctrl keys to xterm", () => {
    const { sent, press } = setup();
    expect(press("keydown", { key: "Backspace" }).handled).toBe(true);
    expect(press("keydown", { key: "Backspace", ctrlKey: true, altKey: true }).handled).toBe(true);
    expect(press("keydown", { key: "w", ctrlKey: true }).handled).toBe(true);
    expect(sent).toEqual([]);
  });
});
