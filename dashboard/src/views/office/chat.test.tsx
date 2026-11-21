import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { inline } from "./ChatConsole";

describe("chat inline markdown", () => {
  it("renders bold and code as elements and leaves other text and HTML as plain text", () => {
    const html = renderToStaticMarkup(<p>{inline("**Done.** Run `npm test` <b>now</b>")}</p>);
    expect(html).toBe("<p><strong>Done.</strong> Run <code>npm test</code> &lt;b&gt;now&lt;/b&gt;</p>");
  });
});
