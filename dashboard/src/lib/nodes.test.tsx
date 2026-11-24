// @vitest-environment jsdom
import { act } from "react-dom/test-utils";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nodeUrl, setApiNode, wsUrl } from "./api";
import { store } from "../store";
import { NewSessionModal } from "../terminal/NewSession";
import { HostsDialog } from "../components/Hosts";

describe("node URLs", () => {
  afterEach(() => setApiNode(""));

  it("keeps this host's calls as they are", () => {
    expect(nodeUrl("/api/state")).toBe("/api/state");
  });

  it("routes a linked host's calls through this host's proxy", () => {
    setApiNode("gpu-box");
    expect(nodeUrl("/api/herdr/screen?pane=p1")).toBe("/api/node/gpu-box/api/herdr/screen?pane=p1");
    expect(nodeUrl("/api/state", "")).toBe("/api/state");
    expect(wsUrl("/api/herdr/client?cols=1")).toMatch(/^ws:\/\/[^/]+\/api\/node\/gpu-box\/api\/herdr\/client\?cols=1$/);
  });

  it("never proxies the host links or an already proxied path", () => {
    setApiNode("gpu-box");
    expect(nodeUrl("/api/nodes")).toBe("/api/nodes");
    expect(nodeUrl("/api/nodes/remove")).toBe("/api/nodes/remove");
    expect(nodeUrl("/api/node/other/api/state")).toBe("/api/node/other/api/state");
  });

  it("leaves no raw /api call outside the node-aware helpers", () => {
    const sources = (import.meta as unknown as { glob: (p: string[], o: object) => Record<string, string> }).glob(
      ["../**/*.ts", "../**/*.tsx", "!../**/*.test.ts", "!../**/*.test.tsx"],
      { query: "?raw", import: "default", eager: true },
    );
    const raw = Object.entries(sources).flatMap(([file, text]) =>
      text
        .split("\n")
        .map((line, i) => [file, i + 1, line] as const)
        .filter(([, , line]) => /(fetch|EventSource|WebSocket)\(\s*[`"']\/api\//.test(line) || /location\.host\}\/api/.test(line)),
    );
    expect(Object.keys(sources).length).toBeGreaterThan(20);
    // Only the host links (always this host) may call /api directly.
    expect(raw.filter(([file]) => !file.endsWith("components/Hosts.tsx"))).toEqual([]);
  });
});

describe("new session dialog", () => {
  let root: Root;
  let host: HTMLDivElement;
  const herdr = {
    running: true,
    workspaces: [{ workspace_id: "w1", label: "ucm" }],
    tabs: [],
    panes: [],
    focused_pane_id: null,
  };

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    store.set({ node: "", nodes: [{ id: "gpu-box", label: "GPU box", host: "10.0.0.2", port: 8766 }] });
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    vi.unstubAllGlobals();
    store.set({ node: "", nodes: [] });
  });

  const flush = () => act(() => new Promise((resolve) => setTimeout(resolve, 0)));

  it("loads the chosen node's workspaces and offers a new one with a folder picker", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        calls.push(url);
        const body = url.includes("/api/fs/dirs")
          ? { path: "/srv", parent: "/", git: false, home: "/root", dirs: [{ name: "app", path: "/srv/app", git: true }], truncated: false }
          : herdr;
        return new Response(JSON.stringify(body), { status: 200 });
      }),
    );
    act(() => root.render(<NewSessionModal action={async () => ({ ok: true })} close={() => undefined} />));
    await flush();
    expect(calls).toEqual(["/api/herdr"]);
    const node = host.querySelector<HTMLSelectElement>('select[name="node"]')!;
    expect([...node.options].map((o) => o.textContent)).toEqual(["This host", "GPU box (10.0.0.2)"]);
    act(() => {
      node.value = "gpu-box";
      node.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flush();
    expect(calls.at(-1)).toBe("/api/node/gpu-box/api/herdr");
    const space = host.querySelector<HTMLSelectElement>('select[name="space"]')!;
    expect([...space.options].map((o) => o.textContent)).toEqual(["ucm", "New workspace…"]);
    act(() => {
      space.value = space.options[1].value;
      space.dispatchEvent(new Event("change", { bubbles: true }));
    });
    const browse = [...host.querySelectorAll("button")].find((b) => b.textContent === "browse")!;
    act(() => browse.click());
    await flush();
    expect(calls.at(-1)).toBe("/api/node/gpu-box/api/fs/dirs?path=");
    expect(host.querySelector(".path-picker")?.textContent).toContain("app/git");
  });
});

describe("hosts dialog", () => {
  it("links a host from its full dashboard URL", async () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    const posts: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (init?.method === "POST") posts.push(JSON.parse(String(init.body)));
        return new Response(JSON.stringify(url === "/api/nodes" && !init ? { nodes: [] } : { ok: true }), { status: 200 });
      }),
    );
    act(() => root.render(<HostsDialog close={() => undefined} />));
    expect(host.querySelectorAll("input").length).toBe(2);
    const url = host.querySelector<HTMLInputElement>('input[name="url"]')!;
    url.value = "http://10.0.0.12:8766/?t=abcdefgh";
    await act(async () => {
      host.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(posts).toEqual([{ label: "", url: "http://10.0.0.12:8766/?t=abcdefgh" }]);
    act(() => root.unmount());
    host.remove();
    vi.unstubAllGlobals();
  });
});
