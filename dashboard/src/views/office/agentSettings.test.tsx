// @vitest-environment jsdom
import { act } from "react-dom/test-utils";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AgentSettings, AgentSettingsForm, engineModelKeys, modelOptions, withSetting, type AgentConfigReply } from "./AgentSettings";

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
    expect(html).toContain("default (claude-sonnet-5)");
    expect(html).not.toContain('type="text"');
    expect(html).toContain("default (claude)");
    expect(html).toContain("default (haiku)");
  });

  it("shows only the chosen implementer's model fields", () => {
    expect(render(reply("default", null))).not.toContain("gpt-5.6-sol");
    const codex = render(reply("session", { implementer: "codex" }));
    expect(codex).toContain("default (gpt-5.6-sol)");
    expect(codex).not.toContain("claude-sonnet-5");
    expect(engineModelKeys(builtin.models, "codex")).toEqual(["codex_implement"]);
  });

  it("shows one implement model and folds the engine's other jobs away", () => {
    const r = { ...reply("session", { implementer: "codex" }),
      builtin: { ...builtin, models: { ...builtin.models, codex_investigate: "gpt-5.6-luna", codex_plan: "gpt-5.6-sol" } } };
    const html = render(r);
    const fold = html.indexOf("<details");
    expect(html.indexOf("Implement model")).toBeGreaterThan(-1);
    expect(html.indexOf("Implement model")).toBeLessThan(fold);
    expect(html.indexOf("Codex investigate")).toBeGreaterThan(fold);
    expect(html.indexOf("Codex plan")).toBeGreaterThan(fold);
    expect(render(reply("default", null))).not.toContain("<details");
  });

  it("offers the engine's models, keeping the built-in and a saved custom value", () => {
    expect(modelOptions(["a", "b"], "b", "custom")).toEqual(["a", "b", "custom"]);
    const r = { ...reply("session", { implementer: "codex", models: { codex_implement: "gpt-6-sol" } }),
      model_choices: { codex: ["gpt-6-sol", "gpt-6-luna"] } };
    const html = render(r);
    expect(html).toContain('<option value="gpt-6-luna">gpt-6-luna</option>');
    expect(html).toContain('<option value="gpt-6-sol" selected="">gpt-6-sol</option>');
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
