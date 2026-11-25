import type { IDisposable, Terminal } from "@xterm/xterm";

// Drag selection past the live terminal's top or bottom edge. The live view mirrors herdr's screen with no local
// scrollback, so the drag scrolls herdr's pane instead, and the rows each new screen reveals are kept here: the
// selection then spans every screen the drag passed, and releasing the mouse copies all of it.

/** The rows seen during one drag: lines[top + r] is the screen's row r now. */
export interface DragDoc {
  lines: string[];
  top: number;
}

export interface DragPoint {
  line: number;
  col: number;
}

const EDGE_TICK_MS = 80;
const EDGE_PX_PER_LINE = 24;
const EDGE_MAX_LINES = 5;

/** How many rows the screen moved down (scrolled up; negative: up, scrolled down) from before to after: the shift
 * that lines up the most identical non-blank rows, the one nearest the expected shift on a tie, 0 when none fit. */
export function rowShift(before: string[], after: string[], expected: number): number {
  const reach = Math.min(after.length - 1, Math.abs(expected) + EDGE_MAX_LINES);
  let best = 0;
  let bestScore = 0;
  for (let shift = -reach; shift <= reach; shift++) {
    let score = 0;
    for (let row = Math.max(0, shift); row < Math.min(after.length, before.length + shift); row++)
      if (after[row].trim() && after[row] === before[row - shift]) score++;
    const nearer = Math.abs(shift - expected) < Math.abs(best - expected);
    if (score > bestScore || (score === bestScore && score > 0 && nearer)) {
      best = shift;
      bestScore = score;
    }
  }
  return bestScore >= Math.min(3, Math.ceil(after.length / 4)) ? best : 0;
}

/** The document after a new screen: the screen moved down `shift` rows, then its rows overwrite what they cover.
 * `added` lines went in above the old first line, so every point kept in the old document moves down by it. */
export function mergeRows(doc: DragDoc, rows: string[], shift: number): DragDoc & { added: number } {
  const lines = doc.lines.slice();
  const added = Math.max(0, shift - doc.top);
  lines.unshift(...Array<string>(added).fill(""));
  const top = doc.top - shift + added;
  rows.forEach((row, index) => (lines[top + index] = row));
  for (let index = 0; index < lines.length; index++) lines[index] ??= "";
  return { lines, top, added };
}

/** The text between two points in reading order, the later point excluded as in xterm, each line's trailing blanks
 * dropped; an end at a line's first column ends the text with the line before. */
export function selectedText(doc: DragDoc, a: DragPoint, b: DragPoint): string {
  const [start, end] = a.line < b.line || (a.line === b.line && a.col <= b.col) ? [a, b] : [b, a];
  const out: string[] = [];
  for (let line = start.line; line <= end.line; line++) {
    const text = doc.lines[line] ?? "";
    const from = line === start.line ? start.col : 0;
    if (line === end.line && end.col === 0 && line > start.line) break;
    const to = line === end.line ? end.col : text.length;
    out.push(text.slice(from, to).trimEnd());
  }
  return out.join("\n");
}

const screenRows = (term: Terminal): string[] =>
  Array.from({ length: term.rows }, (_, row) => term.buffer.active.getLine(row)?.translateToString(true) ?? "");

const screenOf = (host: HTMLElement): HTMLElement => host.querySelector<HTMLElement>(".xterm-screen") ?? host;

/** The terminal cell under a viewport point, clamped to the screen. */
function cellAt(host: HTMLElement, term: Terminal, x: number, y: number): { row: number; col: number } {
  const rect = screenOf(host).getBoundingClientRect();
  const clamp = (value: number, max: number) => Math.max(0, Math.min(max - 1, value));
  return {
    row: clamp(Math.floor(((y - rect.top) / rect.height) * term.rows), term.rows),
    col: clamp(Math.floor(((x - rect.left) / rect.width) * term.cols), term.cols),
  };
}

/** Pixels past the screen's top (negative) or bottom (positive) edge; 0 inside. */
function edgeDistance(host: HTMLElement, y: number): number {
  const rect = screenOf(host).getBoundingClientRect();
  return y < rect.top ? y - rect.top : y > rect.bottom ? y - rect.bottom : 0;
}

/** One left-button drag: the rows it has seen, its two ends, and the edge-scroll timer. */
class DragSession {
  doc: DragDoc;
  rows: string[];
  anchor: DragPoint;
  focus: DragPoint;
  expected = 0;
  scrolled = false;
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor(
    private host: HTMLElement,
    private term: Terminal,
    private scroll: (lines: number) => void,
    private x: number,
    private y: number,
  ) {
    const cell = cellAt(host, term, x, y);
    this.rows = screenRows(term);
    this.doc = { lines: this.rows, top: 0 };
    this.anchor = this.focus = { line: cell.row, col: cell.col };
  }

  /** The pointer moved: start or stop edge scrolling; once herdr scrolled, move the focus and repaint. */
  moveTo(x: number, y: number): void {
    this.x = x;
    this.y = y;
    const past = edgeDistance(this.host, y);
    if (past && !this.timer) {
      this.tick();
      this.timer = setInterval(() => this.tick(), EDGE_TICK_MS);
    } else if (!past) this.stop();
    if (this.scrolled) this.followAndPaint();
  }

  /** The wheel during a drag: the terminal's own handler scrolls herdr, this records the expected shift. */
  wheel(deltaY: number): void {
    this.scrolled = true;
    this.expected -= Math.sign(deltaY) * Math.max(1, Math.round(Math.abs(deltaY) / 40));
  }

  /** A new herdr screen arrived: align it with the last one and keep its rows. */
  frame(): void {
    const rows = screenRows(this.term);
    const shift = rowShift(this.rows, rows, this.expected);
    this.expected -= shift;
    const { lines, top, added } = mergeRows(this.doc, rows, shift);
    this.doc = { lines, top };
    this.anchor = { ...this.anchor, line: this.anchor.line + added };
    this.rows = rows;
    this.followAndPaint();
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  text(): string {
    return selectedText(this.doc, this.anchor, this.focus);
  }

  private tick(): void {
    const past = edgeDistance(this.host, this.y);
    if (!past) return;
    const lines = Math.sign(past) * Math.min(EDGE_MAX_LINES, Math.ceil(Math.abs(past) / EDGE_PX_PER_LINE));
    this.scrolled = true;
    this.expected -= lines;
    this.scroll(lines);
  }

  private followAndPaint(): void {
    const cell = cellAt(this.host, this.term, this.x, this.y);
    this.focus = { line: this.doc.top + cell.row, col: cell.col };
    this.paint();
  }

  /** Paint the part of the selection on the screen now. */
  paint(): void {
    const { anchor, focus, doc, term } = this;
    const [start, end] =
      anchor.line < focus.line || (anchor.line === focus.line && anchor.col <= focus.col) ? [anchor, focus] : [focus, anchor];
    const last = term.rows - 1;
    const from = start.line < doc.top ? { row: 0, col: 0 } : { row: start.line - doc.top, col: start.col };
    const to = end.line > doc.top + last ? { row: last, col: term.cols } : { row: end.line - doc.top, col: end.col };
    if (from.row > last || to.row < 0) return term.clearSelection();
    term.select(from.col, from.row, (to.row - from.row) * term.cols + to.col - from.col);
  }
}

/** Wire drag-past-the-edge scrolling on a live terminal. `scroll(lines)` scrolls herdr's pane (negative: up);
 * `copied(text)` receives the whole selection, synchronously, when a drag that scrolled ends. */
export function wireDragScroll(
  host: HTMLElement,
  term: Terminal,
  scroll: (lines: number) => void,
  copied: (text: string) => void,
): IDisposable {
  let drag: DragSession | null = null;
  const end = () => {
    drag?.stop();
    drag = null;
  };
  const down = (event: MouseEvent) => {
    end();
    if (event.button !== 0 || term.modes.mouseTrackingMode !== "none") return;
    drag = new DragSession(host, term, scroll, event.clientX, event.clientY);
  };
  const move = (event: MouseEvent) => {
    if (!drag) return;
    drag.moveTo(event.clientX, event.clientY);
    // Once herdr scrolled, this module owns the selection: xterm's own would point at rows that moved.
    if (drag.scrolled) event.stopImmediatePropagation();
  };
  const up = () => {
    const done = drag;
    end();
    if (!done?.scrolled) return;
    copied(done.text());
    // After xterm's own mouseup handling, so the full selection stays painted.
    setTimeout(() => done.paint());
  };
  const wheel = (event: WheelEvent) => {
    if (drag && event.deltaY) drag.wheel(event.deltaY);
  };
  const parsed = term.onWriteParsed(() => {
    if (drag?.scrolled) drag.frame();
  });
  const listeners: [EventTarget, string, EventListener][] = [
    [host, "mousedown", down as EventListener],
    [host, "wheel", wheel as EventListener],
    [window, "mousemove", move as EventListener],
    [window, "mouseup", up],
  ];
  for (const [target, type, fn] of listeners) target.addEventListener(type, fn, true);
  return {
    dispose: () => {
      end();
      parsed.dispose();
      for (const [target, type, fn] of listeners) target.removeEventListener(type, fn, true);
    },
  };
}
