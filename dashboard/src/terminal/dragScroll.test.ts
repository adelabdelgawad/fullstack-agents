import { describe, expect, it } from "vitest";
import { edgeSpeed, mergeRows, rowShift, selectedText } from "./dragScroll";

const screen = (first: number, rows = 6) => Array.from({ length: rows }, (_, index) => `line ${first + index}`);

describe("drag selection past the live terminal's edge", () => {
  it("measures how far herdr's screen moved, either way, and 0 when nothing lines up", () => {
    expect(rowShift(screen(10), screen(8), 2)).toBe(2);
    expect(rowShift(screen(10), screen(7), 1)).toBe(3);
    expect(rowShift(screen(10), screen(13), -3)).toBe(-3);
    expect(rowShift(screen(10), screen(10), 2)).toBe(0);
    expect(rowShift(screen(10), screen(100), 2)).toBe(0);
  });

  it("keeps the rows a drag scrolled past, above and below the screen", () => {
    let doc = { lines: screen(10), top: 0, added: 0 };
    let anchor = 4; // "line 14"
    doc = mergeRows(doc, screen(8), 2);
    anchor += doc.added;
    doc = mergeRows(doc, screen(5), 3);
    anchor += doc.added;
    expect(doc).toEqual({ lines: screen(5, 11), top: 0, added: 3 });
    expect(doc.lines[anchor]).toBe("line 14");
    doc = mergeRows(doc, screen(9), -4);
    expect([doc.top, doc.added]).toEqual([4, 0]);
    expect(doc.lines).toEqual(screen(5, 11));
  });

  it("copies from the anchor to the pointer in reading order, whichever way the drag went", () => {
    const doc = { lines: ["alpha one  ", "beta two", "gamma three"], top: 0 };
    expect(selectedText(doc, { line: 2, col: 5 }, { line: 0, col: 6 })).toBe("one\nbeta two\ngamma");
    expect(selectedText(doc, { line: 1, col: 0 }, { line: 1, col: 4 })).toBe("beta");
    expect(selectedText(doc, { line: 2, col: 0 }, { line: 0, col: 0 })).toBe("alpha one\nbeta two");
  });
  it("scrolls faster the further the pointer is past the edge, in the edge's direction, up to a cap", () => {
    expect(edgeSpeed(-1)).toBeLessThan(0);
    expect(edgeSpeed(10)).toBeGreaterThan(0);
    expect(Math.abs(edgeSpeed(-100))).toBeGreaterThan(Math.abs(edgeSpeed(-20)));
    expect(edgeSpeed(5000)).toBe(edgeSpeed(500));
  });
});
