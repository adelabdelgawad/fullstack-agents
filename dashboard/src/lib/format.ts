const ESC_MAP: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export const esc = (s: unknown): string => String(s ?? "").replace(/[&<>"']/g, (c) => ESC_MAP[c]);

export const ago = (t: number): string => {
  const s = Math.max(0, Date.now() / 1000 - t);
  return s < 90 ? `${Math.round(s)}s` : s < 5400 ? `${Math.round(s / 60)}m` : s < 172800 ? `${Math.round(s / 3600)}h` : `${Math.round(s / 86400)}d`;
};

export interface ChipLike {
  verdict: string;
  label: string;
  kind: string;
}

export const chip = (c: ChipLike): string => {
  const good = /^(GREEN|PASS)$/.test(c.verdict);
  const bad = /^(RED|CHANGES)$/.test(c.verdict);
  return `<span class="chip ${good ? "ok" : bad ? "bad" : ""}" title="${esc(c.label)}">${esc(c.kind)} ${esc(c.verdict)}</span>`;
};

export const kb = (n: number): string => (n < 1024 ? `${n} B` : `${Math.round(n / 1024)} KB`);

export const fmtTokens = (n: number): string =>
  !n ? "0" : n >= 1e9 ? (n / 1e9).toFixed(2) + "B" : n >= 1e6 ? (n / 1e6).toFixed(n >= 1e8 ? 0 : 1) + "M" : n >= 1e3 ? Math.round(n / 1e3) + "k" : String(n);

export const fmtCost = (c: number | null | undefined): string => (c === null || c === undefined ? "—" : c >= 100 ? "$" + Math.round(c) : "$" + c.toFixed(2));

const MODELS: Array<[string, string]> = [
  ["opus", "Opus"],
  ["sonnet", "Sonnet"],
  ["haiku", "Haiku"],
  ["fable", "Fable"],
  ["gpt", "Codex"],
  ["grok", "Grok"],
];

export const modelFamily = (m: string | undefined): string => {
  const x = String(m || "").toLowerCase();
  return (MODELS.find(([k]) => x.includes(k)) || [x.includes("codex") ? "gpt" : "other"])[0];
};

export const modelShort = (m: string | undefined): string =>
  String(m || "")
    .replace(/^claude-/, "")
    .replace(/-(\d+)-(\d+)$/, " $1.$2")
    .replace(/-(\d+)$/, " $1");
