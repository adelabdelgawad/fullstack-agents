import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { inline, Markdown } from "./markdown";

describe("chat inline markdown", () => {
  it("renders bold and code as elements and leaves other text and HTML as plain text", () => {
    const html = renderToStaticMarkup(<p>{inline("**Done.** Run `npm test` <b>now</b>")}</p>);
    expect(html).toBe("<p><strong>Done.</strong> Run <code>npm test</code> &lt;b&gt;now&lt;/b&gt;</p>");
  });
});

describe("session order", () => {
  it("keeps each session where it first appeared and adds new ones at the end", async () => {
    const { stableOrder } = await import("./ChatConsole");
    const cards = (...keys: string[]) => keys.map((key) => ({ key }) as never);
    const first = stableOrder([], cards("a", "b", "c"));
    expect(first).toEqual(["a", "b", "c"]);
    expect(stableOrder(first, cards("c", "b", "a", "d"))).toEqual(["a", "b", "c", "d"]);
    expect(stableOrder(first, cards("c", "a"))).toEqual(["a", "c"]);
  });
});

describe("chat markdown blocks", () => {
  it("renders a table, a code fence and a heading, keeping other text as paragraphs", () => {
    const reply =
      "Done.\n\n## Results\n| Check | Result |\n|---|:--:|\n| **tests** | 182 pass |\n| build | `clean` |\n\n```\nnpm test\n```";
    const html = renderToStaticMarkup(<Markdown text={reply} />);
    expect(html).toContain("<p>Done.</p>");
    expect(html).toContain('<p class="chat-heading">Results</p>');
    expect(html).toContain("<th>Check</th><th>Result</th>");
    expect(html).toContain("<td><strong>tests</strong></td><td>182 pass</td>");
    expect(html).toContain("<td>build</td><td><code>clean</code></td>");
    expect(html).toContain("<pre>npm test</pre>");
  });

  it("leaves pipes that are not a table as text", () => {
    expect(renderToStaticMarkup(<Markdown text={"a | b"} />)).toBe("<p>a | b</p>");
  });
});

describe("working line", () => {
  it("shows the running action while the session works, and nothing otherwise", async () => {
    const { workingLine } = await import("./ChatConsole");
    expect(workingLine({ id: "a", state: "working", action: "Bash: run tests", action_running: true } as never)).toBe(
      "Working · Bash: run tests",
    );
    expect(workingLine({ id: "a", state: "working" } as never)).toBe("Working…");
    expect(workingLine({ id: "a", state: "idle", action: "Bash: x", action_running: true } as never)).toBe("");
  });
});
