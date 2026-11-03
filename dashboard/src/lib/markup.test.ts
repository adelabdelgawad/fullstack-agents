import { describe, expect, it } from "vitest";
import { ansiHtml, mdHtml } from "./markup";

describe("ansiHtml", () => {
  it("wraps SGR runs in a span and resets afterwards", () => {
    expect(ansiHtml("\x1b[1;31mHello\x1b[0m World")).toBe('<span style="font-weight:bold;color:#aa0000">Hello</span> World');
  });

  it("renders 256-colour codes as rgb()", () => {
    expect(ansiHtml("\x1b[38;5;196mRed256\x1b[0m")).toBe('<span style="color:rgb(255,0,0)">Red256</span>');
  });

  it("escapes html-sensitive characters in plain text", () => {
    expect(ansiHtml("<tag> & \"quote\"")).toBe("&lt;tag&gt; &amp; &quot;quote&quot;");
  });
});

describe("mdHtml", () => {
  it("renders headings, list items and inline markup", () => {
    const out = mdHtml("# Title\n- item one **bold** and *italic* and `code`");
    expect(out).toBe(
      '<div class="mdh">Title</div><div class="mdli" style="padding-left:12px">• item one <b>bold</b> and <i>italic</i> and <code>code</code></div>',
    );
  });

  it("renders a pipe table", () => {
    const out = mdHtml("| A | B |\n| - | - |\n| 1 | 2 |");
    expect(out).toBe('<table class="md"><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>');
  });

  it("renders blank lines as a gap and other lines as plain divs", () => {
    expect(mdHtml("one\n\ntwo")).toBe('<div>one</div><div class="mdgap"></div><div>two</div>');
  });
});
