#!/usr/bin/env python3
"""Codex lifecycle adapter: no classifier model, transcript scan or Claude hooks."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[1]


def shared_lib():
    """The bundle ships the shared helpers beside this script; the source tree keeps them in the plugin lib."""
    if not Path(__file__).with_name("stop_guard.py").is_file():
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins/fullstack-agents/scripts/lib"))


def guard():
    shared_lib()
    import stop_guard
    return stop_guard


def launcher_hint():
    """Claude audits run through the user's `cc` alias; a missing alias is relayed to the user up front."""
    shared_lib()
    import claude_cli
    try:
        claude_cli.argv()
        return ""
    except claude_cli.MissingAlias as error:
        return f"\n\nClaude launcher missing: {error} Tell the user this before any Claude audit."


def context(event, text):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))


def patch_paths(command):
    paths = []
    for line in command.splitlines():
        match = re.match(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$", line)
        if match:
            paths.append(match[1])
    return paths


def post(payload):
    command = payload.get("tool_input", {}).get("command", "")
    root = Path(payload.get("cwd", ".")).resolve()
    messages = []
    failed = False
    for raw in dict.fromkeys(patch_paths(command)):
        path = (root / raw).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            continue
        if path.suffix not in {".py", ".rs"}:
            continue
        # Use the nearest service directory for tool configuration.
        service = path.parent
        while service != root and not any((service / marker).exists() for marker in ("pyproject.toml", "Cargo.toml")):
            service = service.parent
        tool = "ruff" if path.suffix == ".py" else "rustfmt"
        local = service / ".venv/bin" / tool
        executable = str(local) if local.is_file() else shutil.which(tool)
        if not executable:
            messages.append(f"{raw}: {tool} unavailable; explicit project validation still required.")
            continue
        # Never fetch tools or mutate formatting from a feedback hook.
        if tool == "ruff":
            args = [executable, "check", "--output-format", "concise", "--", str(path)]
        else:
            # cargo fmt supplies the correct project edition; no guessed edition.
            messages.append(f"{raw}: run cargo fmt --all --check from {service} (plus the Rust quality gates).")
            continue
        try:
            result = subprocess.run(args, cwd=service, capture_output=True, text=True, timeout=20)
            if result.returncode:
                failed = True
                messages.append(f"{raw}: lint failed\n" + (result.stdout + result.stderr)[-4000:])
        except (OSError, subprocess.TimeoutExpired) as error:
            failed = True
            messages.append(f"{raw}: validation incomplete: {error}")
    if messages:
        output = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "\n".join(messages)}}
        if failed:
            output.update({"decision": "block", "reason": "Fix the reported lint failures and revalidate before audit."})
        print(json.dumps(output))


def main():
    try:
        payload = json.load(sys.stdin)
        mode = sys.argv[1]
        if mode == "start":
            launcher = launcher_hint()
            if payload.get("source") in {"resume", "compact"}:
                context("SessionStart", f"Fullstack Agents bundle: {BUNDLE}. Reuse cached profiles and loaded skill sections. Codex leads; Claude audits bounded diffs and returns repair scope. Resume fullstack-agents-task-flow; preserve existing authorization and run required checks." + launcher)
            else:
                context("SessionStart", f"Fullstack Agents bundle root: {BUNDLE}\n\n" + (BUNDLE / "AGENTS.md").read_text() + launcher)
        elif mode == "prompt":
            prompt = payload.get("prompt", "")
            guard().record_prompt(payload.get("session_id"), prompt)
            if any(marker in prompt for marker in ("SYSTEM NOTIFICATION - NOT USER INPUT", "<task-notification>")):
                return 0
            if len(prompt.split()) < 6:
                return 0
            context("UserPromptSubmit", "Codex leads: reuse the cached scan and skills, route by service/lane, search before bounded reads. Follow fullstack-agents-task-flow: investigate, plan, implement, validate, bounded read-only Opus audit, scoped Codex repair. Record actual phase transitions with scripts/phase.py from this bundle. For multi-step implementation, maintain and register a repository Markdown task list with scripts/tasks.py and update statuses for the dashboard Tasks section; complete only when the work is done. Do not add approval rounds for already authorized work.")
        elif mode == "post":
            post(payload)
        elif mode == "stop":
            reason = guard().decide(payload.get("session_id"), payload.get("cwd"),
                                    payload.get("last_assistant_message"), "codex")
            if reason:
                print(json.dumps({"decision": "block", "reason": reason}))
        else:
            raise ValueError("unknown hook mode")
    except (ValueError, OSError, KeyError, IndexError, TypeError, ImportError) as error:
        print(f"Fullstack Agents hook incomplete: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
