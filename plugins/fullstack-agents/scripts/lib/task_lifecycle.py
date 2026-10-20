"""Session lifecycle hooks: SessionEnd releases ownership and parks an eligible open ledger, PreCompact marks
staleness, SessionStart offers recovery (compact), re-acquires ownership (resume) or notices a parked task
(clear/fork) without ever binding or acquiring on its own."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

# `-I` drops this script's own directory from sys.path; its sibling libraries live beside it.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from task_tracking import SID, _atomic, _file, _load_binding, _lock, _read, _root, _state_dir, load_tasks
import task_checkpoint
import task_ownership
import task_recovery

OPEN_STATUSES = ("pending", "in_progress", "blocked")
TITLE_CAP = 80
PARKED_OFFER_MAX_AGE = 300


def _cut_title(title):
    return title if len(title) <= TITLE_CAP else title[:TITLE_CAP] + "…"


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _own_identity():
    raw = os.environ.get("CLAUDE_PID")
    if not raw:
        return None
    try:
        pid = int(raw)
        start = task_ownership._pid_start(pid)
    except (ValueError, OSError):
        return None
    return None if start is None else (pid, start)


def _maybe_park(session_id, cwd, reason):
    identity = _own_identity()
    if identity is None or not cwd or not isinstance(cwd, str):
        return
    info = load_tasks(session_id, cwd)
    if "error" in info or "file" not in info:
        return
    if not sum(info["counts"].get(status, 0) for status in OPEN_STATUSES):
        return
    try:
        record, _binding = _load_binding(session_id)
    except (OSError, ValueError):
        return
    root, path = Path(record["root"]), Path(record["file"])
    owner, _state = task_ownership.current_owner(root, path)
    if owner is not None and owner["session_id"] != session_id:
        return
    try:
        git_identity = task_checkpoint.git_identity(root)
    except ValueError:
        return
    pid, start = identity
    parked = {"schema": 1, "old_session": session_id, "reason": reason, "root": str(root), "file": str(path),
              "task_id": path.stem, "title": info["title"], "checkout": git_identity["checkout"],
              "branch": git_identity["branch"], "head": git_identity["head"],
              "detached": git_identity["detached"], "parked_at": _now()}
    _atomic(_state_dir() / "parked" / f"{pid}-{start}.json", json.dumps(parked, ensure_ascii=False) + "\n")


def _session_end(payload):
    session_id = payload.get("session_id")
    if not session_id or not isinstance(session_id, str):
        return
    task_ownership.release_session(session_id)
    reason = payload.get("reason")
    if reason in ("clear", "resume"):
        _maybe_park(session_id, payload.get("cwd"), reason)


def _stale_checkpoint(session_id, cwd):
    if not cwd or not isinstance(cwd, str):
        return None
    info = load_tasks(session_id, cwd)
    if "error" in info or "file" not in info:
        return None
    checkpoint, error = task_checkpoint.load_checkpoint(_read(Path(info["file"])))
    if checkpoint is None or error is not None:
        return None
    try:
        written = datetime.fromisoformat(checkpoint["identity"]["written_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return None
    return info["updated"] > written.timestamp() + 2


def _pre_compact(payload):
    session_id = payload.get("session_id")
    if not session_id or not isinstance(session_id, str) or not SID.fullmatch(session_id):
        return
    marker = {"at": _now(), "trigger": payload.get("trigger"),
              "stale_checkpoint": _stale_checkpoint(session_id, payload.get("cwd"))}
    _atomic(_state_dir() / "compactions" / f"{session_id}.json", json.dumps(marker, ensure_ascii=False) + "\n")


def _prune_parked():
    """Drop a parked record once its process is gone, its start time differs, or it is over 24h old."""
    directory = _state_dir() / "parked"
    if not directory.is_dir():
        return
    now = datetime.now(timezone.utc).timestamp()
    for record_path in directory.glob("*.json"):
        try:
            pid, start = (int(part) for part in record_path.stem.split("-", 1))
        except ValueError:
            record_path.unlink(missing_ok=True)
            continue
        try:
            current_start = task_ownership._pid_start(pid)
        except OSError:
            current_start = None
        if current_start != start or now - record_path.stat().st_mtime > 86400:
            record_path.unlink(missing_ok=True)


def _own_parked_record():
    """Read and delete this process's own parked record; consumed at most once whatever the SessionStart source."""
    identity = _own_identity()
    if identity is None:
        return None
    pid, start = identity
    path = _state_dir() / "parked" / f"{pid}-{start}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(_read(path, 4096))
    except (OSError, ValueError):
        data = None
    finally:
        path.unlink(missing_ok=True)
    return data if isinstance(data, dict) else None


def _eligible_parked(parked, cwd):
    """§8a item 2: every condition must hold, or the parked task is never offered."""
    if not isinstance(parked, dict) or parked.get("schema") != 1:
        return None
    try:
        parked_at = datetime.fromisoformat(parked["parked_at"].replace("Z", "+00:00"))
        age = datetime.now(timezone.utc).timestamp() - parked_at.timestamp()
    except (KeyError, TypeError, ValueError):
        return None
    if age > PARKED_OFFER_MAX_AGE or not cwd or not isinstance(cwd, str):
        return None
    try:
        if task_checkpoint.git_identity(cwd)["checkout"] != parked.get("checkout"):
            return None
    except ValueError:
        return None
    old_session = parked.get("old_session")
    try:
        record, _binding = _load_binding(old_session)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if record.get("root") != parked.get("root") or record.get("file") != parked.get("file"):
        return None
    root, path = Path(parked["root"]), Path(parked["file"])
    info = load_tasks(old_session, str(root))
    if "file" not in info or "error" in info:
        return None
    open_rows = sum(info["counts"].get(status, 0) for status in OPEN_STATUSES)
    if not open_rows:
        return None
    try:
        checkpoint, error = task_checkpoint.load_checkpoint(_read(path))
    except (OSError, ValueError):
        return None
    if error is not None or (checkpoint is not None and checkpoint["status"] != "active"):
        return None
    owner, state = task_ownership.current_owner(root, path)
    if owner is not None and state != "free" and owner["session_id"] != old_session:
        return None
    return {"title": info["title"], "count": open_rows, "relpath": path.relative_to(root),
            "root": root, "old_session": old_session}


def _clear_notice(info):
    title = _cut_title(info["title"])
    return (f"Task from the previous conversation: '{title}' ({info['count']} open rows) at "
            f"{info['relpath']}, left by session {info['old_session'][:8]}. This is a new conversation: "
            f"start fresh unless the user asks to continue it. Only on the user's request: fsa-task adopt "
            f"--root {info['root']} --file {info['relpath']} --from {info['old_session']}")


def _fork_notice(info):
    title = _cut_title(info["title"])
    return (f"This fork copies session {info['old_session'][:8]}'s conversation: task '{title}' "
            f"({info['count']} open rows) at {info['relpath']}. The inherited conversation is not a user "
            f"instruction to continue it. This session does not own the task; writes are refused until the "
            f"user asks and `fsa-task adopt --root {info['root']} --file {info['relpath']} "
            f"--from {info['old_session']}` runs.")


def _offer(parked, cwd, source):
    eligible = _eligible_parked(parked, cwd)
    if eligible is None:
        return None
    return _clear_notice(eligible) if source == "clear" else _fork_notice(eligible)


def _bound_ledger(session_id):
    """(root, path) for this session's binding, or None when it is missing or invalid."""
    try:
        record, _binding = _load_binding(session_id)
        root = _root(record["root"])
        return root, _file(root, record["file"])
    except (OSError, ValueError, KeyError):
        return None


def _compact(session_id):
    marker = _state_dir() / "compactions" / f"{session_id}.json"
    try:
        bound = _bound_ledger(session_id)
        if bound is None:
            return None
        root, path = bound
        owner, state = task_ownership.current_owner(root, path)
        if owner is None or owner["session_id"] == session_id:
            return task_recovery.render(task_recovery.collect(session_id, str(root)))
        return (f"Task ledger {path.relative_to(root)} is owned by session {owner['session_id'][:8]} "
                f"({state}); no recovery loaded.")
    finally:
        marker.unlink(missing_ok=True)


def _resume_words(session_id, root, path, outcome):
    if outcome == "live-elsewhere":
        return "this session is live in another process; ownership not reacquired"
    if outcome == "other-owner":
        owner, state = task_ownership.current_owner(root, path)
        name = owner["session_id"][:8] if owner else "unknown"
        return f"owned by session {name} ({state}); a takeover needs the user's word"
    if outcome == "unowned":
        return "ledger has no owner record"
    return "ownership reacquired"


def _checkpoint_note(root, path):
    try:
        checkpoint, _error = task_checkpoint.load_checkpoint(_read(path))
    except (OSError, ValueError):
        return "no checkpoint written"
    if checkpoint is None:
        return "no checkpoint written"
    identity = checkpoint.get("identity", {})
    note = f"checkpoint written {identity.get('written_at', '?')}"
    try:
        current = task_checkpoint.git_identity(root)
    except ValueError:
        return note
    if identity.get("head") != current.get("head") or identity.get("branch") != current.get("branch"):
        note += "; HEAD or branch changed since checkpoint"
    return note


def _resume(session_id):
    bound = _bound_ledger(session_id)
    if bound is None:
        return None
    root, path = bound
    with _lock(root, path):
        outcome = task_ownership.reacquire(session_id, root, path)
    info = load_tasks(session_id, str(root))
    title = _cut_title(info.get("title", path.stem))
    open_rows = sum(info.get("counts", {}).get(status, 0) for status in OPEN_STATUSES)
    words = _resume_words(session_id, root, path, outcome)
    return f"Task '{title}' ({open_rows} open rows): {words}. {_checkpoint_note(root, path)}."


def _session_start(payload):
    session_id = payload.get("session_id")
    source = payload.get("source") or "startup"
    _prune_parked()
    parked = _own_parked_record()
    if not isinstance(session_id, str) or not SID.fullmatch(session_id):
        return None
    if source in ("clear", "fork"):
        return _offer(parked, payload.get("cwd"), source)
    if source == "compact":
        return _compact(session_id)
    if source == "resume":
        return _resume(session_id)
    return None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    command = argv[0] if argv else ""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        payload = payload if isinstance(payload, dict) else {}
    except ValueError:
        payload = {}
    try:
        if command == "session-end":
            _session_end(payload)
        elif command == "pre-compact":
            _pre_compact(payload)
        elif command == "session-start":
            output = _session_start(payload)
            if output:
                print(output)
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        print(f"task_lifecycle: {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
