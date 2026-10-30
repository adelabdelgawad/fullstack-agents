"""Deploy hold: a user's "no deploy" blocks the project's deploy commands for that session until the user says deploy."""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

MARKER = "DEPLOY HOLD: active"
LIFT_MAX_CHARS = 400
PLAN_FRESH_S = 300
NOT_FROM_USER = ("Another Claude session sent a message", "<teammate-message", "<task-notification",
                 "[SYSTEM NOTIFICATION")
NEGATION = re.compile(r"\b(no|not|never|without|avoid|skip|hold)\b|n'?t\b", re.IGNORECASE)
LATER = re.compile(r"deploy\w*\s+(?:it\s+|them\s+|this\s+)?(?:later|tomorrow)\b", re.IGNORECASE)
UNDEPLOYED = re.compile(r"\bun-?deploy", re.IGNORECASE)
QUESTION_START = re.compile(r"^(did|does|is|are|was|were|why|what|how|can|could|should|will|would|has|have"
                            r"|which|where|who)\b", re.IGNORECASE)
INTERJECTION = re.compile(r"^\s*(no|nope|ok|okay|yes|yeah)\s*,\s*", re.IGNORECASE)
SENTENCE = re.compile(r"[^.!?;\n]+[.!?;\n]?")


def classify(prompt):
    """'hold', 'lift' or None for one user prompt."""
    positive = False
    for raw in SENTENCE.findall(prompt):
        sentence = INTERJECTION.sub("", raw.strip())
        idx = sentence.lower().find("deploy")
        if idx < 0 or sentence.endswith("?") or QUESTION_START.match(sentence):
            continue
        if UNDEPLOYED.search(sentence) or LATER.search(sentence) or NEGATION.search(sentence[:idx]):
            return "hold"
        positive = True
    return "lift" if positive and len(prompt) <= LIFT_MAX_CHARS else None


def hold_dir():
    base = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return Path(base) / "fullstack-agents" / "deploy-holds"


def hold_path(sid):
    return hold_dir() / f"{''.join(c for c in sid if c.isalnum() or c in '-_')}.json"


def read_hold(sid):
    try:
        return json.loads(hold_path(sid).read_text())
    except (OSError, ValueError):
        return None


def set_hold(sid, quote):
    hold_dir().mkdir(parents=True, exist_ok=True)
    hold_path(sid).write_text(json.dumps({"quote": quote[:160], "at": time.strftime("%Y-%m-%d %H:%M")}))


def _context(event, text):
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}})


def on_prompt(hook):
    sid, prompt = hook.get("session_id"), (hook.get("prompt") or "").strip()
    if not sid or not prompt:
        return None
    verdict = classify(prompt)
    if verdict == "lift" and any(m in prompt for m in NOT_FROM_USER):
        verdict = None
    if prompt.startswith("Implement the following plan:") and MARKER in prompt:
        verdict = "hold"
    if verdict == "hold":
        set_hold(sid, prompt.splitlines()[0] if MARKER in prompt else prompt)
    elif verdict == "lift" and read_hold(sid):
        hold_path(sid).unlink(missing_ok=True)
        return _context("UserPromptSubmit", "[fullstack-agents] Deploy hold lifted by this prompt.")
    held = read_hold(sid)
    if not held:
        return None
    return _context("UserPromptSubmit", f'[fullstack-agents] Deploy hold: the user said "{held["quote"]}" '
                    f'({held["at"]}). Deploy commands are blocked until the user tells you to deploy; do not plan, '
                    f'offer or ask about a deploy, and a cross-host brief says deploy: no. A handover plan carries '
                    f'the line `{MARKER}`.')


def deploy_regex(cwd):
    if os.environ.get("FSA_TEAM_DEPLOY_REGEX"):
        return os.environ["FSA_TEAM_DEPLOY_REGEX"]
    top = subprocess.run(["git", "-C", cwd or ".", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                         check=False).stdout.strip()
    try:
        for line in (Path(top or cwd or ".") / ".claude" / "fsa-team.conf").read_text().splitlines():
            if line.startswith("deploy_regex="):
                return line.split("=", 1)[1]
    except OSError:
        pass
    return None


def on_bash(hook):
    sid = hook.get("session_id")
    held = read_hold(sid) if sid else None
    command = (hook.get("tool_input") or {}).get("command", "")
    pattern = deploy_regex(hook.get("cwd")) if held and command else None
    if not pattern or not re.search(pattern, command):
        return None
    return (f'[fullstack-agents] BLOCKED: deploy hold. The user said "{held["quote"]}" ({held["at"]}). Only the '
            f'user lifts it. Tell the user the deploy is on hold; do not retry it or deploy another way.')


def latest_plan(now):
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "plans"
    plans = [p for p in base.glob("*.md") if now - p.stat().st_mtime < PLAN_FRESH_S] if base.is_dir() else []
    return max(plans, key=lambda p: p.stat().st_mtime) if plans else None


def on_plan(hook):
    sid = hook.get("session_id")
    if not sid or not read_hold(sid):
        return None
    plan = (hook.get("tool_input") or {}).get("plan")
    if plan is None:
        path = latest_plan(time.time())
        plan = path.read_text() if path else ""
    if "HANDOFF RESUME" not in plan or MARKER in plan:
        return None
    return f"[fullstack-agents] BLOCKED: a deploy hold is active; add the line `{MARKER}` to the handover plan."


def main():
    try:
        hook = json.load(sys.stdin)
    except ValueError:
        return 0
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "prompt":
        out = on_prompt(hook)
        if out:
            print(out)
        return 0
    reason = on_bash(hook) if mode == "bash" else on_plan(hook) if mode == "plan" else None
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
