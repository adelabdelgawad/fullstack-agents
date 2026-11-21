"""Slash commands a Claude Code session offers, for the dashboard's chat box suggestions: Claude Code's built-in
commands, user and project commands and skills, and the commands and skills of every enabled plugin."""
import json
import os
from pathlib import Path

BUILTIN = {
    "add-dir": "Add a working directory", "agents": "Manage subagents", "clear": "Clear the conversation",
    "compact": "Compact the conversation, optionally with focus instructions", "config": "Open settings",
    "context": "Show context usage", "cost": "Show token usage and cost", "doctor": "Check the installation",
    "exit": "Exit Claude Code", "export": "Export the conversation", "help": "Show help", "hooks": "Manage hooks",
    "init": "Create a CLAUDE.md for this project", "login": "Sign in", "logout": "Sign out",
    "mcp": "Manage MCP servers", "memory": "Edit memory files", "model": "Choose the model",
    "permissions": "Manage tool permissions", "plugin": "Manage plugins", "reload-plugins": "Reload plugins",
    "resume": "Resume a conversation", "review": "Review a pull request", "rewind": "Rewind the conversation or code",
    "security-review": "Security review of pending changes", "status": "Show status", "statusline": "Set up the status line",
    "todos": "Show the todo list", "usage": "Show plan usage", "vim": "Toggle vim mode",
}
DESCRIPTION_MAX = 140


def _frontmatter(path):
    """`name` and `description` from a Markdown file's YAML front matter (simple one-line values only)."""
    try:
        lines = Path(path).read_text(errors="replace").splitlines()[:40]
    except OSError:
        return {}
    if not lines or lines[0].strip() != "---":
        return {}
    out = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        if key.strip() in ("name", "description") and value.strip():
            out[key.strip()] = value.strip().strip("\"'")
    return out


def _describe(path, fallback=""):
    text = _frontmatter(path).get("description") or fallback
    text = " ".join(text.split())
    return text if len(text) <= DESCRIPTION_MAX else text[: DESCRIPTION_MAX - 1] + "…"


def _commands(folder, prefix=""):
    root = Path(folder)
    found = []
    for path in sorted(root.rglob("*.md")) if root.is_dir() else []:
        name = ":".join(path.relative_to(root).with_suffix("").parts)
        found.append({"name": f"{prefix}{name}", "description": _describe(path)})
    return found


def _skills(folder, prefix=""):
    root = Path(folder)
    found = []
    for path in sorted(root.glob("*/SKILL.md")) if root.is_dir() else []:
        name = _frontmatter(path).get("name") or path.parent.name
        found.append({"name": f"{prefix}{name}", "description": _describe(path)})
    return found


def _plugins(home):
    """Install paths of the enabled plugins, keyed by plugin name."""
    try:
        installed = json.loads((home / "plugins/installed_plugins.json").read_text()).get("plugins") or {}
        enabled = json.loads((home / "settings.json").read_text()).get("enabledPlugins") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    paths = {}
    for key, entries in installed.items():
        if enabled.get(key) and isinstance(entries, list) and entries and entries[0].get("installPath"):
            paths[key.split("@", 1)[0]] = Path(entries[0]["installPath"])
    return paths


def discover(cwd="", home=None):
    """Every slash command a session in `cwd` offers, de-duplicated by name, sorted."""
    home = Path(home or os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude").expanduser()
    found = [{"name": name, "description": text} for name, text in BUILTIN.items()]
    found += _commands(home / "commands") + _skills(home / "skills")
    if cwd:
        found += _commands(Path(cwd) / ".claude/commands") + _skills(Path(cwd) / ".claude/skills")
    for plugin, path in _plugins(home).items():
        found += _commands(path / "commands", f"{plugin}:") + _skills(path / "skills", f"{plugin}:")
    unique = {item["name"]: item for item in found}
    return sorted(unique.values(), key=lambda item: item["name"])
