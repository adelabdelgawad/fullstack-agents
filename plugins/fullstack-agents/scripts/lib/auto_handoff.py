"""PreToolUse(ExitPlanMode) hook: in a herdr or tmux pane, presses "Yes, clear context" on the lead's HANDOFF RESUME plan."""
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
TAIL = ("--source", "recent", "--lines", "40")  # pane reads search the buffer tail, never the scrolled viewport
WIDE = ("--source", "recent-unwrapped", "--lines", "400")


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
    """The herdr or tmux pane to approve in, or None; each handover ExitPlanMode call arms once."""
    pane = env.get("HERDR_PANE_ID") or env.get("TMUX_PANE")
    sid, call = hook.get("session_id"), hook.get("tool_use_id")
    if not pane or not sid or hook.get("agent_id") or env.get("FSA_AUTO_HANDOFF", "on") == "off":
        return None
    path = context_handoff.state_path(state_dir, sid)
    st = context_handoff._load(path)
    noticed = st.get("compactions") in (st.get("warned"), st.get("plan_warned"))
    if "model" not in st or not noticed or (call and st.get("auto_call") == call):
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


def _is_tmux(pane):
    return pane.startswith("%")


def _tmux(env, *args, timeout=10):
    cmd = [env.get("FSA_TMUX_BIN") or "tmux", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def _screen(pane, env):
    if _is_tmux(pane):
        return _tmux(env, "capture-pane", "-p", "-J", "-t", pane, "-S", "-40").stdout
    return _herdr(env, "pane", "read", pane, *TAIL).stdout


def _send_enter(pane, env):
    if _is_tmux(pane):
        _tmux(env, "send-keys", "-t", pane, "Enter")
    else:
        _herdr(env, "pane", "send-text", pane, "\r")


def _press(pane, env, tries=3):
    """Send a carriage return while the card stays open; the card ignores keys that arrive as it renders."""
    for _ in range(tries):
        time.sleep(2)
        if not re.search(CARD, _screen(pane, env)):
            return True
        _send_enter(pane, env)
    time.sleep(3)
    return not re.search(CARD, _screen(pane, env))


def needle(plan):
    """The plan's last long line, rendered just above the card, marks this session's plan on screen."""
    line = next((line for line in reversed(plan.splitlines()[1:]) if len(line.strip()) >= 24), "")
    return " ".join(re.sub(r"[*`]", "", line).split())[:40]


def _json(proc):
    try:
        return json.loads(proc.stdout or "{}")
    except ValueError:
        return {}


def _live(pane, env):
    if _is_tmux(pane):
        proc = _tmux(env, "display-message", "-p", "-t", pane, "#{pane_id}")
        return proc.returncode == 0 and proc.stdout.strip() == pane
    proc = _herdr(env, "pane", "get", pane)
    return proc.returncode == 0 and "error" not in _json(proc)


def _shows(pane, mark, env):
    text = " ".join(_herdr(env, "pane", "read", pane, *WIDE).stdout.split())
    return bool(re.search(CARD, text)) and mark in text


def find_pane(mark, env, wait_ms, step=2):
    """The one claude pane showing the card beside this plan's mark; a daemon session's own pane id goes stale."""
    if not mark:
        return None, "pane-gone"
    for _ in range(max(1, wait_ms // (step * 1000))):
        panes = (_json(_herdr(env, "pane", "list")).get("result") or {}).get("panes") or []
        hits = [p["pane_id"] for p in panes if p.get("agent") == "claude" and _shows(p.get("pane_id", ""), mark, env)]
        if len(hits) > 1:
            return None, "ambiguous"
        if hits:
            return hits[0], "found"
        time.sleep(step)
    return None, "pane-gone"


def _wait_card(pane, env, wait_ms, step=1):
    for _ in range(max(1, wait_ms // (step * 1000))):
        if re.search(CARD, _screen(pane, env)):
            return True
        time.sleep(step)
    return False


def _approve(pane, env, wait_ms):
    if _is_tmux(pane):
        return ("approved" if _press(pane, env) else "card-still-open") if _wait_card(pane, env, wait_ms) else "no-card"
    if _herdr(env, "pane", "wait-output", pane, "--regex", CARD, *TAIL,
              "--timeout", str(wait_ms), timeout=wait_ms / 1000 + 10).returncode != 0:
        return "no-card"
    return "approved" if _press(pane, env) else "card-still-open"


def watch(pane, log, env, sid="", wait_ms=120_000, mark=""):
    """Wait for the approval card of an already-checked handover plan, press Enter, record the outcome."""
    entry, result = {"at": time.time(), "pane": pane, "session": sid}, "pane-gone"
    if not _live(pane, env) and not _is_tmux(pane):
        found, result = find_pane(mark, env, wait_ms)
        entry["resolved"] = found
        pane = found or pane
    result = _approve(pane, env, wait_ms) if _live(pane, env) else result
    entry["result"] = result
    if result != "approved":
        entry["screen"] = _screen(pane, env).rstrip().splitlines()[-8:]
    with open(log, "a") as stream:
        stream.write(json.dumps(entry) + "\n")
    return result


def main():
    if len(sys.argv) > 3 and sys.argv[1] == "watch":
        extra = sys.argv[4:] + ["", ""]
        watch(sys.argv[2], sys.argv[3], os.environ, extra[0], mark=extra[1])
        return
    try:
        hook = json.load(sys.stdin)
    except ValueError:
        return
    state_dir = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TMPDIR", "/tmp")
    pane = armed(hook, state_dir, os.environ)
    if pane:
        subprocess.Popen([sys.executable, "-I", __file__, "watch", pane, str(Path(state_dir) / "auto-handoff.log"),
                          hook.get("session_id", ""), needle(plan_text(hook, os.environ))],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)


if __name__ == "__main__":
    main()
