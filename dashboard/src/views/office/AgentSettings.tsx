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
  /** Engines the implementer switch offers (agent_config.IMPLEMENTER_PRESETS); each sets its own implement model. */
  implementer_choices?: string[];
  subagent_models: string[];
  /** Models offered per engine (claude, codex, grok). */
  model_choices?: Record<string, string[]>;
  /** Engine -> the implement model the implementer switch sets for it (read-only in the dialog). */
  implementer_models?: Record<string, string>;
  /** The plugin release a session dispatches through (its pin); null when unknown. */
  pinned_release?: string | null;
  /** False when that release predates agent settings: saved values wait until the session re-pins. */
  applies?: boolean;
}

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

function configUrl(sid?: string) {
  return sid ? `/api/agent-config?sid=${encodeURIComponent(sid)}` : "/api/agent-config";
}

interface FormProps {
  reply: AgentConfigReply;
  draft: AgentSettingsValue;
  setDraft: (draft: AgentSettingsValue) => void;
  /** Runs the implementer switch on the server (the same call as /fullstack-agents:implementer). */
  switchImplementer?: (engine: string) => void;
}

/** "codex" -> "Codex": display only. */
export function engineLabel(engine: string): string {
  return engine.charAt(0).toUpperCase() + engine.slice(1);
}

/** The draft after the server switched the implementer: its engine and that engine's saved implement model. */
export function withSwitchedImplementer(draft: AgentSettingsValue, saved: AgentSettingsValue | null): AgentSettingsValue {
  const engine = saved?.implementer;
  if (!engine) return draft;
  const key = `${engine}_implement`;
  const model = saved?.models?.[key];
  return { ...draft, implementer: engine, models: model ? { ...(draft.models || {}), [key]: model } : draft.models };
}

/** The implementer engines the Office offers (Codex, Claude), in the server's order. */
export function implementerChoices(reply: AgentConfigReply): string[] {
  return reply.implementer_choices || Object.keys(reply.implementer_models || {});
}

/** The implement model an engine uses: the session's saved one for its current engine, else the switch's preset. */
export function implementerModel(reply: AgentConfigReply, draft: AgentSettingsValue, engine: string): string {
  const key = `${engine}_implement`;
  if (engine === (draft.implementer || reply.builtin.implementer)) {
    return draft.models?.[key] || reply.builtin.models[key] || "";
  }
  return reply.implementer_models?.[engine] || reply.builtin.models[key] || "";
}

function ImplementerField({ reply, draft, setDraft, switchImplementer }: FormProps) {
  const engine = draft.implementer || reply.builtin.implementer;
  const choices = implementerChoices(reply);
  return (
    <fieldset className="agent-settings-group" role="radiogroup" aria-label="Implementer">
      <legend>Implementer</legend>
      {choices.map((choice) => (
        <label key={choice} className="agent-settings-choice">
          <input
            type="radio"
            name="implementer"
            value={choice}
            checked={engine === choice}
            onChange={() =>
              switchImplementer ? switchImplementer(choice) : setDraft({ ...draft, implementer: choice })
            }
          />
          <span>{engineLabel(choice)}</span>
          <span className="agent-settings-model">{implementerModel(reply, draft, choice)}</span>
        </label>
      ))}
      {!choices.includes(engine) && (
        <p className="agent-settings-note warn">
          This session is set to {engineLabel(engine)} by an earlier release; choose Codex or Claude.
        </p>
      )}
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
      <ImplementerField {...props} />
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
  const switchImplementer = async (engine: string) => {
    setStatus("Switching implementer…");
    try {
      const data = await postJson<AgentConfigReply>("/api/agent-config", { sid, implementer: engine });
      if (data) {
        setReply(data);
        setDraft((current) => withSwitchedImplementer(current, data.settings));
      }
      setStatus(`Implementer: ${engineLabel(engine)}.`);
    } catch (error) {
      setStatus(`Implementer not changed (${(error as Error).message}).`);
    }
  };
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
      <AgentSettingsForm
        reply={reply}
        draft={draft}
        setDraft={setDraft}
        switchImplementer={(engine) => void switchImplementer(engine)}
      />
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
