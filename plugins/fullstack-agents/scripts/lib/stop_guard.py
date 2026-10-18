"""Deterministic turn-end guard: an answer or progress report never silently ends open ledger work."""
import json
import os
import re
import tempfile
from pathlib import Path

from task_tracking import SID, load_tasks

MAX_BLOCKS = 3
OPEN = ("in_progress", "pending")
PAUSE = re.compile(
    r"^\W*(stop|pause|halt|hold\s+on|cancel)\b"
    r"|\b(stop|pause|halt)\s+(the\s+)?(work|working|task|everything|all|now|here|there)\b"
    r"|\b(do\s+not|don'?t)\s+(continue|proceed)\b",
    re.IGNORECASE)
TRAILER = re.compile(r"^\W*(waiting\s+on|paused|blocked)\s*:\s*(.+)$", re.IGNORECASE)
ON_USER = re.compile(r"\b(you|user|your)\b", re.IGNORECASE)
# A closing line that asks the user to approve, decide or reply hands the turn over even without a '?'.
ASK = re.compile(r"^\W*(please\s+)?(approve|confirm|choose|decide|pick|reply|let me know|tell me)\b"
                 r"|\b(your|awaiting)\s+(approval|decision|go-?ahead|confirmation|choice)\b", re.IGNORECASE)


def _state_path(session_id):
    if not isinstance(session_id, str) or not SID.fullmatch(session_id):
        return None
    base = os.environ.get("FSA_STOP_GUARD_DIR") or "~/.local/state/fullstack-agents/stop-guard"
    return Path(base).expanduser() / (session_id + ".json")


def _load(path):
    try:
        state = json.loads(path.read_text())
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(path, state):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, suffix=".tmp") as stream:
            json.dump(state, stream)
        os.replace(stream.name, path)
    except OSError:
        pass


def record_prompt(session_id, prompt):
    """The latest genuine user prompt decides whether the user asked the work to pause."""
    path = _state_path(session_id)
    if path is None or not isinstance(prompt, str) or not prompt.strip():
        return
    if "SYSTEM NOTIFICATION - NOT USER INPUT" in prompt or "<task-notification>" in prompt:
        return
    _save(path, {"paused": bool(PAUSE.search(prompt.strip())), "blocks": 0, "signature": None})


def _releases(message, engine):
    """A final line naming what the turn waits on, or a closing question, legitimately ends the turn."""
    lines = [line.strip() for line in (message or "").splitlines() if line.strip()]
    if not lines:
        return False
    tail = lines[-1]
    trailer = TRAILER.match(tail)
    if trailer:
        # Codex is not woken by finishing workers, so only a wait on the user may end its turn.
        return engine != "codex" or trailer[1].lower() != "waiting on" or bool(ON_USER.search(trailer[2]))
    return tail.rstrip("*_`) ").endswith("?") or bool(ASK.search(tail))


def decide(session_id, cwd, message, engine):
    """Return the continuation reason when the turn must not end, else None."""
    if os.environ.get("FSA_STOP_GUARD", "on") == "off":
        return None
    path = _state_path(session_id)
    if path is None or not cwd:
        return None
    ledger = load_tasks(session_id, cwd)
    items = ledger.get("items") or []
    open_items = [item for item in items if item.get("status") in OPEN]
    state = _load(path)
    if not open_items or state.get("paused") or _releases(message, engine):
        return None
    signature = f"{ledger.get('updated')}:{json.dumps(ledger.get('counts'), sort_keys=True)}"
    blocks = state.get("blocks", 0) if state.get("signature") == signature else 0
    if blocks >= MAX_BLOCKS:
        return None
    _save(path, {**state, "blocks": blocks + 1, "signature": signature})
    ids = ", ".join(f"{item['id']} ({item['status']})" for item in open_items[:8])
    wait = ("wait for running workers inside this turn (wait_agent with a long timeout), never end the turn on them"
            if engine == "codex" else "a running background task may be named in 'Waiting on: <task>'")
    return (f"Open ledger tasks remain in {ledger.get('relative_file', 'the task ledger')}: {ids}. "
            "Answering a question or reporting progress does not end the work: continue with the next step now. "
            f"End the turn only when the ledger is done, or with a final line 'Waiting on: you - <decision>', "
            f"'Paused: <user instruction>' or 'Blocked: <cause>'; {wait}. Mark finished or abandoned tasks in the ledger.")
