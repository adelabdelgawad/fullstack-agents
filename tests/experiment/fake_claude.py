#!/usr/bin/env python3
"""Deterministic stand-in for the claude CLI; never calls a model. Behaviour per stage comes from FSA_FAKE_SCENARIO."""
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

FIXED = """def apply_discount(price, percent):
    return price * (100 - percent) / 100


def format_price(value):
    return f"{value:.2f}"
"""
WRONG = FIXED.replace("(100 - percent)", "(100 + percent)")
BROKEN = FIXED.replace('f"{value:.2f}"', 'str(value)')
USAGE = {"input_tokens": 10, "output_tokens": 1000, "cache_read_input_tokens": 5000,
         "cache_creation_input_tokens": 2000, "cache_creation": {"ephemeral_1h_input_tokens": 2000}}
COST = 10 * 2 / 1e6 + 1000 * 10 / 1e6 + 5000 * 0.2 / 1e6 + 2000 * 4 / 1e6


def opt(args, name):
    return args[args.index(name) + 1] if name in args else None


def modes(cwd):
    scenario = json.loads(Path(os.environ["FSA_FAKE_SCENARIO"]).read_text())
    match = re.search(r"/stages/([^/]+)/", cwd + "/")
    stage = match.group(1) if match else ""
    if os.environ.get("FSA_ROLE") == "implementer":
        return ["implementer_child"]
    return scenario.get(stage, scenario.get("default", ["fix"]))


def transcript(sid, cwd, model, n, extra_usage=None):
    slug = re.sub(r"[^A-Za-z0-9]", "-", cwd)
    path = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / slug / f"{sid}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        for i in range(n):
            msg = {"id": f"msg_{sid}_{i}_{time.time_ns()}", "model": model, "usage": extra_usage or USAGE,
                   "content": [{"type": "tool_use", "id": f"tu{i}", "name": "Bash", "input": {"command": "ls"}}]}
            fh.write(json.dumps({"type": "assistant", "message": msg}) + "\n")
    return path


def subagent(parent, model):
    """A subagent file repeating one parent message id (must not be double counted) plus one of its own."""
    lines = parent.read_text().splitlines()
    sub = parent.with_suffix("") / "subagents" / "agent-x.jsonl"
    sub.parent.mkdir(parents=True, exist_ok=True)
    own = {"type": "assistant", "isSidechain": True, "message": {"id": "msg_sub_own", "model": model, "usage": USAGE}}
    sub.write_text(lines[0] + "\n" + json.dumps(own) + "\n")


def child_claude(args, env):
    subprocess.run(["claude", *args], input="x", text=True, env={**os.environ, **env}, capture_output=True, check=False)


def implementation(m, resumed):
    if "ask_plan" in m and not resumed:
        return "Plan: change apply_discount.\nWaiting on: you - approve the plan"
    if "ask_plan_twice" in m:
        return "Revised plan.\nWaiting on: you - approve the plan"
    if "ask_permission" in m:
        return "Waiting on: you - grant access to the production database"
    target = Path("pricing.py")
    if "fix" in m:
        target.write_text(FIXED)
    if "wrong" in m:
        target.write_text(WRONG)
    if "break" in m:
        target.write_text(BROKEN)
    if "touch_eval" in m:
        Path("tests_eval").mkdir(exist_ok=True)
        Path("tests_eval/__init__.py").write_text("")
        Path("tests_eval/test_acceptance.py").write_text("import unittest\n\n\nclass A(unittest.TestCase):\n"
                                                        "    def test_ok(self):\n        pass\n")
    if "sentinel" in m:
        Path(os.environ["CLAUDE_CONFIG_DIR"], "SENTINEL").write_text("a")
        Path(os.environ["FSA_STATE_HOME"], "SENTINEL").write_text("a")
    if "peek" in m:
        stage = Path.cwd().parent
        targets = [stage.parent / "b-base/repo/pricing.py", stage.parent.parent / "arm.json",
                   stage.parent.parent.parent / "A/arm.json"]
        seen = {}
        for t in targets:
            try:
                t.read_text()
                seen[str(t)] = "read"
            except OSError:
                seen[str(t)] = "denied"
        (stage / "peek.json").write_text(json.dumps(seen))
    if "leak_token" in m:
        with open(opt(sys.argv[1:], "--debug-file"), "a") as fh:
            fh.write(f"env CLAUDE_CODE_OAUTH_TOKEN={os.environ.get('CLAUDE_CODE_OAUTH_TOKEN')}\n")
    return "Done."


def improver(m):
    ws = Path.cwd()
    skill = ws / "harness/skills/task-flow/SKILL.md"
    if "improve_ok" in m or "improve_leak" in m:
        word = "apply_discount" if "improve_leak" in m else "verification"
        skill.write_text(skill.read_text() + f"\nRun the focused {word} check before finishing.\n")
        (ws / "NOTES.md").write_text("edit: added a check line\ncue: no check ran\nlesson: run it\nevidence: b-base\n")
    if "improve_bad" in m:
        (ws / "harness/hooks/hooks.json").write_text("{}")
        (ws / "NOTES.md").write_text("bad edit\n")
    if "keep_base" in m:
        (ws / "NOTES.md").write_text("KEEP_BASE\n")
    return "Done."


def emit(obj):
    print(json.dumps(obj), flush=True)


def main():
    args, cwd = sys.argv[1:], os.getcwd()
    sys.stdin.read()
    m = modes(cwd)
    model = opt(args, "--model") or "claude-sonnet-5"
    if "--no-session-persistence" in args:
        emit({"type": "result", "is_error": False, "total_cost_usd": COST, "structured_output": {"x": 1},
              "modelUsage": {model: {"inputTokens": 10, "outputTokens": 1000, "cacheReadInputTokens": 5000,
                                     "cacheCreationInputTokens": 2000, "costUSD": COST}}})
        return 0
    sid = opt(args, "--session-id") or opt(args, "--resume") or str(uuid.uuid4())
    if opt(args, "--debug-file"):
        with open(opt(args, "--debug-file"), "a") as fh:
            if Path("AGENTS.md").is_file():
                fh.write(f"[DEBUG] Loaded project instructions {cwd}/AGENTS.md\n")
    plugin = opt(args, "--plugin-dir")
    emit({"type": "system", "subtype": "init", "model": model, "cwd": cwd, "session_id": sid,
          "plugins": [{"name": "fullstack-agents", "path": plugin}] if plugin else [],
          "memory_paths": {"auto": os.environ["CLAUDE_CONFIG_DIR"] + "/projects/x/memory/"},
          "permissionMode": "bypassPermissions"})
    if "fail" in m:
        print("engine crashed", file=sys.stderr)
        return 1
    if "sleep" in m:
        if "detach" in m:
            subprocess.Popen(["sleep", "300"], start_new_session=True)
        time.sleep(300)
    big = {**USAGE, "output_tokens": 2_000_000} if "expensive" in m else None
    path = transcript(sid, cwd, model, 2, big)
    if "expensive" in m:
        time.sleep(60)
    if "subagent" in m:
        subagent(path, model)
    if "classifier" in m:
        child_claude(["-p", "--no-session-persistence", "--output-format", "json"], {"FSA_CLASSIFIER_RUN": "1"})
    if "implementer" in m:
        child_claude(["-p", "--session-id", str(uuid.uuid4()), "--model", "claude-sonnet-5"], {"FSA_ROLE": "implementer"})
    text = improver(m) if plugin is None and "--tools" in args else implementation(m, "--resume" in args)
    result = {"type": "result", "subtype": "success", "is_error": False, "session_id": sid, "result": text,
              "num_turns": 3, "terminal_reason": "completed"}
    if "no_usage" not in m:
        result.update(total_cost_usd=COST * 2, modelUsage={model: {"costUSD": COST * 2}})
    emit(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
