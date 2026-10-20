"""Bounded, explicit Markdown task ledgers shared by dashboard and agent CLIs."""
import argparse
from datetime import datetime, timezone
import time
from collections import Counter
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

# `-I` (used by every CLI caller) drops the script's own directory from sys.path; task_ownership lives beside it.
sys.path.insert(0, str(Path(__file__).resolve().parent))

START = "<!-- fsa:tasks:start -->"
END = "<!-- fsa:tasks:end -->"
STATUSES = ("pending", "in_progress", "blocked", "done", "skipped", "canceled")
MAX_ACTIVE_SECONDS = 300
HEADERS = ["ID", "Status", "Task", "Note"]
ACTIVITY_HEADERS = HEADERS + ["Owner", "Activity", "Active until"]
MAX_BYTES = 256 * 1024
MAX_ROWS = 200
SID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\Z")
TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\Z")


def _state_dir():
    return Path(os.environ.get("FSA_TASKS_DIR") or "~/.local/state/fullstack-agents/tasks").expanduser()


def _binding_path(session_id):
    if not isinstance(session_id, str) or not SID.fullmatch(session_id):
        raise ValueError("Invalid task session id (expected a safe identifier of at most 200 characters)")
    return _state_dir() / (session_id + ".json")


def _root(root):
    if not isinstance(root, (str, os.PathLike)) or not str(root).strip():
        raise ValueError("Task root must be a nonempty path")
    result = Path(root).expanduser().resolve(strict=True)
    if not result.is_dir():
        raise ValueError("Task root must be a directory")
    return result


def _file(root, filename, existing=True):
    path = Path(filename).expanduser()
    if not path.is_absolute():
        path = root / path
    result = path.resolve(strict=existing)
    if not result.is_relative_to(root) or result == root:
        raise ValueError("Task Markdown must remain inside the registered root")
    if result.suffix.lower() != ".md":
        raise ValueError("Task file must have a .md extension")
    if existing and not result.is_file():
        raise ValueError("Task Markdown must be a regular file")
    return result


def _read(path, limit=MAX_BYTES):
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Task document or registration must be a regular file")
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"Task file exceeds {limit} bytes")
    return data.decode("utf-8")


def _cells(line):
    line = line.strip()
    if not line.startswith("|") or not line.endswith("|"):
        raise ValueError("Malformed task table row: expected leading and trailing pipes")
    cells, current = [], []
    body = line[1:-1]
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\" and index + 1 < len(body) and body[index + 1] in "\\|":
            index += 1
            current.append(body[index])
        elif char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    cells.append("".join(current).strip())
    if len(cells) not in (4, 7):
        raise ValueError("Malformed task table row: expected four or seven columns")
    return cells


def _deadline(value):
    if not value:
        return 0.0
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone required")
        return parsed.timestamp()
    except (ValueError, OverflowError, TypeError) as error:
        raise ValueError("Active until must be an ISO 8601 timestamp with timezone") from error


def _item(identifier, status, title, note, owner="", activity="", active_until=""):
    status = "in_progress" if status == "running" else status
    if not isinstance(identifier, str) or not TASK_ID.fullmatch(identifier):
        raise ValueError("Task ID must be a safe nonempty identifier of at most 64 characters")
    if status not in STATUSES:
        raise ValueError(f"Invalid task status: {status}")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Task title must be nonempty")
    for value in (identifier, status, title, note, owner, activity, active_until):
        if not isinstance(value, str) or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Task cells must be single-line text without control characters")
        if START in value or END in value:
            raise ValueError("Task cells cannot contain ledger markers")
    if status != "in_progress":
        active_until = ""
    if active_until and (not owner.strip() or not activity.strip()):
        raise ValueError("Active execution requires an owner and activity")
    _deadline(active_until)
    return {"id": identifier, "status": status, "title": title.strip(), "note": note.strip(),
            "owner": owner.strip(), "activity": activity.strip(), "active_until": active_until}


def _parse(text):
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError("Task Markdown must contain exactly one start marker and one end marker")
    start, end = text.index(START), text.index(END)
    if start >= end:
        raise ValueError("Task markers are out of order")
    # Markers own complete lines, so surrounding prose can be preserved byte for byte.
    for marker in (START, END):
        if not any(line.strip() == marker for line in text.splitlines()):
            raise ValueError("Task markers must be on separate lines")
    rows = [line for line in text[start + len(START):end].splitlines() if line.strip()]
    header = _cells(rows[0]) if rows else []
    if len(rows) < 2 or header not in (HEADERS, ACTIVITY_HEADERS):
        raise ValueError("Task table header must be ID | Status | Task | Note, optionally Owner | Activity | Active until")
    if len(_cells(rows[1])) != len(header):
        raise ValueError("Task separator column count must match header")
    if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in _cells(rows[1])):
        raise ValueError("Malformed task table separator")
    if len(rows) - 2 > MAX_ROWS:
        raise ValueError(f"Task table exceeds {MAX_ROWS} rows")
    items, identifiers = [], set()
    for row in rows[2:]:
        cells = _cells(row)
        if len(cells) != len(header):
            raise ValueError("Task row column count must match header")
        item = _item(*cells)
        if item["id"] in identifiers:
            raise ValueError(f"Duplicate task ID: {item['id']}")
        identifiers.add(item["id"])
        items.append(item)
    return items, start + len(START), end


def _render(items):
    def cell(value):
        return value.replace("\\", "\\\\").replace("|", "\\|")
    extended = any(item.get(key) for item in items for key in ("owner", "activity", "active_until"))
    header = ACTIVITY_HEADERS if extended else HEADERS
    keys = ("id", "status", "title", "note", "owner", "activity", "active_until") if extended else ("id", "status", "title", "note")
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines.extend("| " + " | ".join(cell(item.get(key, "")) for key in keys) + " |" for item in items)
    return "\n" + "\n".join(lines) + "\n"


def _atomic(path, text, exclusive=False):
    data = text.encode("utf-8")
    if len(data) > MAX_BYTES:
        raise ValueError(f"Task file exceeds {MAX_BYTES} bytes")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def _lock(root, path):
    directory = _state_dir() / "locks"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = hashlib.sha256(f"{root}\0{path}".encode()).hexdigest()
    with (directory / (key + ".lock")).open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def _summary(path):
    text = _read(path)
    items, _, _ = _parse(text)
    title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), path.stem)
    updated = path.stat().st_mtime
    now = time.time()
    for item in items:
        item["is_active"] = bool(item["status"] == "in_progress" and item["owner"] and item["activity"]
                                 and min(_deadline(item["active_until"]), updated + MAX_ACTIVE_SECONDS) > now)
    counts = dict.fromkeys(STATUSES, 0)
    counts.update(Counter(item["status"] for item in items))
    return {"title": title, "updated": updated, "items": items, "counts": counts, "total": len(items),
            "completed": counts["done"], "active": sum(item["is_active"] for item in items)}


def _owner_text(owner):
    return f"owner: {owner['session_id']} ({owner['state']})" if owner else "owner: none"


def _show_text(summary):
    counts = summary["counts"]
    lines = [f"done {counts['done']}/{summary['total']} · in_progress {counts['in_progress']} · blocked {counts['blocked']}"
             f" · pending {counts['pending']} · active {summary['active']}",
             _owner_text(summary.get("owner"))]
    for item in summary["items"]:
        if item["status"] == "done":
            continue
        line = f"{item['id']}  {item['status']}  "
        if item["owner"] or item["activity"]:
            line += f"[{item['owner']}: {item['activity']}]  "
        line += item["title"]
        if item["note"]:
            note = item["note"] if len(item["note"]) <= 100 else item["note"][:99] + "…"
            line += f" — {note}"
        lines.append(line)
    return "\n".join(lines)


def _task_specs(values):
    items = []
    for task in values:
        parts = task.split("|", 3)
        if len(parts) != 4:
            raise ValueError("--task requires ID|status|title|note")
        items.append(_item(*(part.strip() for part in parts)))
    return items


def bind_tasks(session_id, root, filename, takeover=None):
    binding = _binding_path(session_id)
    root = _root(root)
    path = _file(root, filename)
    _parse(_read(path))
    import task_ownership
    with _lock(root, path):
        task_ownership.acquire(session_id, root, path, takeover)
    _atomic(binding, json.dumps({"session_id": session_id, "root": str(root), "file": str(path)}, ensure_ascii=False) + "\n")
    return load_tasks(session_id, root)


def release_ownership(session_id, root, filename):
    root = _root(root)
    path = _file(root, filename)
    import task_ownership
    with _lock(root, path):
        released = task_ownership.release(session_id, root, path)
    return {"file": str(path), "released": released}


def load_tasks(session_id, cwd):
    """Read a registered ledger afresh; malformed bound state is an explicit error."""
    info = {}
    try:
        binding = _binding_path(session_id)
        if not binding.exists() and not binding.is_symlink():
            return {}
        if binding.is_symlink():
            raise ValueError("Task registration cannot be a symlink")
        record = json.loads(_read(binding, 16384))
        if not isinstance(record, dict) or record.get("session_id") != session_id:
            raise ValueError("Task registration session does not match")
        root = _root(record["root"])
        # The ledger lives in the repository the work changes, which may differ from the session's cwd
        # (e.g. plugin work run from a project checkout); any other root must be a git repository.
        if _root(cwd) != root and not (root / ".git").exists():
            raise ValueError("Task registration root must be the session cwd or a git repository root")
        path = _file(root, record["file"])
        info = {"file": str(path), "relative_file": str(path.relative_to(root))}
        return {**info, **_summary(path)}
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        return {**info, "error": str(error)}


def _read_checkpoint_input(value):
    data = sys.stdin.read() if value == "-" else Path(value).read_text()
    try:
        return json.loads(data)
    except ValueError as error:
        raise ValueError(f"Checkpoint input is not valid JSON: {error}") from error


def _cmd_checkpoint(args, root, path):
    import task_ownership
    import task_checkpoint
    payload = _read_checkpoint_input(args.input)
    with _lock(root, path):
        path = _file(root, args.file)
        task_ownership.check_write(args.session, root, path)
        new_text, changed = task_checkpoint.apply(_read(path), payload, root, path.stem, args.session)
        if changed:
            _atomic(path, new_text)
    return {"file": str(path), "changed": changed, "updated": path.stat().st_mtime}


def _load_binding(session_id):
    binding = _binding_path(session_id)
    if not binding.exists() or binding.is_symlink():
        raise ValueError(f"Session {session_id} has no task binding")
    record = json.loads(_read(binding, 16384))
    if not isinstance(record, dict) or record.get("session_id") != session_id:
        raise ValueError(f"Session {session_id} binding is invalid")
    return record, binding


def _delete_parked_matching(predicate):
    directory = _state_dir() / "parked"
    if not directory.is_dir():
        return
    for record_path in directory.glob("*.json"):
        try:
            record = json.loads(_read(record_path, 4096))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and predicate(record):
            record_path.unlink(missing_ok=True)


def _append_ownership_log(text, line):
    heading = "## Ownership log"
    text = text.rstrip("\n") + "\n"
    return text + line if heading in text else text + "\n" + heading + "\n" + line


def _cmd_adopt(args, root, path):
    import task_ownership
    import task_recovery
    from_record, from_binding = _load_binding(args.from_session)
    if _root(from_record["root"]) != root or _file(root, from_record["file"]) != path:
        raise ValueError(f"Session {args.from_session} is not bound to this file")
    with _lock(root, path):
        path = _file(root, args.file)
        record, state = task_ownership.current_owner(root, path)
        if record is not None and state != "free" and record["session_id"] not in (args.from_session, args.session):
            raise ValueError(f"Ledger owned by session {record['session_id']} ({state}); adopt refused")
        task_ownership.acquire(args.session, root, path, args.takeover)
        _atomic(_binding_path(args.session),
                json.dumps({"session_id": args.session, "root": str(root), "file": str(path)}, ensure_ascii=False) + "\n")
        from_binding.unlink(missing_ok=True)
        line = f"- {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')} adopted by {args.session} from {args.from_session} ({state})\n"
        text = _append_ownership_log(_read(path), line)
        _parse(text)
        _atomic(path, text)
    _delete_parked_matching(lambda record: record.get("old_session") == args.from_session)
    recovery = task_recovery.render(task_recovery.collect(args.session, str(root)))
    return {"file": str(path), "adopted_from": args.from_session, "session_id": args.session, "recovery": recovery}


def _cmd_close(args, root, path):
    import task_ownership
    import task_checkpoint
    with _lock(root, path):
        path = _file(root, args.file)
        task_ownership.check_write(args.session, root, path)
        text = _read(path)
        items, _start, _end = _parse(text)
        open_rows = [item["id"] for item in items if item["status"] in ("pending", "in_progress", "blocked")]
        if open_rows:
            raise ValueError(f"Cannot close with open rows: {', '.join(open_rows)}")
        checkpoint, error = task_checkpoint.load_checkpoint(text)
        if error is not None:
            raise ValueError(f"fix the checkpoint before close: {error}")
        if checkpoint is not None:
            payload = {key: value for key, value in checkpoint.items() if key != "identity"}
            payload["status"] = "completed"
            text, changed = task_checkpoint.apply(text, payload, root, path.stem, args.session)
            if changed:
                _atomic(path, text)
        released = task_ownership.release(args.session, root, path)
    _delete_parked_matching(lambda record: record.get("file") == str(path))
    return {"file": str(path), "released": released}


def _session_vars(environ):
    return environ.get("CODEX_THREAD_ID"), environ.get("CLAUDE_CODE_SESSION_ID") or environ.get("CLAUDE_SESSION_ID")


def default_session(environ=os.environ, pid=None):
    """Single variable wins; both set walks the ancestor chain for the engine actually running."""
    x, c = _session_vars(environ)
    if bool(x) != bool(c):
        return x or c
    if not x:
        return None
    import task_ownership
    claude_pid = environ.get("CLAUDE_PID")
    target = int(claude_pid) if claude_pid else None
    for candidate in task_ownership.ancestors(pid):
        if target is not None and candidate == target:
            return c
        if task_ownership._is_codex(candidate):
            return x
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Register and update an explicit Markdown task ledger")
    actions = parser.add_subparsers(dest="command", required=True)
    session_default = default_session()
    recover = actions.add_parser("recover")
    recover.add_argument("--session", default=session_default)
    recover.add_argument("--cwd", required=True)
    for command in ("init", "bind", "set", "add", "show", "release", "checkpoint", "adopt", "close"):
        sub = actions.add_parser(command)
        sub.add_argument("--root", required=True)
        sub.add_argument("--file", required=True)
        sub.add_argument("--session", default=session_default)
        if command == "init":
            sub.add_argument("--title", default="Tasks")
        if command in ("bind", "adopt"):
            sub.add_argument("--takeover", help="Expected current owner's session id (CAS takeover, only on the user's word)")
        if command == "adopt":
            sub.add_argument("--from", dest="from_session", required=True, help="Session to adopt the binding from")
        if command == "checkpoint":
            sub.add_argument("--input", required=True, help="Checkpoint JSON file path, or - for stdin")
        if command in ("init", "add"):
            sub.add_argument("--task", action="append", default=[], required=command == "add", help="ID|status|title|note (repeatable)")
        if command == "show":
            sub.add_argument("--json", action="store_true", help="Print the machine-readable summary")
        if command == "set":
            sub.add_argument("--id", action="append", required=True, help="Task ID (repeatable)")
            sub.add_argument("--status", choices=(*STATUSES, "running"), help="Omit to keep each row's status")
            sub.add_argument("--note")
            sub.add_argument("--owner")
            sub.add_argument("--activity")
            sub.add_argument("--active-for", type=int, help="Report active execution for 1..300 seconds; 0 clears it")
    args = parser.parse_args(argv)
    try:
        import task_ownership
        x, c = _session_vars(os.environ)
        if args.command not in ("show", "recover") and args.session is None and x and c:
            raise ValueError("cannot determine the session id (CODEX_THREAD_ID and CLAUDE_CODE_SESSION_ID "
                              "both set and ambiguous); pass --session")
        if args.command == "recover":
            import task_recovery
            info = task_recovery.collect(args.session, args.cwd)
            print(task_recovery.render(info))
            return 2 if "fatal" in info else 0
        root = _root(args.root)
        if args.command in ("init", "bind"):
            _binding_path(args.session)
        path = _file(root, args.file, existing=args.command != "init")
        if args.command == "init":
            _item("title", "pending", args.title, "")
            items = _task_specs(args.task)
            text = f"# {args.title}\n\n{START}{_render(items)}{END}\n"
            _parse(text)
            with _lock(root, path):
                if path.exists() or path.is_symlink():
                    raise ValueError("Task file already exists; init never overwrites it")
                _file(root, path, existing=False)
                _atomic(path, text, exclusive=True)
            result = bind_tasks(args.session, root, path)
        elif args.command == "bind":
            result = bind_tasks(args.session, root, path, args.takeover)
        elif args.command == "release":
            result = release_ownership(args.session, root, args.file)
        elif args.command == "checkpoint":
            result = _cmd_checkpoint(args, root, path)
        elif args.command == "adopt":
            result = _cmd_adopt(args, root, path)
        elif args.command == "close":
            result = _cmd_close(args, root, path)
        elif args.command == "show":
            owner_record, owner_state = task_ownership.current_owner(root, path)
            owner = {"session_id": owner_record["session_id"], "state": owner_state} if owner_record else None
            summary = {"file": str(path), "owner": owner, **_summary(path)}
            print(json.dumps(summary, ensure_ascii=False) if args.json else _show_text(summary))
            return 0
        elif args.command == "add":
            specs = _task_specs(args.task)
            with _lock(root, path):
                path = _file(root, args.file)
                task_ownership.check_write(args.session, root, path)
                text = _read(path)
                items, start, end = _parse(text)
                for spec in specs:
                    task = next((item for item in items if item["id"] == spec["id"]), None)
                    if task is None:
                        items.append(spec)
                    else:
                        task.update(_item(task["id"], spec["status"], spec["title"], spec["note"],
                                          task["owner"], task["activity"], task["active_until"]))
                if len(items) > MAX_ROWS:
                    raise ValueError(f"Task table exceeds {MAX_ROWS} rows")
                changed = text[:start] + _render(items) + text[end:]
                _parse(changed)
                _file(root, args.file)
                _atomic(path, changed)
            result = {"file": str(path), "updated": path.stat().st_mtime}
        elif args.command == "set":
            if args.active_for is not None and not 0 <= args.active_for <= MAX_ACTIVE_SECONDS:
                raise ValueError("--active-for must be between 0 and 300 seconds")
            with _lock(root, path):
                path = _file(root, args.file)
                task_ownership.check_write(args.session, root, path)
                text = _read(path)
                items, start, end = _parse(text)
                for identifier in dict.fromkeys(args.id):
                    task = next((item for item in items if item["id"] == identifier), None)
                    if task is None:
                        raise ValueError(f"Unknown task ID: {identifier}")
                    status = task["status"] if args.status is None else args.status
                    owner = task["owner"] if args.owner is None else args.owner
                    activity = (task["activity"] if owner == task["owner"] else "") if args.activity is None else args.activity
                    active_until = task["active_until"] if owner == task["owner"] else ""
                    if args.active_for is not None:
                        if args.active_for and status not in ("in_progress", "running"):
                            raise ValueError("Active execution requires in_progress status")
                        active_until = datetime.fromtimestamp(time.time() + args.active_for, timezone.utc).isoformat() if args.active_for else ""
                    task.update(_item(task["id"], status, task["title"], task["note"] if args.note is None else args.note,
                                      owner, activity, active_until))
                changed = text[:start] + _render(items) + text[end:]
                _parse(changed)
                _file(root, args.file)
                _atomic(path, changed)
            result = {"file": str(path), "updated": path.stat().st_mtime}
        if "error" in result:
            raise ValueError(result["error"])
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
