import type { IDisposable } from "@xterm/xterm";

// Remote terminals have no local scrollback. Reuse xterm's wheel path so
// mouse reporting (including the pane under the finger) stays authoritative.
export function wireTouchScroll(host: HTMLElement): IDisposable {
  let gesture: {
    id: number;
    x: number;
    y: number;
    lastY: number;
    pending: number;
    target: HTMLElement;
    scrolling: boolean;
  } | null = null;
  const reset = () => {
    gesture?.target.removeEventListener("touchmove", move, true);
    gesture?.target.removeEventListener("touchend", reset, true);
    gesture?.target.removeEventListener("touchcancel", reset, true);
    gesture = null;
  };
  const start = (event: TouchEvent) => {
    reset();
    if (event.touches.length !== 1 || !(event.target instanceof HTMLElement)) return;
    const touch = event.touches[0];
    gesture = {
      id: touch.identifier,
      x: touch.clientX,
      y: touch.clientY,
      lastY: touch.clientY,
      pending: 0,
      target: event.target,
      scrolling: false,
    };
    // Touch events keep their original target even after xterm redraws it.
    gesture.target.addEventListener("touchmove", move, { capture: true, passive: false });
    gesture.target.addEventListener("touchend", reset, true);
    gesture.target.addEventListener("touchcancel", reset, true);
  };
  const move = (event: TouchEvent) => {
    if (!gesture) return;
    const touch = event.touches[0];
    if (event.touches.length !== 1 || touch.identifier !== gesture.id) return reset();
    if (!gesture.scrolling) {
      const dx = Math.abs(touch.clientX - gesture.x);
      const dy = Math.abs(touch.clientY - gesture.y);
      if (Math.max(dx, dy) < 8) return;
      if (dx >= dy) return reset();
      gesture.scrolling = true;
    }
    event.preventDefault();
    event.stopPropagation();
    gesture.pending += gesture.lastY - touch.clientY;
    gesture.lastY = touch.clientY;
    while (Math.abs(gesture.pending) >= 40) {
      const direction = Math.sign(gesture.pending);
      gesture.pending -= direction * 40;
      (host.querySelector(".xterm-screen") ?? host).dispatchEvent(
        new WheelEvent("wheel", {
          bubbles: true,
          cancelable: true,
          deltaMode: 1,
          deltaY: direction,
          clientX: gesture.x,
          clientY: gesture.y,
        }),
      );
    }
  };
  host.addEventListener("touchstart", start, { capture: true, passive: true });
  host.addEventListener("touchend", reset, true);
  host.addEventListener("touchcancel", reset, true);
  return {
    dispose() {
      reset();
      host.removeEventListener("touchstart", start, true);
      host.removeEventListener("touchend", reset, true);
      host.removeEventListener("touchcancel", reset, true);
    },
  };
}
