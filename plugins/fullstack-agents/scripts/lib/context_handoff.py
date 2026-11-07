"""PostToolUse hook: prints HANDOFF once per compaction cycle when the lead's context passes the checkpoint size."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usage

EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


def _load(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _save(path, state):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state))
    os.replace(tmp, path)


def state_path(state_dir, sid):
    return Path(state_dir) / f"handoff-{''.join(c for c in sid if c.isalnum() or c in '-_')}.json"


def notice(hook, state_dir):
    """The HANDOFF line to inject for this hook call, or None."""
    transcript, sid = hook.get("transcript_path"), hook.get("session_id")
    if hook.get("agent_id") or not transcript or not sid:
        return None
    state_file = state_path(state_dir, sid)
    saved = _load(state_file)
    st = usage.resume_scan(transcript, saved)
    if not st:
        return None
    at = usage.handoff_at(usage.window_of(st["model"], st["context"]), st["compact_min"])
    due = st["context"] >= at and saved.get("warned") != st["compactions"]
    st["warned"] = st["compactions"] if due else saved.get("warned")
    plan_adopt = None if due else _plan_due(hook, saved, st)
    if plan_adopt:
        st["plan_warned"] = st["compactions"]
    _save(state_file, {**saved, **st})
    if plan_adopt:
        return usage.plan_handoff_line(st["context"], plan_adopt)
    return usage.handoff_line(st["context"], at, _adopt(sid)) if due else None


def _plan_due(hook, saved, st):
    """The adopt command when a full-path task's first edit lands on a large context, once per cycle, else None."""
    at = usage.plan_handoff_at()
    if hook.get("tool_name") not in EDIT_TOOLS or at <= 0 or st["context"] < at:
        return None
    if st["compactions"] in (saved.get("plan_warned"), saved.get("warned")):
        return None
    return _adopt(hook["session_id"])


def _adopt(sid):
    """The `fsa-task adopt` command a fresh session runs to take over this session's ledger, or None."""
    import task_lifecycle
    bound = task_lifecycle._bound_ledger(sid)
    return task_lifecycle.adopt_command(bound[0], bound[1].relative_to(bound[0]), sid) if bound else None


def main():
    try:
        hook = json.load(sys.stdin)
    except ValueError:
        return
    line = notice(hook, sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TMPDIR", "/tmp"))
    if line:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": line}}))


if __name__ == "__main__":
    main()
