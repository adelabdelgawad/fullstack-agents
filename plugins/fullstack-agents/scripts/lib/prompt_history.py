"""Per-session record of recent genuine user prompts, used to authenticate `resolve --quote`.

See docs/TASK_LIFECYCLE_DESIGN.md §14.6 item 2.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

MAX_PROMPTS = 30
MAX_BYTES = 8192
SKIP_MARKERS = ("<task-notification>", "SYSTEM NOTIFICATION")
SID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\Z")


def _state_dir():
    return Path(os.environ.get("FSA_TASKS_DIR") or "~/.local/state/fullstack-agents/tasks").expanduser()


def _path(session_id):
    if not isinstance(session_id, str) or not SID.fullmatch(session_id):
        raise ValueError("Invalid session id")
    return _state_dir() / "prompts" / (session_id + ".json")


def _read(path):
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [entry for entry in data
            if isinstance(entry, list) and all(isinstance(value, str) for value in entry)]


def _atomic_write(path, text):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def record(session_id, prompt):
    """Append a genuine prompt, bounded to the last MAX_PROMPTS entries; a non-prompt is skipped silently."""
    if not isinstance(prompt, str) or not prompt.strip():
        return
    if any(marker in prompt for marker in SKIP_MARKERS):
        return
    encoded = prompt.encode("utf-8")
    text = prompt if len(encoded) <= MAX_BYTES else encoded[:MAX_BYTES].decode("utf-8", "ignore")
    path = _path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (path.parent / (path.name + ".lock")).open("a") as lock_stream:
        fcntl.flock(lock_stream, fcntl.LOCK_EX)
        prompts = (_read(path) + [_hashes(session_id, text)])[-MAX_PROMPTS:]
        _atomic_write(path, json.dumps(prompts, ensure_ascii=False))


def _normalize(text):
    return " ".join(text.lower().split())


def _words(text):
    return _normalize(text).split()


def _hashes(session_id, text):
    words = _words(text)
    return sorted({_hash(session_id, " ".join(words[index:index + 3]))
                   for index in range(len(words) - 2)})


def _hash(session_id, gram):
    return hashlib.sha256(f"{session_id}\0{gram}".encode()).hexdigest()[:16]


def contains(session_id, quote):
    """Match a sufficiently long quote when all of its word trigrams occur in one recorded prompt."""
    if not isinstance(quote, str):
        return False
    normalized = _normalize(quote)
    if len(normalized) < 8 or len(_words(normalized)) < 3:
        return False
    wanted = set(_hashes(session_id, normalized))
    return any(wanted.issubset(set(prompt)) for prompt in _read(_path(session_id)))
