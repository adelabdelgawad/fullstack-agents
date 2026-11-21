/** Just enough Markdown for agent replies in the chat: tables, fenced code, headings, bold and inline code.
 * Everything is built as React elements, so text from transcripts can never inject HTML. */

export type Block =
  | { kind: "text"; text: string }
  | { kind: "heading"; text: string }
  | { kind: "code"; text: string }
  | { kind: "table"; head: string[]; rows: string[][] };

/** Bold and inline code as React nodes; everything else stays plain text. */
export function inline(text: string): Array<string | JSX.Element> {
  return text.split(/(\*\*[^*\n]+\*\*|`[^`\n]+`)/g).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4)
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2)
      return <code key={index}>{part.slice(1, -1)}</code>;
    return part;
  });
}

const cells = (line: string) =>
  line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
const isRow = (line: string | undefined) => Boolean(line && /^\s*\|.*\|\s*$/.test(line));
const isRule = (line: string | undefined) =>
  Boolean(line && /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/.test(line));

/** Split a reply into blocks; anything that is not a table, fence or heading stays text with its line breaks. */
export function blocks(source: string): Block[] {
  const lines = source.split("\n");
  const out: Block[] = [];
  let text: string[] = [];
  const flush = () => {
    if (text.join("").trim()) out.push({ kind: "text", text: text.join("\n").replace(/^\n+|\n+$/g, "") });
    text = [];
  };
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (/^\s*```/.test(line)) {
      flush();
      const code: string[] = [];
      for (index += 1; index < lines.length && !/^\s*```/.test(lines[index]); index += 1) code.push(lines[index]);
      out.push({ kind: "code", text: code.join("\n") });
    } else if (isRow(line) && isRule(lines[index + 1])) {
      flush();
      const head = cells(line);
      const rows: string[][] = [];
      for (index += 2; isRow(lines[index]); index += 1) rows.push(cells(lines[index]));
      index -= 1;
      out.push({ kind: "table", head, rows });
    } else if (/^#{1,6}\s+/.test(line)) {
      flush();
      out.push({ kind: "heading", text: line.replace(/^#{1,6}\s+/, "") });
    } else text.push(line);
  }
  flush();
  return out;
}

export function Markdown({ text }: { text: string }) {
  return (
    <>
      {blocks(text).map((block, index) => {
        if (block.kind === "code") return <pre key={index}>{block.text}</pre>;
        if (block.kind === "heading")
          return (
            <p key={index} className="chat-heading">
              {inline(block.text)}
            </p>
          );
        if (block.kind === "text") return <p key={index}>{inline(block.text)}</p>;
        return (
          <div key={index} className="chat-table">
            <table>
              <thead>
                <tr>
                  {block.head.map((cell, column) => (
                    <th key={column}>{inline(cell)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {block.rows.map((row, line) => (
                  <tr key={line}>
                    {block.head.map((_, column) => (
                      <td key={column}>{inline(row[column] ?? "")}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </>
  );
}
