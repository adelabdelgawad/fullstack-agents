"""One owner record per task ledger, computed liveness via /proc, never trusting a bare PID."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import time

from task_tracking import _atomic, _lock, _read, _state_dir


def ancestors(pid=None):
    """Ancestor pids of `pid` (default: this process), nearest parent first, at most 64 steps."""
    chain = []
    current = pid if pid is not None else os.getpid()
    for _ in range(64):
        try:
            with open(f"/proc/{current}/stat") as stream:
                fields = stream.read().rsplit(")", 1)[-1].split()
        except OSError:
            break
        if len(fields) < 2:
            break
        parent = int(fields[1])
        if parent <= 0:
            break
        chain.append(parent)
        if parent == 1:
            break
        current = parent
    return chain


def _is_codex(pid):
    """True when `pid`'s argv[0] or argv[1] basename is "codex"."""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as stream:
            argv = stream.read().split(b"\0")
    except OSError:
        return False
    return any(Path(arg.decode(errors="ignore")).name == "codex" for arg in argv[:2] if arg)


REQUIRED = ("session_id", "claude_pid", "pid_start", "host", "checkout", "file", "acquired_at")


def _record_path(root, path):
    key = hashlib.sha256(f"{root}\0{path}".encode()).hexdigest()
    return _state_dir() / "owners" / (key + ".json")


def _pid_start(pid):
    with open(f"/proc/{pid}/stat") as stream:
        stat = stream.read()
    fields = stat.rsplit(")", 1)[-1].split()
    return int(fields[19]) if len(fields) > 19 else None


def _identity(root):
    claude_pid = int(os.environ["CLAUDE_PID"]) if os.environ.get("CLAUDE_PID") else None
    pid = claude_pid if claude_pid is not None and claude_pid in (os.getpid(), *ancestors()) else os.getppid()
    return pid, _pid_start(pid), socket.gethostname(), str(root)


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _age(acquired_at):
    try:
        parsed = datetime.fromisoformat(acquired_at.replace("Z", "+00:00"))
        seconds = max(0, time.time() - parsed.timestamp())
    except (AttributeError, TypeError, ValueError):
        return "unknown age"
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}m"
    return f"{int(seconds / 3600)}h"


def _validate(record):
    if not isinstance(record, dict) or not all(key in record for key in REQUIRED):
        raise ValueError("Malformed owner record")


def owner_state(record):
    """free | live | stale | unknown; the PID alone is never trusted, only PID + start time."""
    _validate(record)
    if record.get("released_at"):
        return "free"
    if record["host"] != socket.gethostname():
        return "unknown"
    try:
        start = _pid_start(record["claude_pid"])
    except FileNotFoundError:
        return "stale"
    except OSError:
        return "unknown"
    return "live" if start == record["pid_start"] else "stale"


def _read_record(record_path):
    if not record_path.exists():
        return None
    try:
        record = json.loads(_read(record_path, 16384))
    except (OSError, ValueError) as error:
        raise ValueError(f"Malformed owner record: {error}") from error
    _validate(record)
    return record


def acquire(session_id, root, path, takeover=None):
    """Under the caller's (root, path) lock: write, or refuse naming owner/state/expected (CAS by session id)."""
    record_path = _record_path(root, path)
    current = _read_record(record_path)
    other = current is not None and current["session_id"] != session_id
    state = owner_state(current) if current is not None else "free"
    contested = other and state in ("live", "stale", "unknown")
    if contested and takeover != current["session_id"]:
        expected = current["session_id"]
        got = "" if takeover is None else f" (got {takeover!r})"
        raise ValueError(f"Ledger owned by session {expected} on {current['host']} "
                          f"({state}, acquired {_age(current['acquired_at'])} ago); "
                          f"--takeover {expected} needs the user's confirmation{got}")
    pid, pid_start, host, checkout = _identity(root)
    record = {"session_id": session_id, "claude_pid": pid, "pid_start": pid_start, "host": host,
              "checkout": checkout, "file": str(path), "acquired_at": _now(), "released_at": None}
    if contested:
        record["previous"] = current
    _atomic(record_path, json.dumps(record, ensure_ascii=False) + "\n")
    return record


def current_owner(root, path):
    """Return (record, state); state is "free" with record None when there is no owner record."""
    record = _read_record(_record_path(root, path))
    if record is None:
        return None, "free"
    return record, owner_state(record)


def release(session_id, root, path):
    """Return True when this session's record, held by this exact (claude_pid, pid_start), was released."""
    record_path = _record_path(root, path)
    current = _read_record(record_path)
    if current is None or current["session_id"] != session_id or current.get("released_at"):
        return False
    pid, pid_start, _host, _checkout = _identity(root)
    if (current["claude_pid"], current["pid_start"]) != (pid, pid_start):
        return False
    current["released_at"] = _now()
    _atomic(record_path, json.dumps(current, ensure_ascii=False) + "\n")
    return True


def release_session(session_id):
    """Release every owner record this session holds; an unreadable record is skipped, never raised."""
    released = []
    directory = _state_dir() / "owners"
    if not directory.is_dir():
        return released
    for record_path in sorted(directory.glob("*.json")):
        try:
            current = _read_record(record_path)
        except ValueError:
            continue
        if current is None or current["session_id"] != session_id or current.get("released_at"):
            continue
        root, path = Path(current["checkout"]), Path(current["file"])
        with _lock(root, path):
            if release(session_id, root, path):
                released.append(str(path))
    return released


def reacquire(session_id, root, path):
    """SessionStart `resume`: touch only this session's own record, and only when safe to reclaim."""
    current = _read_record(_record_path(root, path))
    if current is None:
        return "unowned"
    if current["session_id"] != session_id:
        return "other-owner"
    state = owner_state(current)
    if state in ("free", "stale"):
        acquire(session_id, root, path)
        return "acquired"
    pid, pid_start, _host, _checkout = _identity(root)
    if state == "live" and (current["claude_pid"], current["pid_start"]) == (pid, pid_start):
        acquire(session_id, root, path)
        return "acquired"
    return "live-elsewhere"


def check_write(session_id, root, path):
    """Refuse a write from any session but the owner's; a legacy unowned ledger always passes."""
    current = _read_record(_record_path(root, path))
    if current is None:
        return
    if session_id is None:
        raise ValueError("Ledger has an owner; pass --session")
    if current["session_id"] == session_id:
        return
    raise ValueError(f"Ledger owned by session {current['session_id']} on {current['host']}; "
                      "run bind (or adopt) to take ownership")
