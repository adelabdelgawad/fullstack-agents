"""PreToolUse(ExitPlanMode) hook: in a herdr pane, presses "Yes, clear context" on the lead's HANDOFF RESUME plan."""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import context_handoff

MARKER = "HANDOFF RESUME"
MIN_THRESHOLD = 100_000
CARD = r"❯ 1\. Yes, clear context"
SLUG = re.compile(r'"slug":"([A-Za-z0-9_-]+)"')
TAIL_BYTES = 262_144


def _slug(transcript):
    try:
        with open(transcript, "rb") as stream:
            stream.seek(max(0, os.path.getsize(transcript) - TAIL_BYTES))
            found = SLUG.findall(stream.read().decode("utf-8", "replace"))
    except (OSError, TypeError):
        return None
    return found[-1] if found else None


def plan_text(hook, env):
    """The plan being approved: the tool input, else this session's own plan file."""
    plan = (hook.get("tool_input") or {}).get("plan")
    if plan:
        return plan
    slug = _slug(hook.get("transcript_path"))
    base = Path(env.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "plans"
    try:
        return (base / f"{slug}.md").read_text() if slug else ""
    except OSError:
        return ""


def is_handover(plan):
    return MARKER in next((line for line in plan.splitlines() if line.strip()), "")


def armed(hook, state_dir, env):
    """The herdr pane to approve in, or None; each handover ExitPlanMode call arms once."""
    pane = env.get("HERDR_PANE_ID")
    sid, call = hook.get("session_id"), hook.get("tool_use_id")
    if not pane or not sid or hook.get("agent_id") or env.get("FSA_AUTO_HANDOFF", "on") == "off":
        return None
    path = context_handoff.state_path(state_dir, sid)
    st = context_handoff._load(path)
    if "model" not in st or st.get("warned") != st.get("compactions") or (call and st.get("auto_call") == call):
        return None
    usage = context_handoff.usage
    if usage.handoff_at(usage.window_of(st["model"], st["context"]), st["compact_min"]) < MIN_THRESHOLD:
        return None
    if not is_handover(plan_text(hook, env)):
        return None
    st["auto_call"] = call
    context_handoff._save(path, st)
    return pane


def _herdr(env, *args, timeout=10):
    cmd = [env.get("HERDR_BIN_PATH") or "herdr", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def _screen(pane, env):
    return _herdr(env, "pane", "read", pane, "--source", "visible").stdout


def _press(pane, env, tries=3):
    """Send a carriage return while the card stays open; the card ignores keys that arrive as it renders."""
    for _ in range(tries):
        time.sleep(2)
        if not re.search(CARD, _screen(pane, env)):
            return True
        _herdr(env, "pane", "send-text", pane, "\r")
    time.sleep(3)
    return not re.search(CARD, _screen(pane, env))


def watch(pane, log, env, sid="", wait_ms=120_000):
    """Wait for the approval card of an already-checked handover plan, press Enter, record the outcome."""
    result = "no-card"
    if _herdr(env, "pane", "wait-output", pane, "--regex", CARD, "--source", "visible",
              "--timeout", str(wait_ms), timeout=wait_ms / 1000 + 10).returncode == 0:
        result = "approved" if _press(pane, env) else "card-still-open"
    entry = {"at": time.time(), "pane": pane, "session": sid, "result": result}
    if result != "approved":
        entry["screen"] = _screen(pane, env).rstrip().splitlines()[-8:]
    with open(log, "a") as stream:
        stream.write(json.dumps(entry) + "\n")
    return result


def main():
    if len(sys.argv) > 3 and sys.argv[1] == "watch":
        watch(sys.argv[2], sys.argv[3], os.environ, sys.argv[4] if len(sys.argv) > 4 else "")
        return
    try:
        hook = json.load(sys.stdin)
    except ValueError:
        return
    state_dir = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TMPDIR", "/tmp")
    pane = armed(hook, state_dir, os.environ)
    if pane:
        subprocess.Popen([sys.executable, "-I", __file__, "watch", pane, str(Path(state_dir) / "auto-handoff.log"),
                          hook.get("session_id", "")],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)


if __name__ == "__main__":
    main()
