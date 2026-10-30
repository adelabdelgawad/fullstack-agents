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
PLAN_PATH = re.compile(r"ctrl\+g to edit in \S+ · (\S+\.md)")


def armed(hook, state_dir, env):
    """The herdr pane to approve in, or None; claims this compaction cycle so it fires once."""
    pane = env.get("HERDR_PANE_ID")
    sid = hook.get("session_id")
    if not pane or not sid or hook.get("agent_id") or env.get("FSA_AUTO_HANDOFF", "on") == "off":
        return None
    path = context_handoff.state_path(state_dir, sid)
    st = context_handoff._load(path)
    cycle = st.get("compactions")
    if "model" not in st or st.get("warned") != cycle or st.get("auto_cycle") == cycle:
        return None
    usage = context_handoff.usage
    at = usage.handoff_at(usage.window_of(st["model"], st["context"]), st["compact_min"])
    if at < MIN_THRESHOLD or st["context"] < at:
        return None
    st["auto_cycle"] = cycle
    context_handoff._save(path, st)
    return pane


def _herdr(env, *args, timeout=10):
    cmd = [env.get("HERDR_BIN_PATH") or "herdr", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def _is_handover_plan(screen):
    match = PLAN_PATH.search(screen)
    if not match:
        return False
    try:
        lines = Path(match.group(1)).expanduser().read_text().splitlines()
    except OSError:
        return False
    return MARKER in next((line for line in lines if line.strip()), "")


def _press(pane, env, tries=3):
    """Send a carriage return while the card stays open; the card ignores keys that arrive as it renders."""
    for _ in range(tries):
        time.sleep(2)
        if not re.search(CARD, _herdr(env, "pane", "read", pane, "--source", "visible").stdout):
            return True
        _herdr(env, "pane", "send-text", pane, "\r")
    time.sleep(3)
    return not re.search(CARD, _herdr(env, "pane", "read", pane, "--source", "visible").stdout)


def watch(pane, log, env, wait_ms=120_000):
    """Wait for the approval card, check the plan file's first line, press Enter, record the outcome."""
    result = "no-card"
    if _herdr(env, "pane", "wait-output", pane, "--regex", CARD, "--source", "visible",
              "--timeout", str(wait_ms), timeout=wait_ms / 1000 + 10).returncode == 0:
        screen = _herdr(env, "pane", "read", pane, "--source", "visible").stdout
        result = "not-a-handover-plan"
        if re.search(CARD, screen) and _is_handover_plan(screen):
            result = "approved" if _press(pane, env) else "card-still-open"
    with open(log, "a") as stream:
        stream.write(json.dumps({"at": time.time(), "pane": pane, "result": result}) + "\n")
    return result


def main():
    if len(sys.argv) > 3 and sys.argv[1] == "watch":
        watch(sys.argv[2], sys.argv[3], os.environ)
        return
    try:
        hook = json.load(sys.stdin)
    except ValueError:
        return
    state_dir = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TMPDIR", "/tmp")
    pane = armed(hook, state_dir, os.environ)
    if pane:
        subprocess.Popen([sys.executable, "-I", __file__, "watch", pane, str(Path(state_dir) / "auto-handoff.log")],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)


if __name__ == "__main__":
    main()
