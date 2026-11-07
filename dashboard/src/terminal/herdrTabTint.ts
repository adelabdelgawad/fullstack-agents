import type { Terminal } from "@xterm/xterm";

export interface TabTintChip {
  label: string;
  status: string;
  focused: boolean;
}

export interface TabTintSpan extends TabTintChip {
  start: number;
  end: number;
}

const WORD = /[\p{L}\p{N}_-]/u;

function isBoundary(row: string, index: number): boolean {
  return index < 0 || index >= row.length || !WORD.test(row[index]);
}

export function tabTintSpans(row: string, chips: TabTintChip[]): TabTintSpan[] {
  const spans: TabTintSpan[] = [];
  let from = 0;
  for (const chip of chips) {
    if (!chip.label) continue;
    let at = row.indexOf(chip.label, from);
    while (at >= 0 && !(isBoundary(row, at - 1) && isBoundary(row, at + chip.label.length)))
      at = row.indexOf(chip.label, at + 1);
    if (at < 0) continue;
    spans.push({ ...chip, start: at, end: at + chip.label.length });
    from = at + chip.label.length;
  }
  return spans;
}

let chips: TabTintChip[] = [];
let redraw: (() => void) | null = null;

export function setHerdrTabTintChips(next: TabTintChip[]): void {
  chips = next;
  redraw?.();
}

function paint(term: Terminal, host: HTMLElement, layer: HTMLElement): void {
  const screen = term.element?.querySelector<HTMLElement>(".xterm-screen");
  const row = term.buffer.active.getLine(0)?.translateToString(false) ?? "";
  if (!screen || !term.cols || !term.rows) return void layer.replaceChildren();
  const box = screen.getBoundingClientRect();
  const origin = host.getBoundingClientRect();
  const cell = { w: box.width / term.cols, h: box.height / term.rows };
  layer.style.left = `${box.left - origin.left}px`;
  layer.style.top = `${box.top - origin.top}px`;
  layer.replaceChildren(
    ...tabTintSpans(row, chips).map((span) => {
      const mark = document.createElement("span");
      mark.className = `herdr-state-tint is-${span.status}${span.focused ? " is-focused" : ""}`;
      mark.style.left = `${span.start * cell.w}px`;
      mark.style.width = `${(span.end - span.start) * cell.w}px`;
      mark.style.height = `${cell.h}px`;
      return mark;
    }),
  );
}

export function wireHerdrTabTint(term: Terminal, host: HTMLElement): { dispose(): void } {
  const layer = document.createElement("div");
  layer.className = "herdr-state-tints";
  layer.setAttribute("aria-hidden", "true");
  host.append(layer);
  let queued = false;
  const draw = () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      paint(term, host, layer);
    });
  };
  redraw = draw;
  const onRender = term.onRender(({ start }) => {
    if (start === 0) draw();
  });
  const onResize = term.onResize(draw);
  draw();
  return {
    dispose() {
      onRender.dispose();
      onResize.dispose();
      layer.remove();
      if (redraw === draw) redraw = null;
    },
  };
}
