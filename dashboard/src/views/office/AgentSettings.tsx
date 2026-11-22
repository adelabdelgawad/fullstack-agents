import { useEffect, useState } from "react";
import { getJson, postJson } from "../../lib/api";

/** Saved agent settings: a missing key means the built-in default. */
export interface AgentSettingsValue {
  implementer?: string;
  models?: Record<string, string>;
  grok_scan?: boolean;
  subagents?: Record<string, string>;
}

export interface AgentConfigReply {
  scope: "default" | "session";
  /** null: no file yet (a session that started before agent settings existed keeps the environment's choice). */
  settings: AgentSettingsValue | null;
  builtin: Required<AgentSettingsValue>;
  engines: string[];
  subagent_models: string[];
}

const MODEL_LABELS: Record<string, string> = {
  claude_implement: "Claude implement",
  codex_investigate: "Codex investigate",
  codex_plan: "Codex plan",
  codex_implement: "Codex implement",
  grok_investigate: "Grok investigate",
  grok_implement: "Grok implement",
};

/** The draft with one nested setting changed; an empty value removes it so the built-in default applies. */
export function withSetting(
  draft: AgentSettingsValue,
  group: "models" | "subagents",
  key: string,
  value: string,
): AgentSettingsValue {
  const next = { ...(draft[group] || {}) };
  if (value) next[key] = value;
  else delete next[key];
  return { ...draft, [group]: next };
}

/** The model settings of one engine: their keys start with the engine's name (claude_implement, codex_plan...). */
export function engineModelKeys(models: Record<string, string>, engine: string): string[] {
  return Object.keys(models).filter((key) => key.startsWith(`${engine}_`));
}

function configUrl(sid?: string) {
  return sid ? `/api/agent-config?sid=${encodeURIComponent(sid)}` : "/api/agent-config";
}

interface FormProps {
  reply: AgentConfigReply;
  draft: AgentSettingsValue;
  setDraft: (draft: AgentSettingsValue) => void;
}

function EngineFields({ reply, draft, setDraft }: FormProps) {
  const { builtin } = reply;
  const engine = draft.implementer || builtin.implementer;
  return (
    <fieldset className="agent-settings-group">
      <legend>Implementer</legend>
      <label>
        Engine
        <select
          value={draft.implementer || ""}
          onChange={(event) => setDraft({ ...draft, implementer: event.target.value || undefined })}
        >
          <option value="">default ({builtin.implementer})</option>
          {reply.engines.map((engine) => (
            <option key={engine} value={engine}>
              {engine}
            </option>
          ))}
        </select>
      </label>
      {engineModelKeys(builtin.models, engine).map((key) => (
        <label key={key}>
          {MODEL_LABELS[key] || key}
          <input
            type="text"
            value={draft.models?.[key] || ""}
            placeholder={builtin.models[key]}
            spellCheck={false}
            onChange={(event) => setDraft(withSetting(draft, "models", key, event.target.value.trim()))}
          />
        </label>
      ))}
      <label className="agent-settings-check">
        <input
          type="checkbox"
          checked={draft.grok_scan ?? builtin.grok_scan}
          onChange={(event) => setDraft({ ...draft, grok_scan: event.target.checked })}
        />
        Grok scans for wide investigations
      </label>
    </fieldset>
  );
}

function SubagentFields({ reply, draft, setDraft }: FormProps) {
  return (
    <fieldset className="agent-settings-group">
      <legend>Subagent models</legend>
      {Object.entries(reply.builtin.subagents).map(([name, fallback]) => (
        <label key={name}>
          {name}
          <select
            value={draft.subagents?.[name] || ""}
            onChange={(event) => setDraft(withSetting(draft, "subagents", name, event.target.value))}
          >
            <option value="">default ({fallback})</option>
            {reply.subagent_models.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </label>
      ))}
    </fieldset>
  );
}

/** The form itself, without loading or saving: the dialog below wraps it. */
export function AgentSettingsForm(props: FormProps) {
  const { reply } = props;
  return (
    <div className="agent-settings-form">
      {reply.scope === "default" ? (
        <p className="agent-settings-note">Applies to new sessions only. Running sessions keep their own settings.</p>
      ) : reply.settings === null ? (
        <p className="agent-settings-note">
          This session started before agent settings existed and follows the environment. Saving creates its settings
          file.
        </p>
      ) : (
        <p className="agent-settings-note">Applies to this session from its next dispatch or subagent call.</p>
      )}
      <EngineFields {...props} />
      <SubagentFields {...props} />
    </div>
  );
}

/** Load, edit and save the CTO default (no sid) or one session's agent settings. */
export function AgentSettings({ sid, close }: { sid?: string; close: () => void }) {
  const [reply, setReply] = useState<AgentConfigReply | null>(null);
  const [draft, setDraft] = useState<AgentSettingsValue>({});
  const [status, setStatus] = useState("");
  useEffect(() => {
    let live = true;
    getJson<AgentConfigReply>(configUrl(sid))
      .then((data) => {
        if (!live) return;
        setReply(data);
        setDraft(data.settings || {});
      })
      .catch(() => live && setStatus("Could not load the agent settings."));
    return () => {
      live = false;
    };
  }, [sid]);
  const save = async () => {
    setStatus("Saving…");
    try {
      const data = await postJson<AgentConfigReply>("/api/agent-config", { sid, settings: draft });
      if (data) setReply(data);
      setStatus("Saved.");
    } catch (error) {
      setStatus(`Not saved (${(error as Error).message}).`);
    }
  };
  if (!reply) return <p className="agent-settings-note">{status || "Loading…"}</p>;
  return (
    <form
      className="agent-settings"
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      <AgentSettingsForm reply={reply} draft={draft} setDraft={setDraft} />
      <div className="agent-settings-actions">
        <span role="status">{status}</span>
        <button type="button" onClick={() => setDraft({})}>
          Reset to built-in
        </button>
        <button type="button" onClick={close}>
          Cancel
        </button>
        <button type="submit">Save</button>
      </div>
    </form>
  );
}
