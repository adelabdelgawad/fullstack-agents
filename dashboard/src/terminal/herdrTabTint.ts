import type { IBufferCell, Terminal } from "@xterm/xterm";

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
let focusBg: string | null = null;

export function setHerdrTabTintChips(next: TabTintChip[]): void {
  chips = next;
  redraw?.();
}

function cellBackground(term: Terminal, cell: IBufferCell): string | null {
  if (cell.isBgRGB()) return `#${cell.getBgColor().toString(16).padStart(6, "0")}`;
  return cell.isBgDefault() ? (term.options.theme?.background ?? null) : null;
}

function highlightRange(term: Terminal, span: TabTintSpan): [number, number] {
  const line = term.buffer.active.getLine(0);
  const first = line?.getCell(span.start);
  const background = first && !first.isBgDefault() ? cellBackground(term, first) : null;
  if (!span.focused || !line || !background) return [span.start, span.end];
  const same = (x: number) => {
    const data = x >= 0 && x < term.cols ? line.getCell(x) : undefined;
    return Boolean(data && cellBackground(term, data) === background);
  };
  let [start, end] = [span.start, span.end];
  while (span.start - start < 4 && same(start - 1)) start--;
  while (end - span.end < 4 && same(end)) end++;
  return [start, end];
}

function cellMarks(term: Terminal, span: TabTintSpan, cell: { w: number; h: number }): HTMLElement[] {
  const line = term.buffer.active.getLine(0);
  const marks: HTMLElement[] = [];
  const [start, end] = highlightRange(term, span);
  for (let x = start; x < end && line; x++) {
    const data = line.getCell(x);
    const background = data && data.getWidth() ? cellBackground(term, data) : null;
    if (!data || !background) continue;
    const mark = document.createElement("span");
    mark.className = `herdr-state-tint is-${span.status}${span.focused ? " is-focused" : ""}`;
    mark.textContent = data.getChars();
    Object.assign(mark.style, {
      left: `${x * cell.w}px`,
      width: `${data.getWidth() * cell.w}px`,
      height: `${cell.h}px`,
      lineHeight: `${cell.h}px`,
      background: span.focused ? "" : background,
      fontFamily: term.options.fontFamily ?? "monospace",
      fontSize: `${term.options.fontSize ?? 14}px`,
      fontWeight: data.isBold() ? "700" : "400",
    });
    marks.push(mark);
  }
  return marks;
}

export function focusedByBackground(backgrounds: (string | null)[]): number {
  const odd = backgrounds.map((bg, i) => (bg && backgrounds.filter((other) => other === bg).length === 1 ? i : -1));
  const found = odd.filter((i) => i >= 0);
  return backgrounds.length > 1 && found.length === 1 ? found[0] : -1;
}

function focusFromRow(term: Terminal, spans: TabTintSpan[]): TabTintSpan[] {
  const line = term.buffer.active.getLine(0);
  const backgrounds = spans.map((span) => {
    const data = line?.getCell(span.start);
    return data ? cellBackground(term, data) : null;
  });
  let focused = focusedByBackground(backgrounds);
  if (focused < 0 && focusBg && backgrounds.filter((bg) => bg === focusBg).length === 1)
    focused = backgrounds.indexOf(focusBg);
  if (focused < 0 && !focusBg) focused = spans.findIndex((span) => span.focused);
  if (focused < 0) return spans;
  focusBg = backgrounds[focused] ?? focusBg;
  return spans.map((span, i) => ({ ...span, focused: i === focused }));
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
  const spans = focusFromRow(term, tabTintSpans(row, chips)).filter((span) => span.status !== "unknown");
  layer.replaceChildren(...spans.flatMap((span) => cellMarks(term, span, cell)));
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
