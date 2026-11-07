"""One headless execution session: bounded processes, a spend watcher, stop-line handling and canned plan replies."""
import json
import re
import subprocess
import time
import uuid
from pathlib import Path

from common import kill_group, now, sweep
from measure import live_estimate

CANNED_REPLY = ("Proceed with the implementation plan within the recorded task scope, permissions, and remaining "
                "budget. Do not commit, push, merge, release, deploy, or expand access.")
MAX_REPLIES_PER_SESSION = 2
WAITING = re.compile(r"^\s*Waiting on:\s*(.+?)\s*$", re.MULTILINE)
STOPPED = re.compile(r"^\s*(Paused|Blocked):\s*(.+?)\s*$", re.MULTILINE)
APPROVAL = re.compile(r"\b(approv\w*|go[- ]ahead|proceed\w*|confirm\w*)\b", re.IGNORECASE)
PLAN = re.compile(r"\bplan\b", re.IGNORECASE)
FORBIDDEN = re.compile(
    r"\$|\b(permission\w*|credential\w*|token\w*|secret\w*|password\w*|keys?|login|auth\w*|budget\w*|spend\w*|"
    r"cost\w*|usd|paid|billing|transmi\w*|upload\w*|send\w*|share\w*|provider\w*|scope\w*|access\w*|allow\w*|"
    r"path\w*|network\w*|install\w*|push\w*|commit\w*|merg\w*|release\w*|deploy\w*|production|prod|migrat\w*|"
    r"restart\w*|reload\w*|delet\w*|remov\w*|sudo|decision\w*|choos\w*|choice\w*|which|options?|or)\b", re.IGNORECASE)


def plan_approval(text):
    """Only an unambiguous request to approve a plan qualifies; anything touching access, money or scope does not."""
    return bool(APPROVAL.search(text) and PLAN.search(text) and not FORBIDDEN.search(text))


def classify_stop(final_text):
    """(state, reason, reply_allowed) for a finished process, read from its last stop line."""
    waiting = WAITING.findall(final_text or "")
    stopped = STOPPED.findall(final_text or "")
    if waiting:
        line = waiting[-1]
        if not re.match(r"you\b", line, re.IGNORECASE):
            return "needs_human", f"waiting on a non-user dependency in a headless run: {line}", False
        questions = [q for q in (final_text or "").splitlines() if q.rstrip().endswith("?")]
        text = " ".join([line, *questions])
        return "needs_human", f"waiting on the user: {line}", plan_approval(text)
    if stopped:
        kind, why = stopped[-1]
        return "needs_human", f"{kind.lower()}: {why}", False
    return "succeeded", "session ended without a stop line", False


def parse_stream(log):
    init, result = None, None
    for line in Path(log).read_text(errors="replace").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "system" and d.get("subtype") == "init" and init is None:
            init = {k: d.get(k) for k in ("model", "cwd", "plugins", "agents", "skills", "memory_paths", "tools",
                                          "mcp_servers", "permissionMode", "claude_code_version", "apiKeySource")}
        elif d.get("type") == "result":
            result = d
    return init, result


class Limits:
    def __init__(self, deadline, budget_usd, prior_usd, poll_s=5.0):
        self.deadline, self.budget_usd, self.prior_usd, self.poll_s = deadline, budget_usd, prior_usd, poll_s

    def remaining_usd(self, spent):
        return max(self.budget_usd - self.prior_usd - spent, 0.0)


def _watch(proc, sb, limits):
    """Wait for the process; kill its group and every marked process on timeout or spend over budget."""
    while proc.poll() is None:
        if time.time() >= limits.deadline:
            reason = "timed_out"
        elif limits.remaining_usd(live_estimate(sb.root)) <= 0:
            reason = "budget_exhausted"
        else:
            time.sleep(limits.poll_s)
            continue
        kill_group(proc.pid)
        sweep(sb.marker)
        proc.wait()
        return reason
    return None


def _launch(sb, cwd, env, args, stdin_text, log):
    with open(log, "w") as out:
        proc = subprocess.Popen(["claude", *args], cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=out,
                                stderr=subprocess.STDOUT, start_new_session=True, text=True)
    proc.stdin.write(stdin_text)
    proc.stdin.close()
    return proc


def _one(sb, cwd, env, args, stdin_text, log, limits):
    proc = _launch(sb, cwd, env, args, stdin_text, log)
    try:
        killed = _watch(proc, sb, limits)
    except KeyboardInterrupt:
        kill_group(proc.pid)
        sweep(sb.marker)
        proc.wait()
        raise
    sweep(sb.marker, wait_s=1)
    init, result = parse_stream(log)
    return {"args": args, "log": str(log), "exit": proc.returncode, "killed": killed, "init": init,
            "result": result and {k: result.get(k) for k in ("subtype", "is_error", "terminal_reason", "num_turns",
                                                             "total_cost_usd", "session_id")},
            "final_text": (result or {}).get("result") or ""}


def _process_state(step):
    if step["killed"]:
        return step["killed"], f"runner stopped the session ({step['killed']})"
    result = step["result"]
    if result and str(result.get("subtype", "")).startswith("error_max_budget"):
        return "budget_exhausted", "CLI budget cap reached"
    if not result:
        return "failed", f"exit {step['exit']}, no result event"
    if step["exit"] != 0 or result.get("is_error"):
        return "failed", f"exit {step['exit']}, {result.get('subtype')}, {result.get('terminal_reason')}"
    return None, None


def run_session(sb, cwd, env, base_args, prompt, limits, log_dir, replies_left, record=None):
    """Run to a terminal state, auto-replying only to plan approvals; a given `record` is continued with `prompt`."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    if record is None:
        sid = str(uuid.uuid4())
        record = {"session_id": sid, "started": now(), "steps": [], "auto_replies": [], "state": None, "reason": None}
        args = [*base_args, "--session-id", sid]
    else:
        sid = record["session_id"]
        args = [*base_args, "--resume", sid]
    stdin_text = prompt
    try:
        while True:
            spent = live_estimate(sb.root)
            run_args = ["-p", *args, "--output-format", "stream-json", "--verbose",
                        "--max-budget-usd", f"{max(limits.remaining_usd(spent), 0.01):.2f}"]
            step = _one(sb, cwd, env, run_args, stdin_text, log_dir / f"step-{len(record['steps'])}.jsonl", limits)
            record["steps"].append(step)
            state, reason = _process_state(step)
            if state is None:
                state, reason, reply = classify_stop(step["final_text"])
                capped = len(record["auto_replies"]) >= MAX_REPLIES_PER_SESSION or replies_left <= 0
                if reply and not capped:
                    record["auto_replies"].append({"at": now(), "request": reason, "reply": CANNED_REPLY})
                    replies_left -= 1
                    stdin_text, args = CANNED_REPLY, [*base_args, "--resume", sid]
                    continue
                if reply and capped:
                    reason += " (canned-reply cap reached)"
            record.update(state=state, reason=reason)
            break
    except KeyboardInterrupt:
        record.update(state="interrupted", reason="runner received SIGINT")
        raise
    finally:
        record["ended"] = now()
    return record
