import { ago, esc, kb } from "./format";
import type { Card, DashState, Session } from "./types";

const BASIC = ["#000000", "#aa0000", "#00aa00", "#aa5500", "#0000aa", "#aa00aa", "#00aaaa", "#aaaaaa"];
const BRIGHT = ["#555555", "#ff5555", "#55ff55", "#ffff55", "#5555ff", "#ff55ff", "#55ffff", "#ffffff"];

const indexed = (n: number): string => {
  if (n < 8) return BASIC[n];
  if (n < 16) return BRIGHT[n - 8];
  if (n < 232) {
    const x = n - 16;
    const v = (z: number) => (z ? 55 + z * 40 : 0);
    return `rgb(${v(Math.floor(x / 36))},${v(Math.floor(x / 6) % 6)},${v(x % 6)})`;
  }
  const v = 8 + (n - 232) * 10;
  return `rgb(${v},${v},${v})`;
};

interface Sgr {
  bold: boolean;
  dim: boolean;
  italic: boolean;
  underline: boolean;
  inverse: boolean;
  fg: string;
  bg: string;
}

const plain = (): Sgr => ({ bold: false, dim: false, italic: false, underline: false, inverse: false, fg: "", bg: "" });

function sgrStyle(s: Sgr): string {
  let fg = s.fg;
  let bg = s.bg;
  if (s.inverse) [fg, bg] = [bg || "#e8e8e8", fg || "#101218"];
  return [
    s.bold && "font-weight:bold",
    s.dim && "opacity:.65",
    s.italic && "font-style:italic",
    s.underline && "text-decoration:underline",
    fg && `color:${fg}`,
    bg && `background-color:${bg}`,
  ]
    .filter(Boolean)
    .join(";");
}

function applySgr(s: Sgr, raw: string): void {
  const codes = raw === "" ? [0] : raw.split(";").map((x) => Number(x || 0));
  for (let i = 0; i < codes.length; i++) {
    const c = codes[i];
    if (c === 0) Object.assign(s, plain());
    else if (c === 1) s.bold = true;
    else if (c === 2) s.dim = true;
    else if (c === 3) s.italic = true;
    else if (c === 4) s.underline = true;
    else if (c === 7) s.inverse = true;
    else if (c === 22) s.bold = s.dim = false;
    else if (c === 23) s.italic = false;
    else if (c === 24) s.underline = false;
    else if (c === 27) s.inverse = false;
    else if (c >= 30 && c <= 37) s.fg = BASIC[c - 30];
    else if (c >= 90 && c <= 97) s.fg = BRIGHT[c - 90];
    else if (c >= 40 && c <= 47) s.bg = BASIC[c - 40];
    else if (c >= 100 && c <= 107) s.bg = BRIGHT[c - 100];
    else if (c === 39) s.fg = "";
    else if (c === 49) s.bg = "";
    else if ((c === 38 || c === 48) && codes[i + 1] === 5 && Number.isInteger(codes[i + 2])) {
      s[c === 38 ? "fg" : "bg"] = indexed(Math.max(0, Math.min(255, codes[i + 2])));
      i += 2;
    } else if (
      (c === 38 || c === 48) &&
      codes[i + 1] === 2 &&
      i + 4 < codes.length &&
      codes.slice(i + 2, i + 5).every(Number.isFinite)
    ) {
      s[c === 38 ? "fg" : "bg"] = `rgb(${codes
        .slice(i + 2, i + 5)
        .map((x) => Math.max(0, Math.min(255, x)))
        .join(",")})`;
      i += 4;
    }
  }
}

export function ansiHtml(input: unknown): string {
  const s = plain();
  const text = String(input ?? "").replace(/\x1b\][\s\S]*?(?:\x07|\x1b\\|$)/g, "");
  const csi = /\x1b\[([0-?]*)([ -/]*)([@-~])/g;
  let out = "";
  let at = 0;
  let m: RegExpExecArray | null;
  const add = (part: string) => {
    if (!part) return;
    const css = sgrStyle(s);
    out += css ? `<span style="${css}">${esc(part)}</span>` : esc(part);
  };
  while ((m = csi.exec(text))) {
    add(text.slice(at, m.index));
    if (m[3] === "m" && !m[2]) applySgr(s, m[1]);
    at = csi.lastIndex;
  }
  add(text.slice(at));
  return out.replace(/\x1b/g, "");
}

export const mdInline = (t: string): string =>
  esc(t)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>");

export const mdCells = (l: string): string[] =>
  l
    .trim()
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((x) => x.trim());

export function mdHtml(text: string): string {
  const out: string[] = [];
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (/^\s*\|.*\|\s*$/.test(l) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || "")) {
      const head = mdCells(l);
      const rows: string[][] = [];
      for (i += 2; i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i]); i++) rows.push(mdCells(lines[i]));
      i--;
      out.push(
        `<table class="md"><tr>${head.map((h) => `<th>${mdInline(h)}</th>`).join("")}</tr>${rows
          .map((r) => `<tr>${r.map((c) => `<td>${mdInline(c)}</td>`).join("")}</tr>`)
          .join("")}</table>`,
      );
    } else if (/^#{1,6} /.test(l)) out.push(`<div class="mdh">${mdInline(l.replace(/^#+ /, ""))}</div>`);
    else if (/^\s*([-*]|\d+\.) /.test(l))
      out.push(
        `<div class="mdli" style="padding-left:${12 + l.search(/\S/) * 6}px">${/^\s*\d/.test(l) ? esc(l.trim().split(" ")[0]) : "•"} ${mdInline(
          l.trim().replace(/^([-*]|\d+\.) /, ""),
        )}</div>`,
      );
    else out.push(l.trim() ? `<div>${mdInline(l)}</div>` : '<div class="mdgap"></div>');
  }
  return out.join("");
}

function docsHtml(s: Session): string {
  const docs = s.docs || [];
  if (!docs.length) return "";
  return `<div class="lbl">Files in this message · ${docs.length}</div><div class="docs">${docs
    .map(
      (d) =>
        `<div class="doc" title="${esc(d.path)}"><b>${esc(d.name)}</b><button class="copy-ico" data-doc-sid="${esc(s.id)}" data-doc="${esc(d.path)}" aria-label="Copy ${esc(
          d.name,
        )}" title="Copy file content">${COPY_ICON}</button><span class="s">${esc(d.shown)} · ${kb(d.size)}</span></div>`,
    )
    .join("")}</div>`;
}

const COPY_ICON =
  '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';

export function saidHtml(s: Session): string {
  const text = s.said_full || s.said;
  if (!text) return "";
  return `<div class="now"><div><b>${esc(s.name)}</b>${s.said_at ? ` <span class="s">sent ${ago(s.said_at)} ago</span>` : ""}</div><div class="said-full">${mdHtml(
    text,
  )}</div>${docsHtml(s)}</div>`;
}

export function saidText(sid: string, state: DashState | null): string | null {
  for (const c of (state && state.cards) || [])
    for (const x of c.now || []) if (x.id === sid) return x.said_full || x.said || null;
  return null;
}

export function lastPara(text: string | undefined): string {
  return (text || "")
    .replace(/^… /, "")
    .trim()
    .split(/\n\s*\n/)
    .pop()!
    .replace(/\s+/g, " ");
}

export function toolLine(s: Session): string {
  if (!s.action) return "";
  return s.action_running
    ? `Running ${ago(s.action_at!)} · ${s.action}`
    : `Done ${ago(s.action_at!)} ago · ${s.action}`;
}

export function questionLine(c: Pick<Card, "now">): string {
  const q = (c.now || []).find((x) => x.question);
  return q ? `<div class="act ask-q" title="${esc(q.question)}">Question for you: ${esc(q.question)}</div>` : "";
}
