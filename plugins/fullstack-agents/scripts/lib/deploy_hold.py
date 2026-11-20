"""Deploy hold: a user's "no deploy" is a candidate the lead turns into a `fsa-task control set --kind deploy_hold`
record (or lifts); this module only detects candidates and enforces active holds."""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import request_inbox
import task_controls

MARKER = "DEPLOY HOLD: active"
LIFT_MAX_CHARS = 400
PLAN_FRESH_S = 300
NEGATION = re.compile(r"\b(no|not|never|without|avoid|skip|hold)\b|n'?t\b", re.IGNORECASE)
LATER = re.compile(r"deploy\w*\s+(?:it\s+|them\s+|this\s+)?(?:later|tomorrow)\b", re.IGNORECASE)
UNDEPLOYED = re.compile(r"\bun-?deploy", re.IGNORECASE)
QUESTION_START = re.compile(r"^(did|does|is|are|was|were|why|what|how|can|could|should|will|would|has|have"
                            r"|which|where|who)\b", re.IGNORECASE)
INTERJECTION = re.compile(r"^\s*(no|nope|ok|okay|yes|yeah)\s*,\s*", re.IGNORECASE)
SENTENCE = re.compile(r"[^.!?;\n]+[.!?;\n]?")


def _classify_detail(prompt):
    """('hold'|'lift'|None, matching sentence or None) for one user prompt."""
    positive = None
    for raw in SENTENCE.findall(prompt):
        sentence = INTERJECTION.sub("", raw.strip())
        idx = sentence.lower().find("deploy")
        if idx < 0 or sentence.endswith("?") or QUESTION_START.match(sentence):
            continue
        if UNDEPLOYED.search(sentence) or LATER.search(sentence) or NEGATION.search(sentence[:idx]):
            return "hold", sentence
        positive = sentence
    return ("lift", positive) if positive and len(prompt) <= LIFT_MAX_CHARS else (None, None)


def classify(prompt):
    """'hold', 'lift' or None for one user prompt."""
    return _classify_detail(prompt)[0]


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


def set_hold(sid, quote, control_id=None):
    hold_dir().mkdir(parents=True, exist_ok=True)
    data = {"quote": quote[:160], "at": time.strftime("%Y-%m-%d %H:%M")}
    if control_id:
        data["control_id"] = control_id
    hold_path(sid).write_text(json.dumps(data))


def _context(event, text):
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}})


COORDINATION_ERRORS = (OSError, ValueError, KeyError, TypeError, RuntimeError)


def _hold_message(control):
    return (f'[fullstack-agents] Deploy hold {control["id"]} ({control["scope"]["level"]}): the user said '
            f'"{control["quote"]}". Deploy commands are blocked until the user tells you to deploy; do not plan, '
            f'offer or ask about a deploy, and a cross-host brief says deploy: no. A handover plan carries the '
            f'line `{MARKER}`.')


def _legacy_hold_message(held):
    return (f'[fullstack-agents] Deploy hold: the user said "{held["quote"]}" ({held["at"]}). Deploy commands are '
            f'blocked until the user tells you to deploy; do not plan, offer or ask about a deploy, and a '
            f'cross-host brief says deploy: no. A handover plan carries the line `{MARKER}`.')


def _lift_hint(control, rid, quote):
    return (f'[fullstack-agents] To lift deploy hold {control["id"]}: `fsa-task control lift --id {control["id"]} '
            f'--request {rid} --quote "{quote}"`.')


def on_prompt(hook):
    """Only detects a `deploy_hold` candidate from this prompt and reports any already-active hold; the lead
    alone turns a candidate into a hold (`fsa-task control set`) or lifts one (`fsa-task control lift`). Any
    coordination-log error is reported once on stderr and falls back to the legacy per-session hold file."""
    sid, prompt, cwd = hook.get("session_id"), (hook.get("prompt") or "").strip(), hook.get("cwd")
    if not sid or not prompt:
        return None
    rid, verdict, sentence, control = None, None, None, None
    if cwd:
        try:
            rid = request_inbox.capture(hook)
            verdict, sentence = _classify_detail(task_controls.strip_quoted(prompt))
            if rid is not None:
                is_marker_plan = prompt.startswith("Implement the following plan:") and MARKER in prompt
                if verdict == "hold" or is_marker_plan:
                    task_controls.record_candidate(cwd, sid, rid, "deploy_hold",
                                                    prompt.splitlines()[0] if is_marker_plan else (sentence or prompt))
            control = task_controls.active_deploy_hold(cwd, sid)
        except COORDINATION_ERRORS as error:
            print(f"deploy_hold: coordination log unavailable: {error}", file=sys.stderr)
    if control is not None:
        message = _hold_message(control)
        if verdict == "lift" and rid is not None and sentence and len(" ".join(sentence.split())) >= 8:
            message += "\n" + _lift_hint(control, rid, sentence)
        return _context("UserPromptSubmit", message)
    held = read_hold(sid)
    return _context("UserPromptSubmit", _legacy_hold_message(held)) if held else None


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


def _block_reason(cwd, sid):
    """An active control, an unresolved candidate (fail-closed, project-wide) or a legacy hold, in that order."""
    control = task_controls.active_deploy_hold(cwd, sid) if cwd else None
    if control is not None:
        return (f'[fullstack-agents] BLOCKED: deploy hold {control["id"]} ({control["scope"]["level"]}). The user '
                f'said "{control["quote"]}". Only the user lifts it (`fsa-task control lift`). Tell the user the '
                f'deploy is on hold; do not retry it or deploy another way.')
    candidate = task_controls.unresolved_project_candidate(cwd, "deploy_hold") if cwd else None
    if candidate is not None:
        return (f'[fullstack-agents] BLOCKED: a possible deploy hold ({candidate["request"]}: '
                f'"{candidate["sentence"]}") has not been classified. Resolve it with `fsa-task control set '
                f'--kind deploy_hold ...` or `fsa-task control dismiss --request {candidate["request"]} --kind '
                f'deploy_hold --reason ...` before deploying.')
    held = read_hold(sid) if sid else None
    if held:
        return (f'[fullstack-agents] BLOCKED: deploy hold. The user said "{held["quote"]}" ({held["at"]}). Only '
                f'the user lifts it. Tell the user the deploy is on hold; do not retry it or deploy another way.')
    return None


def on_bash(hook):
    """The deploy pattern is tested first: a non-matching command does no coordination-log work at all. For a
    matching command, any storage/lock/parse error blocks rather than letting the deploy through (fail closed)."""
    command = (hook.get("tool_input") or {}).get("command", "")
    if not command:
        return None
    pattern = deploy_regex(hook.get("cwd"))
    if not pattern or not re.search(pattern, command):
        return None
    try:
        return _block_reason(hook.get("cwd"), hook.get("session_id"))
    except COORDINATION_ERRORS as error:
        return (f"[fullstack-agents] BLOCKED: deploy hold state could not be read ({error}); refusing to deploy "
                f"until this is resolved.")


def latest_plan(now):
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "plans"
    plans = [p for p in base.glob("*.md") if now - p.stat().st_mtime < PLAN_FRESH_S] if base.is_dir() else []
    return max(plans, key=lambda p: p.stat().st_mtime) if plans else None


def on_plan(hook):
    sid, cwd = hook.get("session_id"), hook.get("cwd")
    if not sid:
        return None
    active = task_controls.active_deploy_hold(cwd, sid) if cwd else None
    if active is None and not read_hold(sid):
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
