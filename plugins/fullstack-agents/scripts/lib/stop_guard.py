"""Deterministic turn-end guard: an answer or progress report never silently ends open ledger work."""
import json
import os
from pathlib import Path
import re
import tempfile
import time

from task_tracking import SID, load_tasks
import prompt_history
import task_rules

MAX_BLOCKS = 3
PAUSE = re.compile(
    r"^\W*(stop|pause|halt|hold\s+on|cancel)\b"
    r"|\b(stop|pause|halt)\s+(the\s+)?(work|working|task|everything|all|now|here|there)\b"
    r"|\b(do\s+not|don'?t)\s+(continue|proceed)\b",
    re.IGNORECASE)
TRAILER = re.compile(r"^\W*(waiting\s+on|paused|blocked)\s*:\s*(.+)$", re.IGNORECASE)
ON_USER = re.compile(r"\b(you|user|your)\b", re.IGNORECASE)
# The user's latest prompt approves work already proposed ("go ahead", "approved", "proceed ...").
APPROVAL = re.compile(r"\b(approved?|go ahead|proceed|lgtm|ship it|green ?light|sounds good|do it|"
                      r"you (may|can) (start|proceed|continue))\b", re.IGNORECASE)
# A sentence that negates, defers or questions its approval word is not an approval ("don't do it until I review",
# "is this approved?", "I will approve later"). Missing an approval only restores the plain release rules; a false
# one would keep the lead working on something the user has not approved, so ambiguity counts as no approval.
NOT_APPROVAL = re.compile(r"\?|n't\b|\b(not|no|never|wait|until|before|after|later|yet|unless|once|if|when|"
                          r"whether|why|how|what)\b", re.IGNORECASE)
HOLD = re.compile(r"\b(hold off|not yet|wait for me|do not start|don'?t start)\b", re.IGNORECASE)
SENTENCE = re.compile(r"(?<=[.!?;\n])\s*")
# After an approval, asking permission to start or continue the approved work is a re-ask, not a new decision.
PERMISSION = re.compile(r"\b(shall|should|can|may)\s+I\s+(start|begin|proceed|continue|go ahead|carry on|move on)\b"
                        r"|\b(do you want|would you like)\s+me\s+to\s+(start|begin|proceed|continue|go ahead|carry on|"
                        r"move on)\b|\bready\s+to\s+(start|begin|proceed|continue)\b", re.IGNORECASE)


def _approves(text):
    """True only when some sentence approves plainly and no sentence holds, negates or questions an approval."""
    sentences = [part.strip() for part in SENTENCE.split(text) if part.strip()]
    approving = [part for part in sentences if APPROVAL.search(part)]
    if not approving or HOLD.search(text) or PAUSE.search(text):
        return False
    return not any(NOT_APPROVAL.search(part) for part in approving)
# A closing line that asks the user to approve, decide or reply hands the turn over even without a '?'.
# Anchored to an actual request: a line that merely mentions approval ("committed per your approval") is not one.
ASK = re.compile(r"^\W*(please\s+)?(approve|confirm|choose|decide|let me know|tell me)\b"
                 r"|\b(needs?|awaiting|waiting (on|for)|pending)\s+(your\s+)?(approval|decision|go-?ahead|"
                 r"confirmation|choice)\b", re.IGNORECASE)


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
    """The latest genuine user prompt decides whether the user asked the work to pause; also feeds `resolve --quote`."""
    path = _state_path(session_id)
    if path is None or not isinstance(prompt, str) or not prompt.strip():
        return
    if "SYSTEM NOTIFICATION - NOT USER INPUT" in prompt or "<task-notification>" in prompt:
        return
    text = prompt.strip()
    _save(path, {"paused": bool(PAUSE.search(text)), "approved": _approves(text), "blocks": 0, "signature": None})
    prompt_history.record(session_id, text)


def _releases(message, engine, approved=False):
    """A final line naming what the turn waits on, or a closing question, legitimately ends the turn.
    An approval-style ask ("Approve the plan and I'll start") ends it only while approval is genuinely pending:
    after the user's latest prompt approved the work, asking again does not release open ledger rows."""
    lines = [line.strip() for line in (message or "").splitlines() if line.strip()]
    if not lines:
        return False
    tail = lines[-1]
    trailer = TRAILER.match(tail)
    if trailer:
        # Codex is not woken by finishing workers, so only a wait on the user may end its turn.
        return engine != "codex" or trailer[1].lower() != "waiting on" or bool(ON_USER.search(trailer[2]))
    if approved and (ASK.search(tail) or PERMISSION.search(tail)):
        return False
    return tail.rstrip("*_`) ").endswith("?") or bool(ASK.search(tail))


def _legacy_continuation(ledger, message, engine, approved):
    """Today's rule, unchanged for legacy ledgers and v2 ledgers whose blockers block is unreadable (§13.7)."""
    items = ledger.get("items") or []
    open_items = [item for item in items if item.get("status") in task_rules.HOLDS_TURN]
    if not open_items or _releases(message, engine, approved):
        return None
    ids = ", ".join(f"{item['id']} ({item['status']})" for item in open_items[:8])
    wait = ("wait for running workers inside this turn (wait_agent with a long timeout), never end the turn on them"
            if engine == "codex" else "a running background task may be named in 'Waiting on: <task>'")
    return (f"Open ledger tasks remain in {ledger.get('relative_file', 'the task ledger')}: {ids}. "
            "Answering a question or reporting progress does not end the work: continue with the next step now. "
            f"End the turn only when the ledger is done, or with a final line 'Waiting on: you - <decision>', "
            f"'Paused: <user instruction>' or 'Blocked: <cause>'; {wait}. Mark finished or abandoned tasks in the ledger.")


def _names_blocker(message, question):
    """A reply names a question by quoting its id or its text, whitespace-normalised (§13.4)."""
    text = message or ""
    if re.search(rf"\b{re.escape(question['id'])}\b", text, re.IGNORECASE):
        return True
    normalized = " ".join(question["text"].split())
    return bool(normalized) and normalized.lower() in " ".join(text.split()).lower()


def _v2_continuation(ledger, message):
    """§13.3/§13.4/§13.10: `executable` always holds the turn; `waiting_user` only names an unnamed question."""
    info = ledger["session_state"]
    state = info["state"]
    if state != "executable" and state != "waiting_user":
        return None
    if state == "executable":
        by_id = {item["id"]: item["status"] for item in ledger.get("items") or []}
        ids = ", ".join(f"{row} ({by_id.get(row, '?')})" for row in info["executable"][:8])
        return (f"Open ledger tasks remain in {ledger.get('relative_file', 'the task ledger')}: {ids}. "
                "Answering a question or reporting progress does not end the work: continue with the next step now. "
                "End the turn only when the ledger is done, or after recording a blocker with `fsa-task block` "
                "(--kind user/worker/external) that explains what the open rows actually wait on.")
    missing = [question for question in info["questions"] if not _names_blocker(message, question)]
    if not missing:
        return None
    question = missing[0]
    return f"state {question['id']}: {question['text']} — blocks {', '.join(question['rows'])} because {question['why']}"


def decide(session_id, cwd, message, engine, stop_hook_active=False):
    """Return a block reason, a release report mapping, or None."""
    if os.environ.get("FSA_STOP_GUARD", "on") == "off":
        return None
    path = _state_path(session_id)
    if path is None or not cwd:
        return None
    state = _load(path)
    if state.get("paused"):
        return None
    ledger = load_tasks(session_id, cwd)
    if ledger.get("format") == "v2" and "session_state" in ledger:
        continuation = _v2_continuation(ledger, message)
    else:
        continuation = _legacy_continuation(ledger, message, engine, bool(state.get("approved")))
    if continuation is None:
        return None
    signature = f"{ledger.get('updated')}:{json.dumps(ledger.get('counts'), sort_keys=True)}"
    no_progress = state.get("signature") == signature
    if stop_hook_active and no_progress:
        # No ledger change since the last continuation: a repeat stop attempt made no progress, so let it end
        # rather than looping forever. Real progress still falls through to the ordinary signature cap below.
        return _release_report(ledger)
    blocks = state.get("blocks", 0) if no_progress else 0
    if blocks >= MAX_BLOCKS:
        return _release_report(ledger)
    _save(path, {**state, "blocks": blocks + 1, "signature": signature})
    return continuation


def _release_report(ledger):
    info = ledger.get("session_state") or {}
    by_id = {item["id"]: item.get("status", "?") for item in ledger.get("items") or []}
    open_rows = [item for item in ledger.get("items") or [] if item.get("status") in task_rules.OPEN]
    rows = info.get("executable") or [item["id"] for item in open_rows]
    named = ", ".join(f"{row} ({by_id.get(row, '?')})" for row in rows[:8])
    message = (f"Stop guard released without progress: state {info.get('state', 'open')}; "
               f"open {named}; nothing was marked complete.")
    return {"systemMessage": message}


def _blocker_text(identifier, entry):
    if entry.get("kind") == "external" and entry.get("class") == "capacity":
        until = f" until {entry['until']}" if entry.get("until") else ""
        offer = f" ({entry['offer']})" if entry.get("offer") else ""
        return f"{identifier}: capacity {entry['engine']}{until}{offer}"
    return f"{identifier}: {entry.get('kind')} {entry.get('text')}"


def _overdue_capacity(blockers):
    now = time.time()
    for identifier, entry in sorted(blockers.items()):
        if entry.get("kind") == "external" and entry.get("class") == "capacity" and entry.get("until"):
            deadline = task_rules._epoch(entry["until"])
            if deadline is not None and deadline <= now:
                return identifier
    return None


def _failing_lines(session_id, ledger):
    from task_tracking import _load_binding, _read, _root
    import task_evidence
    record, _binding = _load_binding(session_id)
    root = _root(record["root"])
    path = Path(ledger["file"])
    text = _read(path)
    block = task_evidence.load_block(text)
    lines = []
    for item in ledger.get("items") or []:
        if item.get("parent") or item["status"] not in task_rules.OPEN:
            continue
        report = task_evidence.build_report(root, block, item["id"], ledger_path=path)
        if not report["ok"]:
            lines.extend(f"{item['id']}: {reason}" for reason in report["blocking"])
    return lines


def continuation_line(session_id, cwd):
    """One same-session continuation line for a bound v2 ledger that is not executable or has open blockers
    (§14.3 item 4, §14.6 item 4). Cached data only; any failure here must never surface to the caller."""
    try:
        ledger = load_tasks(session_id, cwd)
        if ledger.get("format") != "v2" or "session_state" not in ledger:
            return None
        info = ledger["session_state"]
        blockers = ledger.get("blockers") or {}
        if info["state"] == "executable" and not blockers:
            return None
        parts = [f"state {info['state']}"]
        blocker_texts = [_blocker_text(identifier, entry) for identifier, entry in sorted(blockers.items())]
        if blocker_texts:
            parts.append("blockers: " + "; ".join(blocker_texts))
        parts.extend(_failing_lines(session_id, ledger)[:3])
        overdue = _overdue_capacity(blockers)
        if overdue:
            parts.append(f"check capacity with fsa-usage before resolving {overdue}")
        return "; ".join(parts)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def phase_complete_refusal(tracked):
    """None when `phase complete` may proceed, else why not, naming the open rows or derived state (§13.4 item 3)."""
    if not tracked:
        return None
    if tracked.get("error"):
        return f"ledger is invalid: {tracked['error']}"
    open_ids = [item["id"] for item in tracked.get("items") or [] if item["status"] in task_rules.OPEN]
    if tracked.get("format") == "v2" and "session_state" in tracked:
        state = tracked["session_state"]["state"]
        if state == "done":
            return None
        return f"ledger state is {state} (open: {', '.join(open_ids) or 'none'})"
    if open_ids:
        return f"open rows remain: {', '.join(open_ids)}"
    return None
