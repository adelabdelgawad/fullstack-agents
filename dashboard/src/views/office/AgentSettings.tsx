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
  /** Models offered per engine (claude, codex, grok). */
  model_choices?: Record<string, string[]>;
  /** The plugin release a session dispatches through (its pin); null when unknown. */
  pinned_release?: string | null;
  /** False when that release predates agent settings: saved values wait until the session re-pins. */
  applies?: boolean;
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

/** The engine's offered models with the built-in default and a saved value kept, without duplicates. */
export function modelOptions(choices: string[] | undefined, builtin: string, saved: string | undefined): string[] {
  return [...new Set([...(choices || []), builtin, ...(saved ? [saved] : [])])];
}

function configUrl(sid?: string) {
  return sid ? `/api/agent-config?sid=${encodeURIComponent(sid)}` : "/api/agent-config";
}

interface FormProps {
  reply: AgentConfigReply;
  draft: AgentSettingsValue;
  setDraft: (draft: AgentSettingsValue) => void;
}

function ModelField({ reply, draft, setDraft, engine, modelKey, label }: FormProps & ModelFieldProps) {
  const fallback = reply.builtin.models[modelKey];
  return (
    <label>
      {label}
      <select
        value={draft.models?.[modelKey] || ""}
        onChange={(event) => setDraft(withSetting(draft, "models", modelKey, event.target.value))}
      >
        <option value="">default ({fallback})</option>
        {modelOptions(reply.model_choices?.[engine], fallback, draft.models?.[modelKey]).map((model) => (
          <option key={model} value={model}>
            {model}
          </option>
        ))}
      </select>
    </label>
  );
}

interface ModelFieldProps {
  engine: string;
  modelKey: string;
  label: string;
}

function EngineFields(props: FormProps) {
  const { reply, draft, setDraft } = props;
  const { builtin } = reply;
  const engine = draft.implementer || builtin.implementer;
  const implementKey = `${engine}_implement`;
  const otherKeys = engineModelKeys(builtin.models, engine).filter((key) => key !== implementKey);
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
      {implementKey in builtin.models && (
        <ModelField {...props} engine={engine} modelKey={implementKey} label="Implement model" />
      )}
      {otherKeys.length > 0 && (
        <details className="agent-settings-more">
          <summary>Other {engine} jobs (scans, planning)</summary>
          {otherKeys.map((key) => (
            <ModelField key={key} {...props} engine={engine} modelKey={key} label={MODEL_LABELS[key] || key} />
          ))}
        </details>
      )}
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
      {reply.scope === "session" && reply.applies === false ? (
        <p className="agent-settings-note warn" role="alert">
          This session runs plugin {reply.pinned_release}, which ignores agent settings: its dispatches keep the
          environment&apos;s engine and models. Saved values apply once the session restarts or resumes
          (<code>claude --resume</code>) or hands off, which moves it to the installed release.
        </p>
      ) : reply.scope === "default" ? (
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
