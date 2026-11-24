/** The dashboard node every view talks to: "" is this host, any other id a linked host reached through
 * `/api/node/<id>/...` on this host (which holds that host's token). */
let focused = "";

export function apiNode(): string {
  return focused;
}

export function setApiNode(node: string): void {
  focused = node;
}

/** Calls that always stay on this host: the host links themselves and the proxy. */
const LOCAL_ONLY = /^\/api\/(nodes(\/|$|\?)|node\/)/;

/** The URL of an `/api/...` path on a node (default: the focused one). */
export function nodeUrl(path: string, node: string = focused): string {
  if (!node || !path.startsWith("/api/") || LOCAL_ONLY.test(path)) return path;
  return `/api/node/${encodeURIComponent(node)}${path}`;
}

/** The ws:// URL of an `/api/...` path on the focused node. */
export function wsUrl(path: string): string {
  return `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}${nodeUrl(path)}`;
}

export async function getJson<T = unknown>(url: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(nodeUrl(url), { cache: "no-store", ...init });
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

export async function fetchText(url: string): Promise<string> {
  const r = await fetch(nodeUrl(url), { cache: "no-store" });
  if (!r.ok) throw new Error(String(r.status));
  return r.text();
}

export async function postJson<T = unknown>(url: string, body: unknown): Promise<T | undefined> {
  const r = await fetch(nodeUrl(url), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(String(r.status));
  const text = await r.text();
  return text ? (JSON.parse(text) as T) : undefined;
}
