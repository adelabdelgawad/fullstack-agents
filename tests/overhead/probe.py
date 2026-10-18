#!/usr/bin/env python3
"""Overhead probe: what the plugin injects into the model's context and how long its hooks take.

Runs every hook exactly as hooks.json wires it (command, matcher, sync/async) against a project directory, with an
isolated TMPDIR so session flags start clean. Measures characters (the unit of Claude Code's 10,000-character
per-string hook cap) and UTF-8 bytes separately. Token figures are estimates (characters / 3.8), never measurements.

    python3 -I tests/overhead/probe.py --plugin plugins/fullstack-agents --project /path/to/repo [--json out.json]
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

HOOK_CAP = 10_000          # Claude Code: per additionalContext / stdout string, per hook command
CHARS_PER_TOKEN = 3.8      # estimate only

# Fixed prompt set, in session order (first-prompt-of-session effects are part of the measurement).
PROMPTS = [
    ("question", "what does the edit budget gate count?"),
    ("continue", "continue"),
    ("research", "do github and online research for plugins like this one and compare them"),
    ("small-edit", "rename the helper in hooks/lib.sh and update its three callers"),
    ("negated-deploy", "fix the flaky dashboard test; do not deploy and do not push"),
    ("mixed", "investigate why the users page is slow, then fix the cause"),
    ("pasted-report", "## Goal\nImplement the plan.\n## Constraints\n- No deployment, release or push.\n"
                      "- Keep the diff minimal.\n## Done when\n- Tests pass.\n" + "Context line about SQLx and Axum. " * 20),
    ("substantial", "implement the session-scoped edit budget across the gate, its tests and the task-flow guide, "
                    "with a regression test for concurrent sessions and session resume"),
]


def load_hooks(plugin):
    return json.loads((plugin / "hooks" / "hooks.json").read_text())["hooks"]


def clean_env(plugin, project, tmp):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("FSA_", "CLAUDE_CODE_SESSION", "KC_"))}
    env.update(CLAUDE_PLUGIN_ROOT=str(plugin), CLAUDE_PROJECT_DIR=str(project), TMPDIR=str(tmp),
               FSA_STATE_HOME=str(Path(tmp) / "state-home"))
    return env


def run_hook(command, payload, env, cwd):
    cmd = command.replace("${CLAUDE_PLUGIN_ROOT}", env["CLAUDE_PLUGIN_ROOT"])
    start = time.perf_counter()
    proc = subprocess.run(["bash", "-c", cmd], input=json.dumps(payload), capture_output=True, text=True,
                          env=env, cwd=cwd, timeout=60)
    return proc, (time.perf_counter() - start) * 1000


def context_strings(stdout):
    """The strings Claude Code would hand the model: additionalContext when JSON, else plain stdout."""
    text = stdout.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except ValueError:
        return [stdout]
    if not isinstance(data, dict):
        return [stdout]
    found = []
    hso = data.get("hookSpecificOutput") or {}
    if isinstance(hso.get("additionalContext"), str):
        found.append(hso["additionalContext"])
    if isinstance(data.get("systemMessage"), str):
        found.append(data["systemMessage"])
    return found


def measure_strings(strings):
    return [{"chars": len(s), "bytes": len(s.encode()), "over_cap": len(s) > HOOK_CAP} for s in strings]


def sync_hooks(hooks, event, tool=None):
    out = []
    for group in hooks.get(event, []):
        matcher = group.get("matcher")
        if tool and matcher and not re.fullmatch(matcher, tool):
            continue
        for hook in group["hooks"]:
            if not hook.get("async"):
                out.append(hook["command"])
    return out


def session_start(hooks, env, project, session):
    rows = []
    for command in sync_hooks(hooks, "SessionStart"):
        proc, ms = run_hook(command, {"session_id": session, "source": "startup", "cwd": str(project),
                                      "hook_event_name": "SessionStart"}, env, project)
        rows.append({"command": command.split("run-hook.cmd\"")[-1].strip(), "ms": round(ms),
                     "strings": measure_strings(context_strings(proc.stdout))})
    return rows


def prompts(hooks, env, project, session):
    rows = []
    for label, prompt in PROMPTS:
        strings, ms = [], 0.0
        for command in sync_hooks(hooks, "UserPromptSubmit"):
            proc, t = run_hook(command, {"session_id": session, "prompt": prompt, "cwd": str(project),
                                         "hook_event_name": "UserPromptSubmit"}, env, project)
            ms += t
            strings += context_strings(proc.stdout)
        total = sum(len(s) for s in strings)
        rows.append({"prompt": label, "chars": total, "bytes": sum(len(s.encode()) for s in strings), "ms": round(ms),
                     "text": "\n".join(strings)})
    return rows


def tool_latency(hooks, env, project, session, repeats=5):
    payloads = {
        "Bash": {"tool_name": "Bash", "tool_input": {"command": "ls"}},
        "Edit": {"tool_name": "Edit", "tool_input": {"file_path": str(project / "README.md"),
                                                     "old_string": "a", "new_string": "b"}},
        "Agent": {"tool_name": "Agent", "tool_input": {"subagent_type": "fullstack-agents:test-runner",
                                                       "prompt": "run x"}},
    }
    out = {}
    for tool, payload in payloads.items():
        payload = {**payload, "session_id": session, "cwd": str(project), "hook_event_name": "PreToolUse"}
        commands = sync_hooks(hooks, "PreToolUse", tool)
        totals = []
        for _ in range(repeats):
            totals.append(sum(run_hook(c, payload, env, project)[1] for c in commands))
        out[tool] = {"hooks": len(commands), "median_ms": round(statistics.median(totals))}
    return out


def frontmatter(text):
    if not text.startswith("---"):
        return {}
    block = text.split("---", 2)[1]
    fields, key = {}, None
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if m:
            key = m.group(1)
            fields[key] = m.group(2).strip().strip('"').strip("'")
        elif key and line.startswith((" ", "\t")):
            fields[key] += " " + line.strip()
    return fields


def skills(plugin):
    rows = []
    for path in sorted((plugin / "skills").glob("*/SKILL.md")):
        fm = frontmatter(path.read_text())
        if fm.get("disable-model-invocation") == "true":
            continue
        listed = (fm.get("description", "") + " " + fm.get("when_to_use", "")).strip()
        rows.append({"skill": path.parent.name, "chars": len(listed)})
    return rows


def static_context(plugin):
    lead = plugin / "agents" / "lead" / "fullstack-agent.md"
    return {"lead_prompt_chars": len(lead.read_text()) if lead.exists() else 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin", required=True, type=Path)
    ap.add_argument("--project", required=True, type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--repeats", type=int, default=5)
    args = ap.parse_args()
    plugin, project = args.plugin.resolve(), args.project.resolve()
    hooks = load_hooks(plugin)
    with tempfile.TemporaryDirectory() as tmp:
        env = clean_env(plugin, project, tmp)
        session = "probe-" + uuid.uuid4().hex[:12]
        report = {
            "plugin": str(plugin), "project": str(project),
            "session_start": session_start(hooks, env, project, session),
            "prompts": prompts(hooks, env, project, session),
            "tool_latency": tool_latency(hooks, env, project, session, args.repeats),
            "skills": skills(plugin),
            "static": static_context(plugin),
        }
    ss_chars = sum(s["chars"] for r in report["session_start"] for s in r["strings"])
    report["totals"] = {
        "session_start_chars": ss_chars,
        "session_start_bytes": sum(s["bytes"] for r in report["session_start"] for s in r["strings"]),
        "session_start_over_cap": any(s["over_cap"] for r in report["session_start"] for s in r["strings"]),
        "prompt_chars": sum(r["chars"] for r in report["prompts"]),
        "skill_description_chars": sum(r["chars"] for r in report["skills"]),
        "est_tokens_session_start": round(ss_chars / CHARS_PER_TOKEN),
        "est_tokens_prompts": round(sum(r["chars"] for r in report["prompts"]) / CHARS_PER_TOKEN),
        "est_tokens_lead_prompt": round(report["static"]["lead_prompt_chars"] / CHARS_PER_TOKEN),
    }
    if args.json:
        args.json.write_text(json.dumps(report, indent=1))
    t = report["totals"]
    print(f"session-start: {t['session_start_chars']} chars / {t['session_start_bytes']} bytes "
          f"(over cap: {t['session_start_over_cap']}) ~{t['est_tokens_session_start']} tok est")
    for r in report["session_start"]:
        print(f"  {r['command']:<28} {r['ms']:>5} ms  " + ", ".join(f"{s['chars']}c/{s['bytes']}b" for s in r["strings"]))
    print(f"prompts ({len(PROMPTS)}): {t['prompt_chars']} chars ~{t['est_tokens_prompts']} tok est")
    for r in report["prompts"]:
        print(f"  {r['prompt']:<15} {r['chars']:>5} chars {r['ms']:>5} ms")
    for tool, v in report["tool_latency"].items():
        print(f"PreToolUse {tool:<6} {v['hooks']} hooks, median {v['median_ms']} ms")
    print(f"skill descriptions: {t['skill_description_chars']} chars over {len(report['skills'])} skills")
    print(f"lead prompt: {report['static']['lead_prompt_chars']} chars ~{t['est_tokens_lead_prompt']} tok est")
    return 0


if __name__ == "__main__":
    sys.exit(main())
