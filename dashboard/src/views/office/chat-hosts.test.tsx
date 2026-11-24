// @vitest-environment jsdom
import { act } from "react-dom/test-utils";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setApiNode } from "../../lib/api";
import { store } from "../../store";
import { ChatConsole } from "./ChatConsole";

const card = (key: string, title: string) =>
  ({ key, title, phase: "", needs_you: [], sessions: [{ id: key, state: "idle" }], now: [], runs: [] }) as never;
const dash = (cards: unknown[]) => ({ cards, waiting: [], still_open: [], history: [], session_panes: {} }) as never;

describe("CTO chat across linked hosts", () => {
  let root: Root;
  let host: HTMLDivElement;

  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 200 })));
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    store.set({
      node: "",
      nodes: [{ id: "gpu-box", label: "GPU box", host: "10.0.0.2", port: 8766 }],
      state: dash([card("session:local1", "local work")]),
      nodeStates: { "gpu-box": { state: dash([card("session:remote1", "remote work")]), offline: false } },
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    vi.unstubAllGlobals();
    setApiNode("");
    store.set({ node: "", nodes: [], nodeStates: {}, state: null });
  });

  it("lists every host's sessions under its own heading and focuses a remote host when its session is picked", () => {
    act(() => root.render(<ChatConsole close={() => undefined} title="CTO" />));
    const headings = [...host.querySelectorAll(".chat-host")].map((node) => node.textContent);
    expect(headings).toEqual(["Local host", "GPU box"]);
    const remote = [...host.querySelectorAll<HTMLButtonElement>(".chat-sidebar button")].find((button) =>
      button.textContent?.includes("remote work"),
    );
    expect(remote).toBeTruthy();
    act(() => remote!.click());
    expect(store.get().node).toBe("gpu-box");
    const selected = host.querySelector('.chat-sidebar button[aria-current="true"]');
    expect(selected?.textContent).toContain("remote work");
  });
});
