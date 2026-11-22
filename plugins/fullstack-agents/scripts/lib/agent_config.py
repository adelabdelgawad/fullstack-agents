"""Agent settings per session: implementer engine, engine models and subagent models.

The CTO default (default.json) is copied into a session's own file when the session starts, so a later change
to the default reaches only new sessions. A missing key means the built-in default. Values are validated on
every read and write; nothing here is ever evaluated as shell.

CLI (hooks and the dispatcher):
  agent_config.py snapshot <sid>        copy the default into the session file unless it exists
  agent_config.py env <sid>             KEY=value lines for codex-task.sh (only keys the session sets)
  agent_config.py hook                  PreToolUse Agent|Task: set the configured subagent model
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ENGINES = ("claude", "codex", "grok")
SUBAGENT_MODELS = ("haiku", "sonnet", "opus", "fable")
# Config key -> (dispatcher env var, built-in default shown in the Office as a placeholder).
MODELS = {
    "claude_implement": ("FSA_CLAUDE_MODEL_IMPLEMENT", "claude-sonnet-5"),
    "codex_investigate": ("FSA_CODEX_MODEL_INVESTIGATE", "gpt-5.6-luna"),
    "codex_plan": ("FSA_CODEX_MODEL_PLAN", "gpt-5.6-sol"),
    "codex_implement": ("FSA_CODEX_MODEL_IMPLEMENT", "gpt-5.6-sol"),
    "grok_investigate": ("FSA_GROK_MODEL_INVESTIGATE", "xai/grok-4.7"),
    "grok_implement": ("FSA_GROK_MODEL_IMPLEMENT", "xai/grok-4.7"),
}
SUBAGENTS = {"bounded-extractor": "haiku", "test-runner": "sonnet", "diff-reviewer": "sonnet", "web-researcher": "sonnet"}
BUILTIN = {"implementer": "claude", "models": {k: v[1] for k, v in MODELS.items()}, "grok_scan": False,
           "subagents": dict(SUBAGENTS)}
# Models offered in the Office per engine. Codex's own visible models (its model cache) replace the Codex list.
MODEL_CHOICES = {
    "claude": ["claude-sonnet-5", "claude-sonnet-5-5", "claude-opus-5", "claude-opus-5-5", "claude-haiku-5-5",
               "claude-fable-5-1"],
    "codex": ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"],
    "grok": ["xai/grok-4.7", "xai/grok-4.6", "xai/grok-4.5", "xai/grok-4.3"],
}
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:\[\]-]{0,79}$")
SID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def config_dir():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "fullstack-agents" / "agents"


def codex_models():
    """Model slugs Codex lists in its picker (~/.codex/models_cache.json), or [] when the cache is missing."""
    cache = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "models_cache.json"
    try:
        data = json.loads(cache.read_text())
    except (OSError, ValueError):
        return []
    models = data.get("models", data) if isinstance(data, dict) else data
    if not isinstance(models, list):
        return []
    return [m["slug"] for m in models if isinstance(m, dict) and m.get("visibility") == "list"
            and isinstance(m.get("slug"), str) and MODEL_RE.match(m["slug"])]


def model_choices():
    return {**MODEL_CHOICES, "codex": codex_models() or MODEL_CHOICES["codex"]}


def path_of(sid=None):
    if sid is None:
        return config_dir() / "default.json"
    if not SID_RE.match(sid):
        raise ValueError("bad session id")
    return config_dir() / f"session-{sid}.json"


def validate(cfg):
    """A normalized copy holding only valid, non-empty settings; ValueError names the first bad one."""
    if not isinstance(cfg, dict):
        raise ValueError("settings must be an object")
    out = {}
    if cfg.get("implementer"):
        if cfg["implementer"] not in ENGINES:
            raise ValueError("implementer must be one of " + ", ".join(ENGINES))
        out["implementer"] = cfg["implementer"]
    models = {}
    for key, value in (cfg.get("models") or {}).items():
        if key not in MODELS:
            raise ValueError(f"unknown model setting {key}")
        if value:
            if not isinstance(value, str) or not MODEL_RE.match(value):
                raise ValueError(f"bad model name for {key}")
            models[key] = value
    if models:
        out["models"] = models
    if cfg.get("grok_scan") is not None:
        out["grok_scan"] = bool(cfg["grok_scan"])
    subagents = {}
    for name, value in (cfg.get("subagents") or {}).items():
        if name not in SUBAGENTS:
            raise ValueError(f"unknown subagent {name}")
        if value:
            if value not in SUBAGENT_MODELS:
                raise ValueError("subagent model must be one of " + ", ".join(SUBAGENT_MODELS))
            subagents[name] = value
    if subagents:
        out["subagents"] = subagents
    return out


def load(sid=None):
    """The saved settings, or None when there is no file (a session that predates the feature)."""
    try:
        return validate(json.loads(path_of(sid).read_text()))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {}


def save(sid, cfg):
    clean = validate(cfg)
    target = path_of(sid)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".agents-")
    with os.fdopen(fd, "w") as fh:
        json.dump(clean, fh, indent=2)
    os.replace(tmp, target)
    return clean


def snapshot(sid):
    """Give a new session its own copy of the CTO default; an existing session file is never replaced."""
    if path_of(sid).exists():
        return load(sid)
    return save(sid, load() or {})


def env_lines(cfg):
    lines = []
    if cfg.get("implementer"):
        lines.append(f"FSA_IMPLEMENTER={cfg['implementer']}")
    for key, value in (cfg.get("models") or {}).items():
        lines.append(f"{MODELS[key][0]}={value}")
    if "grok_scan" in cfg:
        lines.append(f"FSA_GROK_INVESTIGATE={1 if cfg['grok_scan'] else 0}")
    return lines


def hook_output(event, cfg):
    """PreToolUse result that sets the configured model on an Agent call, or None to leave it alone."""
    tool_input = event.get("tool_input") or {}
    name = str(tool_input.get("subagent_type") or "").split(":")[-1]
    model = (cfg.get("subagents") or {}).get(name)
    if not model or tool_input.get("model") == model:
        return None
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                   "permissionDecisionReason": f"session agent settings: {name} runs on {model}",
                                   "updatedInput": {**tool_input, "model": model}}}


def main(argv):
    if argv[:1] == ["hook"]:
        try:
            event = json.load(sys.stdin)
            out = hook_output(event, load(str(event.get("session_id") or "")) or {})
        except (ValueError, TypeError, AttributeError):
            return 0
        if out:
            print(json.dumps(out))
        return 0
    if len(argv) == 2 and argv[0] in ("snapshot", "env"):
        try:
            cfg = snapshot(argv[1]) if argv[0] == "snapshot" else load(argv[1]) or {}
        except (OSError, ValueError) as exc:
            print(f"agent_config: {exc}", file=sys.stderr)
            return 1
        if argv[0] == "env":
            print("\n".join(env_lines(cfg)))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
