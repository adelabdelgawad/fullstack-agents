import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { inline } from "./ChatConsole";

describe("chat inline markdown", () => {
  it("renders bold and code as elements and leaves other text and HTML as plain text", () => {
    const html = renderToStaticMarkup(<p>{inline("**Done.** Run `npm test` <b>now</b>")}</p>);
    expect(html).toBe("<p><strong>Done.</strong> Run <code>npm test</code> &lt;b&gt;now&lt;/b&gt;</p>");
  });
});

describe("session order", () => {
  it("puts the sessions that need you first and keeps each group's order", async () => {
    const { needsYouFirst } = await import("./ChatConsole");
    const card = (key: string, phase: string) =>
      ({ key, phase, sessions: [{ id: key, name: key, state: "working" }], needs_you: [], runs: [], now: [] }) as never;
    const order = needsYouFirst([card("a", "implement"), card("b", "review"), card("c", "plan"), card("d", "review")]);
    expect(order.map((item: { key: string }) => item.key)).toEqual(["b", "d", "a", "c"]);
  });
});
