"""Append-only per-project coordination log: one JSON event per line, folded by readers into state; see docs/TASK_LIFECYCLE_DESIGN.md §15."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

MARKERS = ("<task-notification", "SYSTEM NOTIFICATION", "<teammate-message", "Another Claude session sent a message")


def is_notification(text):
    return isinstance(text, str) and any(marker in text for marker in MARKERS)


def _state_dir():
    return Path(os.environ.get("FSA_TASKS_DIR") or "~/.local/state/fullstack-agents/tasks").expanduser()


def _coordination_dir():
    return _state_dir() / "coordination"


def _project_root(cwd):
    """The main checkout of the repository (git-common-dir's parent), so worktrees share one log;
    a non-git cwd falls back to its own resolved path."""
    try:
        result = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--git-common-dir"],
                                 capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        result = None
    if result is not None and result.returncode == 0 and result.stdout.strip():
        common_dir = Path(result.stdout.strip())
        if not common_dir.is_absolute():
            common_dir = Path(cwd).expanduser().resolve() / common_dir
        return str(common_dir.resolve().parent)
    return str(Path(cwd).expanduser().resolve())


def _key(cwd):
    return hashlib.sha256(_project_root(cwd).encode("utf-8")).hexdigest()[:16]


def _log_path(cwd):
    return _coordination_dir() / f"{_key(cwd)}.jsonl"


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_lines(data):
    """Parse complete JSON lines; any line that fails to parse (a torn write) is skipped and reported."""
    events, torn = [], False
    for line in data.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            torn = True
            continue
        if isinstance(event, dict):
            events.append(event)
        else:
            torn = True
    return events, torn


def read_path(path):
    if not path.exists():
        return {"events": [], "torn": False}
    events, torn = _parse_lines(path.read_bytes())
    return {"events": events, "torn": torn}


def read(cwd):
    return read_path(_log_path(cwd))


def _flock(stream, timeout):
    deadline = time.time() + timeout
    while True:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.time() >= deadline:
                raise TimeoutError("coordination log lock timed out")
            time.sleep(0.05)


@contextmanager
def locked(cwd, timeout=5):
    directory = _coordination_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / f"{_key(cwd)}.lock").open("a") as stream:
        _flock(stream, timeout)
        try:
            yield _log_path(cwd)
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def append_locked(path, session, type_, **fields):
    """Append one event; the caller must already hold `locked(cwd)` for this same path. Never rewrites a prior
    line: a torn tail is left as-is and a leading newline keeps the new event from gluing onto it."""
    existing = read_path(path)["events"]
    seq = existing[-1]["seq"] + 1 if existing else 1
    event = {"seq": seq, "at": _now_iso(), "session": session, "type": type_, **fields}
    line = json.dumps(event, ensure_ascii=False).encode("utf-8")
    with path.open("a+b") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        prefix = b""
        if size:
            stream.seek(size - 1)
            if stream.read(1) != b"\n":
                prefix = b"\n"
        stream.write(prefix + line + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    return event


def append(cwd, session, type_, timeout=5, **fields):
    """Append one event under its own exclusive lock; `seq` is assigned while holding it."""
    with locked(cwd, timeout) as path:
        return append_locked(path, session, type_, **fields)


def _capture_failed_path(cwd):
    return _coordination_dir() / f"{_key(cwd)}.capture_failed"


def mark_capture_failed(cwd):
    directory = _coordination_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = _capture_failed_path(cwd)
    path.touch(exist_ok=True)
    os.chmod(path, 0o600)


def capture_failed(cwd):
    return _capture_failed_path(cwd).exists()


def ack_capture_failed(cwd):
    _capture_failed_path(cwd).unlink(missing_ok=True)
