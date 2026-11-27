// @vitest-environment jsdom
import { act } from "react-dom/test-utils";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  AgentSettings,
  AgentSettingsForm,
  implementerModel,
  withSetting,
  withSwitchedImplementer,
  type AgentConfigReply,
} from "./AgentSettings";

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
  implementer_choices: ["codex", "claude"],
  implementer_models: { codex: "gpt-6.1-sol", claude: "claude-sonnet-5-5" },
  subagent_models: ["haiku", "sonnet", "opus", "fable"],
});
const render = (r: AgentConfigReply) =>
  renderToStaticMarkup(<AgentSettingsForm reply={r} draft={r.settings || {}} setDraft={() => undefined} />);

describe("agent settings form", () => {
  it("offers exactly Codex and Claude as radio options with each one's model as text", () => {
    const html = render(reply("default", null));
    expect(html).toContain("Applies to new sessions only");
    const radios = html.match(/<input type="radio"[^>]*>/g) || [];
    expect(radios).toHaveLength(2);
    expect(radios[0]).toContain('value="codex"');
    expect(radios[1]).toContain('value="claude"');
    expect(radios[1]).toContain("checked");
    expect(html.indexOf("Codex")).toBeLessThan(html.indexOf("Claude"));
    // The current engine shows its effective model; the other shows the model its switch sets.
    expect(html).toContain('<span class="agent-settings-model">gpt-6.1-sol</span>');
    expect(html).toContain('<span class="agent-settings-model">claude-sonnet-5</span>');
    expect(html).toContain("default (haiku)");
  });

  it("drops the engine model selects, the other-jobs fold and the Grok scan switch", () => {
    const html = render(reply("session", { implementer: "codex", grok_scan: true }));
    expect(html).not.toContain("Implement model");
    expect(html).not.toContain("<details");
    expect(html).not.toContain("Grok scans");
    expect(html).not.toContain('type="checkbox"');
    expect(html.toLowerCase()).not.toContain("grok");
    expect(html).toContain("Subagent models");
    expect((html.match(/<select/g) || []).length).toBe(Object.keys(builtin.subagents).length);
  });

  it("shows the current engine's saved implement model", () => {
    const r = reply("session", { implementer: "codex", models: { codex_implement: "gpt-6-sol" } });
    expect(implementerModel(r, r.settings || {}, "codex")).toBe("gpt-6-sol");
    expect(implementerModel(r, r.settings || {}, "claude")).toBe("claude-sonnet-5-5");
  });

  it("names a session still on Grok and leaves both options unchecked", () => {
    const html = render(reply("session", { implementer: "grok" }));
    expect(html).not.toContain("checked");
    expect(html).toContain("set to Grok by an earlier release");
  });

  it("warns that a session pinned to a release before agent settings ignores them", () => {
    const html = render({ ...reply("session", { implementer: "codex" }), pinned_release: "3.87.0", applies: false });
    expect(html).toContain("runs plugin 3.87.0, which ignores agent settings");
    expect(render({ ...reply("session", {}), pinned_release: "3.113.2", applies: true })).not.toContain("ignores");
  });

  it("tells a pre-feature session that saving creates its file", () => {
    expect(render(reply("session", null))).toContain("Saving creates its settings");
    expect(render(reply("session", { implementer: "codex" }))).toContain("this session");
  });

  it("takes the switched engine and its saved implement model, keeping unsaved edits", () => {
    const draft = { implementer: "claude", models: { codex_plan: "edited" }, grok_scan: true };
    const saved = { implementer: "codex", models: { codex_implement: "gpt-6.1-sol", codex_plan: "old" } };
    expect(withSwitchedImplementer(draft, saved)).toEqual({
      implementer: "codex",
      models: { codex_plan: "edited", codex_implement: "gpt-6.1-sol" },
      grok_scan: true,
    });
    expect(withSwitchedImplementer(draft, null)).toBe(draft);
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
    const checked = host.querySelector('input[name="implementer"]:checked') as HTMLInputElement;
    expect(checked.value).toBe("codex");
    await act(async () => {
      (host.querySelector('button[type="submit"]') as HTMLButtonElement).click();
    });
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/agent-config");
    expect(JSON.parse(init.body)).toEqual({ sid: "lead-1", settings: { implementer: "codex" } });
    expect(host.textContent).toContain("Saved.");
  });

  it("changing the implementer runs the server switch at once", async () => {
    const loaded = reply("session", { implementer: "claude" });
    const switched = reply("session", { implementer: "codex", models: { codex_implement: "gpt-6.1-sol" } });
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => loaded });
    fetchMock.mockResolvedValueOnce({ ok: true, text: async () => JSON.stringify(switched) });
    await act(async () => root.render(<AgentSettings sid="lead-1" close={() => undefined} />));
    await act(async () => {
      (host.querySelector('input[value="codex"]') as HTMLInputElement).click();
    });
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/agent-config");
    expect(JSON.parse(init.body)).toEqual({ sid: "lead-1", implementer: "codex" });
    expect((host.querySelector('input[name="implementer"]:checked') as HTMLInputElement).value).toBe("codex");
    expect(host.textContent).toContain("Implementer: Codex.");
    expect(host.textContent).toContain("gpt-6.1-sol");
  });
});
