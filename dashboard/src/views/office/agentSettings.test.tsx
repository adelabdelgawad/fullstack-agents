// @vitest-environment jsdom
import { act } from "react-dom/test-utils";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AgentSettings, AgentSettingsForm, withSetting, type AgentConfigReply } from "./AgentSettings";

const builtin = {
  implementer: "claude",
  models: { claude_implement: "claude-sonnet-5", codex_implement: "gpt-5.6-sol" },
  grok_scan: false,
  subagents: { "bounded-extractor": "haiku", "test-runner": "sonnet" },
};
const reply = (scope: "default" | "session", settings: AgentConfigReply["settings"]): AgentConfigReply => ({
  scope,
  settings,
  builtin,
  engines: ["claude", "codex", "grok"],
  subagent_models: ["haiku", "sonnet", "opus", "fable"],
});
const render = (r: AgentConfigReply) =>
  renderToStaticMarkup(<AgentSettingsForm reply={r} draft={r.settings || {}} setDraft={() => undefined} />);

describe("agent settings form", () => {
  it("shows built-in defaults as placeholders and default options", () => {
    const html = render(reply("default", null));
    expect(html).toContain("Applies to new sessions only");
    expect(html).toContain('placeholder="claude-sonnet-5"');
    expect(html).toContain("default (claude)");
    expect(html).toContain("default (haiku)");
  });

  it("tells a pre-feature session that saving creates its file", () => {
    expect(render(reply("session", null))).toContain("Saving creates its settings");
    expect(render(reply("session", { implementer: "codex" }))).toContain("this session");
  });

  it("drops an emptied setting so the built-in applies", () => {
    const draft = withSetting({ models: { codex_plan: "x" } }, "models", "codex_plan", "");
    expect(draft.models).toEqual({});
    expect(withSetting({}, "subagents", "test-runner", "opus").subagents).toEqual({ "test-runner": "opus" });
  });
});

describe("agent settings dialog", () => {
  let host: HTMLDivElement;
  let root: Root;
  const fetchMock = vi.fn();
  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("loads the session's settings and posts the edited draft with its sid", async () => {
    const loaded = reply("session", { implementer: "codex" });
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => loaded });
    fetchMock.mockResolvedValueOnce({ ok: true, text: async () => JSON.stringify(loaded) });
    await act(async () => root.render(<AgentSettings sid="lead-1" close={() => undefined} />));
    expect(fetchMock.mock.calls[0][0]).toBe("/api/agent-config?sid=lead-1");
    const engine = host.querySelector("select") as HTMLSelectElement;
    expect(engine.value).toBe("codex");
    await act(async () => {
      (host.querySelector('button[type="submit"]') as HTMLButtonElement).click();
    });
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/agent-config");
    expect(JSON.parse(init.body)).toEqual({ sid: "lead-1", settings: { implementer: "codex" } });
    expect(host.textContent).toContain("Saved.");
  });
});
