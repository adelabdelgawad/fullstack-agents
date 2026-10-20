"""Checkpoint section: a strictly validated fenced JSON block spliced into the task ledger."""
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import subprocess

from task_tracking import END as TABLE_END

CP_START = "<!-- fsa:checkpoint:start -->"
CP_END = "<!-- fsa:checkpoint:end -->"
MAX_STRING = 500
MAX_LIST = 40
MAX_SECTION_BYTES = 8192
STATUSES = ("active", "completed", "abandoned")
APPROVAL_KINDS = ("single-use", "task")
APPROVAL_CLARITY = ("explicit", "ambiguous")
VERIFICATION_RESULTS = ("pass", "fail", "other")
REQUIRED_TOP = {"goal", "scope", "approvals", "decisions", "constraints", "done", "next", "evidence",
                "verification", "status"}
OPTIONAL_TOP = {"blockers"}
IDENTITY_REQUIRED = {"schema", "task_id", "root", "checkout", "branch", "head", "session_id", "written_at"}
IDENTITY_OPTIONAL = {"detached"}


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _git(args, cwd):
    try:
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10)
    except OSError as error:
        raise ValueError(f"git unavailable: {error}") from error
    if result.returncode != 0:
        raise ValueError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def fingerprint(root, paths):
    """HEAD plus a hash of `git status --porcelain` restricted to the given paths."""
    head = _git(["rev-parse", "HEAD"], root)
    status = _git(["status", "--porcelain", "--", *paths], root)
    return {"head": head, "status_sha256": hashlib.sha256(status.encode()).hexdigest()}


def _str(value, field):
    if not isinstance(value, str) or not value or len(value) > MAX_STRING:
        raise ValueError(f"{field} must be a nonempty string of at most {MAX_STRING} characters")
    return value


def _list(value, field, item_validator):
    if not isinstance(value, list) or len(value) > MAX_LIST:
        raise ValueError(f"{field} must be a list of at most {MAX_LIST} items")
    return [item_validator(item, f"{field}[{index}]") for index, item in enumerate(value)]


def _dict(value, field, allowed):
    if not isinstance(value, dict) or not set(value).issubset(allowed):
        raise ValueError(f"{field} has unknown or invalid keys")
    return value


def _require(value, field, keys):
    missing = [key for key in keys if key not in value]
    if missing:
        raise ValueError(f"{field} missing {missing}")


def _scope(value, field):
    _dict(value, field, {"in", "out"})
    _require(value, field, ("in", "out"))
    return {"in": _list(value["in"], f"{field}.in", _str), "out": _list(value["out"], f"{field}.out", _str)}


def _approval(value, field):
    keys = ("quote", "at", "scope", "kind", "used", "clarity")
    _dict(value, field, set(keys))
    _require(value, field, keys)
    for key in ("quote", "at", "scope"):
        _str(value[key], f"{field}.{key}")
    if value["kind"] not in APPROVAL_KINDS:
        raise ValueError(f"{field}.kind must be single-use or task")
    if not isinstance(value["used"], bool):
        raise ValueError(f"{field}.used must be a boolean")
    if value["clarity"] not in APPROVAL_CLARITY:
        raise ValueError(f"{field}.clarity must be explicit or ambiguous")
    return value


def _decision(value, field):
    _dict(value, field, {"id", "text", "source"})
    _require(value, field, ("id", "text", "source"))
    for key in ("id", "text", "source"):
        _str(value[key], f"{field}.{key}")
    return value


def _done_item(value, field):
    _dict(value, field, {"text", "evidence"})
    _require(value, field, ("text", "evidence"))
    for key in ("text", "evidence"):
        _str(value[key], f"{field}.{key}")
    return value


def _next(value, field):
    _dict(value, field, {"action", "owner"})
    _require(value, field, ("action", "owner"))
    for key in ("action", "owner"):
        _str(value[key], f"{field}.{key}")
    return value


def _fingerprint_shape(value, field):
    _dict(value, field, {"head", "status_sha256"})
    _require(value, field, ("head", "status_sha256"))
    return value


def _verification(value, field, allow_fingerprint=False):
    keys = ("command", "result", "log", "run_at", "paths")
    allowed = set(keys) | ({"fingerprint"} if allow_fingerprint else set())
    _dict(value, field, allowed)
    _require(value, field, keys)
    _str(value["command"], f"{field}.command")
    if value["result"] not in VERIFICATION_RESULTS:
        raise ValueError(f"{field}.result must be pass, fail or other")
    _str(value["log"], f"{field}.log")
    _str(value["run_at"], f"{field}.run_at")
    _list(value["paths"], f"{field}.paths", _str)
    if allow_fingerprint and "fingerprint" in value:
        _fingerprint_shape(value["fingerprint"], f"{field}.fingerprint")
    return value


def _identity_shape(value, field):
    _dict(value, field, IDENTITY_REQUIRED | IDENTITY_OPTIONAL)
    _require(value, field, IDENTITY_REQUIRED)
    return value


def validate(payload, allow_identity=False):
    """Reject unknown keys and bad types at every level; never return a partially built checkpoint."""
    if not isinstance(payload, dict):
        raise ValueError("Checkpoint must be a JSON object")
    allowed = REQUIRED_TOP | OPTIONAL_TOP | ({"identity"} if allow_identity else set())
    if not set(payload).issubset(allowed):
        raise ValueError(f"Unknown checkpoint keys: {sorted(set(payload) - allowed)}")
    missing = REQUIRED_TOP - set(payload)
    if missing:
        raise ValueError(f"Checkpoint missing required keys: {sorted(missing)}")
    if payload["status"] not in STATUSES:
        raise ValueError("status must be active, completed or abandoned")
    checkpoint = {
        "goal": _str(payload["goal"], "goal"),
        "scope": _scope(payload["scope"], "scope"),
        "approvals": _list(payload["approvals"], "approvals", _approval),
        "decisions": _list(payload["decisions"], "decisions", _decision),
        "constraints": _list(payload["constraints"], "constraints", _str),
        "done": _list(payload["done"], "done", _done_item),
        "next": _next(payload["next"], "next"),
        "blockers": _list(payload.get("blockers", []), "blockers", _str),
        "evidence": _list(payload["evidence"], "evidence", _str),
        "verification": _list(payload["verification"], "verification",
                               lambda item, field: _verification(item, field, allow_identity)),
        "status": payload["status"],
    }
    if allow_identity:
        checkpoint["identity"] = _identity_shape(payload.get("identity"), "identity")
    return checkpoint


def git_identity(root):
    """Ask Git, not `.git`, so linked worktrees and symlinked paths resolve correctly."""
    checkout = os.path.realpath(_git(["rev-parse", "--show-toplevel"], root))
    try:
        branch = _git(["symbolic-ref", "-q", "--short", "HEAD"], root) or None
        detached = branch is None
    except ValueError:
        branch, detached = None, True
    head = _git(["rev-parse", "HEAD"], root)
    return {"checkout": checkout, "branch": branch, "head": head, "detached": detached}


def build_identity(root, task_id, session_id):
    identity = git_identity(root)
    return {"schema": 1, "task_id": task_id, "root": str(root), "checkout": identity["checkout"],
            "branch": identity["branch"], "head": identity["head"], "detached": identity["detached"],
            "session_id": session_id, "written_at": _now()}


def render(checkpoint, identity):
    body = dict(checkpoint)
    body["identity"] = identity
    text = json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False)
    section = f"{CP_START}\n```json\n{text}\n```\n{CP_END}\n"
    if len(section.encode("utf-8")) > MAX_SECTION_BYTES:
        raise ValueError(f"Checkpoint section exceeds {MAX_SECTION_BYTES} bytes")
    return section


def splice(text, section):
    """Replace an existing checkpoint section in place, or insert one right after the task table."""
    start = text.find(CP_START)
    if start != -1:
        end = text.find(CP_END)
        if end == -1:
            raise ValueError("Checkpoint section missing its end marker")
        end += len(CP_END)
        if end < len(text) and text[end] == "\n":
            end += 1
        return text[:start] + section + text[end:]
    anchor = text.find(TABLE_END)
    if anchor == -1:
        raise ValueError("Task table end marker not found")
    anchor += len(TABLE_END)
    newline = text.find("\n", anchor)
    anchor = newline + 1 if newline != -1 else len(text)
    return text[:anchor] + "\n" + section + text[anchor:]


def load_checkpoint(text):
    """(dict|None, error|None); a missing end marker, bad JSON or schema failure is an error, never partial data."""
    start = text.find(CP_START)
    if start == -1:
        return None, None
    end = text.find(CP_END)
    if end == -1:
        return None, "Checkpoint section missing its end marker"
    match = re.search(r"```json\s*\n(.*?)\n```", text[start:end], re.DOTALL)
    if not match:
        return None, "Checkpoint section must contain a fenced json block"
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        return None, f"Checkpoint JSON is invalid: {error}"
    try:
        return validate(payload, allow_identity=True), None
    except ValueError as error:
        return None, str(error)


def _same(existing, checkpoint, identity):
    old_identity = {key: value for key, value in existing["identity"].items() if key != "written_at"}
    new_identity = {key: value for key, value in identity.items() if key != "written_at"}
    old_body = {key: value for key, value in existing.items() if key != "identity"}
    return old_identity == new_identity and old_body == checkpoint


_FINGERPRINT_KEYS = ("command", "result", "log", "run_at", "paths")


def _find_fingerprint(old_entries, entry):
    """Reuse the fingerprint of an old entry with the same content, else None."""
    for old in old_entries:
        if "fingerprint" not in old:
            continue
        if all(old[key] == entry[key] for key in _FINGERPRINT_KEYS):
            return old["fingerprint"]
    return None


def apply(text, payload, root, task_id, session_id):
    """Validate, stamp identity/fingerprints, and splice the section; return (text, changed)."""
    stripped = dict(payload)
    stripped["verification"] = [{key: value for key, value in entry.items() if key != "fingerprint"}
                                 for entry in payload["verification"]]
    checkpoint = validate(stripped)
    existing, _ = load_checkpoint(text)
    old_entries = existing["verification"] if existing is not None else []
    for entry in checkpoint["verification"]:
        reused = _find_fingerprint(old_entries, entry)
        entry["fingerprint"] = reused if reused is not None else fingerprint(root, entry["paths"])
    identity = build_identity(root, task_id, session_id)
    if existing is not None and _same(existing, checkpoint, identity):
        return text, False
    return splice(text, render(checkpoint, identity)), True
