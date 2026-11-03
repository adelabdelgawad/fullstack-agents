export function snapshot(roots) {
  const OPAQUE = ".terminal, .herdr-client";
  const RAW = new Set(["PRE", "TEXTAREA"]);
  const CACHE = new Set(["data-h", "data-sig"]);
  const attrs = el => {
    const out = [...el.attributes].filter(a => !CACHE.has(a.name) && !(a.name === "selected" && el.tagName === "OPTION")).map(a => {
      if (a.name === "style") return ["style", el.style.cssText];
      if (a.name === "class") return ["class", [...el.classList].sort().join(" ")];
      return [a.name, a.value];
    });
    if ("value" in el && /^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName)) out.push([".value", String(el.value)]);
    if (el.tagName === "INPUT" && /^(checkbox|radio)$/.test(el.type)) out.push([".checked", String(el.checked)]);
    return out.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0))
      .map(([k, v]) => (v === "" ? ` ${k}` : ` ${k}="${v.replace(/"/g, "&quot;")}"`)).join("");
  };
  // Adjacent text nodes render as one run of text, so they compare as one.
  const merged = node => [...node.childNodes].reduce((acc, c) => {
    const prev = acc[acc.length - 1];
    if (c.nodeType === Node.TEXT_NODE && prev && prev.nodeType === Node.TEXT_NODE) acc[acc.length - 1] = {nodeType: Node.TEXT_NODE, data: prev.data + c.data};
    else acc.push(c);
    return acc;
  }, []);
  const ser = (node, depth, raw) => {
    const pad = "  ".repeat(depth);
    if (node.nodeType === Node.TEXT_NODE) {
      const text = raw ? node.data : node.data.replace(/\s+/g, " ").trim();
      return text ? [pad + JSON.stringify(text)] : [];
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return [];
    const tag = node.tagName.toLowerCase();
    const open = `${pad}<${tag}${attrs(node)}>`;
    if (node.matches(OPAQUE)) return [open, `${pad}  [opaque]`, `${pad}</${tag}>`];
    const inner = merged(node).flatMap(c => ser(c, depth + 1, raw || RAW.has(node.tagName)));
    return inner.length ? [open, ...inner, `${pad}</${tag}>`] : [`${open}</${tag}>`];
  };
  const out = {"html.class": [...document.documentElement.classList].sort().join(" "), title: document.title};
  for (const sel of roots) {
    const el = document.querySelector(sel);
    out[sel] = el ? ser(el, 0, false).join("\n") : null;
  }
  return out;
}

export function stubSockets() {
  class Inert extends EventTarget {
    static CONNECTING = 0; static OPEN = 1; static CLOSING = 2; static CLOSED = 3;
    constructor(url) { super(); this.url = String(url); this.readyState = 0; }
    send() {}
    close() { this.readyState = 3; }
  }
  window.WebSocket = class extends Inert {};
  window.EventSource = class extends Inert {};
}
