"""Bounded, explicit Markdown task ledgers shared by dashboard and agent CLIs."""
import argparse
from datetime import datetime, timezone
import time
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
import task_rules

START = "<!-- fsa:tasks:start -->"
END = "<!-- fsa:tasks:end -->"
LOG_START = "<!-- fsa:log:start -->"
LOG_END = "<!-- fsa:log:end -->"
STATUSES = task_rules.LEGACY_STATUSES
MAX_ACTIVE_SECONDS = 300
HEADERS = ["ID", "Status", "Task", "Note"]
ACTIVITY_HEADERS = HEADERS + ["Owner", "Activity", "Active until"]
V2_HEADERS = ACTIVITY_HEADERS + ["Parent"]
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
    if len(cells) not in (4, 7, 8):
        raise ValueError("Malformed task table row: expected four, seven or eight columns")
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


def _item(identifier, status, title, note, owner="", activity="", active_until="", parent="", version="legacy"):
    status = "in_progress" if status == "running" else status
    if not isinstance(identifier, str) or not TASK_ID.fullmatch(identifier):
        raise ValueError("Task ID must be a safe nonempty identifier of at most 64 characters")
    statuses = task_rules.V2_STATUSES if version == "v2" else STATUSES
    if status not in statuses:
        raise ValueError(f"Invalid task status: {status}")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Task title must be nonempty")
    for value in (identifier, status, title, note, owner, activity, active_until, parent):
        if not isinstance(value, str) or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Task cells must be single-line text without control characters")
        if any(marker in value for marker in (START, END, LOG_START, LOG_END)):
            raise ValueError("Task cells cannot contain ledger markers")
    if status not in ("in_progress", "verifying"):
        active_until = ""
    if active_until and (not owner.strip() or not activity.strip()):
        raise ValueError("Active execution requires an owner and activity")
    _deadline(active_until)
    return {"id": identifier, "status": status, "title": title.strip(), "note": note.strip(),
            "owner": owner.strip(), "activity": activity.strip(), "active_until": active_until,
            "parent": parent.strip()}


def _format(text):
    start, end = text.index(START), text.index(END)
    rows = [line for line in text[start + len(START):end].splitlines() if line.strip()]
    header = _cells(rows[0]) if rows else []
    expected = "ID | Status | Task | Note; optionally Owner | Activity | Active until; or v2 with Parent"
    if header not in (HEADERS, ACTIVITY_HEADERS, V2_HEADERS):
        raise ValueError(f"Task table header must equal one of: {expected}")
    return "v2" if header == V2_HEADERS else "legacy", len(header)


def _validate_log(text, table_end, version):
    if version != "v2":
        return
    if text.count(LOG_START) != 1 or text.count(LOG_END) != 1:
        raise ValueError("v2 ledger must contain exactly one task log marker pair")
    log_start, log_end = text.index(LOG_START), text.index(LOG_END)
    if not table_end < log_start < log_end:
        raise ValueError("v2 task log markers must follow the task table")
    lines = text.splitlines()
    if not all(any(line == marker for line in lines) for marker in (LOG_START, LOG_END)):
        raise ValueError("Task log markers must each be on their own line")


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
    version, width = _format(text)
    header = _cells(rows[0]) if rows else []
    if len(rows) < 2:
        raise ValueError("Task table requires a header and separator")
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
        item = _item(*cells, version=version)
        if item["id"] in identifiers:
            raise ValueError(f"Duplicate task ID: {item['id']}")
        identifiers.add(item["id"])
        items.append(item)
    _validate_log(text, end, version)
    if version == "v2":
        task_rules.validate_parents(items)
    return items, start + len(START), end


def _render(items, version="legacy", width=None):
    def cell(value):
        return value.replace("\\", "\\\\").replace("|", "\\|")
    extended = width == 7 or (width is None and any(item.get(key) for item in items for key in ("owner", "activity", "active_until")))
    header = V2_HEADERS if version == "v2" else ACTIVITY_HEADERS if extended else HEADERS
    keys = ("id", "status", "title", "note", "owner", "activity", "active_until", "parent") if version == "v2" else (("id", "status", "title", "note", "owner", "activity", "active_until") if extended else ("id", "status", "title", "note"))
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines.extend("| " + " | ".join(cell(item.get(key, "")) for key in keys) + " |" for item in items)
    return "\n" + "\n".join(lines) + "\n"


def _append_log(text, line):
    position = text.index(LOG_END)
    return text[:position] + line + text[position:]


def _mutated(text, items, start, end, version, logs=(), force_width=None):
    if version == "v2":
        task_rules.validate_open_steps(items)
    changed = text[:start] + _render(items, version, force_width) + text[end:]
    for line in logs:
        changed = _append_log(changed, line)
    if len(changed.encode()) > MAX_BYTES:
        raise ValueError("ledger too large: close or split it")
    _parse(changed)
    return changed


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
    version, _width = _format(text)
    title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), path.stem)
    updated = path.stat().st_mtime
    now = time.time()
    for item in items:
        item["is_active"] = bool(item["status"] in ("in_progress", "verifying") and item["owner"] and item["activity"]
                                 and min(_deadline(item["active_until"]), updated + MAX_ACTIVE_SECONDS) > now)
    counts, totals = task_rules.counts(items, version)
    evidence_error = None
    blockers_error = None
    if version == "v2":
        import task_evidence
        try:
            block = task_evidence.load_block(text)
            for item in items:
                if not item.get("parent") and item["status"] == "done":
                    item["completion"] = task_evidence.completion_kind(block, item["id"])
            totals["deliverables"]["completion"] = task_evidence.completion_counts(items)
        except ValueError as error:
            evidence_error = str(error)
        import task_blockers
        try:
            blk = task_blockers.load_block(text) if task_blockers.has_block(text) else {"schema": 1, "blockers": {}}
            totals["session_state"] = task_rules.session_state(items, blk["blockers"], now)
            totals["blockers"] = {bid: entry for bid, entry in blk["blockers"].items() if entry["status"] == "open"}
        except ValueError as error:
            blockers_error = str(error)
    if version == "legacy":
        for item in items:
            item.pop("parent", None)
    summary = {"title": title, "updated": updated, "items": items, "counts": counts, "format": version,
               **totals, "active": sum(item["is_active"] for item in items)}
    if evidence_error:
        summary["evidence_error"] = evidence_error
    if blockers_error:
        summary["blockers_error"] = blockers_error
    return summary


def _owner_text(owner):
    return f"owner: {owner['session_id']} ({owner['state']})" if owner else "owner: none"


def _show_text(summary):
    counts = summary["counts"]
    if summary["format"] == "v2":
        deliverables, steps = summary["deliverables"], summary["steps"]
        baseline = deliverables.get("completion", {}).get("evidence_with_baseline", 0)
        note = f" ({baseline} with baseline failures)" if baseline else ""
        first = (f"deliverables {deliverables['completed']}/{deliverables['total']}{note} · steps "
                 f"{steps['completed']}/{steps['total']} · verifying {counts['verifying']} · "
                 f"in_progress {counts['in_progress']} · blocked {counts['blocked']} · pending {counts['pending']} "
                 f"· active {summary['active']}")
    else:
        first = (f"done {counts['done']}/{summary['total']} · in_progress {counts['in_progress']} · "
                 f"blocked {counts['blocked']} · pending {counts['pending']} · active {summary['active']}")
    lines = [first, _owner_text(summary.get("owner"))]
    if summary.get("evidence_error"):
        lines.append(f"evidence_error: {summary['evidence_error']}")
    for item in summary["items"]:
        if item["status"] == "done":
            continue
        line = f"{item['id']}  {item['status']}  "
        if item["owner"] or item["activity"]:
            line += f"[{item['owner']}: {item['activity']}]  "
        line += item["title"]
        if summary["format"] == "v2" and item.get("parent"):
            line += f" (step of {item['parent']})"
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
        items.append(_item(*(part.strip() for part in parts), version="v2"))
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
        open_rows = [item["id"] for item in items if item["status"] in task_rules.OPEN]
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


def _owned_text(args, root, path):
    import task_ownership
    path = _file(root, args.file)
    task_ownership.check_write(args.session, root, path)
    return path, _read(path)


def _parser():
    parser = argparse.ArgumentParser(description="Register and update an explicit Markdown task ledger")
    actions = parser.add_subparsers(dest="command", required=True)
    session_default = default_session()
    recover = actions.add_parser("recover")
    recover.add_argument("--session", default=session_default)
    recover.add_argument("--cwd", required=True)
    import task_evidence
    import task_evidence_cli
    import task_blockers
    evidence_commands = task_evidence.COMMANDS
    blocker_commands = task_blockers.COMMANDS
    for command in ("init", "bind", "set", "add", "show", "release", "checkpoint", "adopt", "close", "upgrade",
                     "downgrade", *evidence_commands, *blocker_commands):
        sub = actions.add_parser(command)
        sub.add_argument("--root", required=True)
        sub.add_argument("--file", required=True)
        sub.add_argument("--session", default=session_default)
        if command in evidence_commands:
            task_evidence_cli.add_arguments(command, sub)
        if command in blocker_commands:
            task_blockers.add_arguments(command, sub)
        if command == "init":
            sub.add_argument("--title", default="Tasks")
            sub.add_argument("--format", choices=("v2", "legacy"), default="v2")
        if command in ("bind", "adopt"):
            sub.add_argument("--takeover", help="Expected current owner's session id (CAS takeover, only on the user's word)")
        if command == "adopt":
            sub.add_argument("--from", dest="from_session", required=True, help="Session to adopt the binding from")
        if command == "checkpoint":
            sub.add_argument("--input", required=True, help="Checkpoint JSON file path, or - for stdin")
        if command in ("init", "add"):
            sub.add_argument("--task", action="append", default=[], required=command == "add", help="ID|status|title|note (repeatable)")
        if command == "add":
            sub.add_argument("--parent")
        if command == "show":
            sub.add_argument("--json", action="store_true", help="Print the machine-readable summary")
        if command == "set":
            sub.add_argument("--id", action="append", required=True, help="Task ID (repeatable)")
            sub.add_argument("--status", choices=(*task_rules.V2_STATUSES, "running"), help="Omit to keep each row's status")
            sub.add_argument("--title")
            sub.add_argument("--reason")
            sub.add_argument("--note")
            sub.add_argument("--owner")
            sub.add_argument("--activity")
            sub.add_argument("--active-for", type=int, help="Report active execution for 1..300 seconds; 0 clears it")
    return parser


def _cmd_init(args, root, path):
    _item("title", "pending", args.title, "")
    items = _task_specs(args.task)
    if args.format == "v2":
        if any(item["status"] == "done" for item in items):
            import task_evidence
            for item in (i for i in items if i["status"] == "done"):
                task_evidence.require_done(task_evidence.load_block(""), item["id"], root)
        line = task_rules.log_line("", "init")
        text = f"# {args.title}\n\n{START}{_render(items, 'v2')}{END}\n\n## Task log\n{LOG_START}\n{line}{LOG_END}\n"
    else:
        if any(item["status"] == "verifying" for item in items):
            raise ValueError("verifying requires a v2 ledger; run fsa-task upgrade")
        text = f"# {args.title}\n\n{START}{_render(items)}{END}\n"
    _parse(text)
    with _lock(root, path):
        if path.exists() or path.is_symlink():
            raise ValueError("Task file already exists; init never overwrites it")
        _file(root, path, existing=False)
        _atomic(path, text, exclusive=True)
    return bind_tasks(args.session, root, path)


def _validate_add(specs, items, version, parent_id):
    if parent_id and version != "v2":
        raise ValueError("--parent requires a v2 ledger")
    if version != "v2" and any(spec["status"] == "verifying" for spec in specs):
        raise ValueError("verifying requires a v2 ledger; run fsa-task upgrade")
    identifiers = [spec["id"] for spec in specs]
    duplicates = set(identifiers) & {item["id"] for item in items}
    duplicates.update(identifier for identifier in identifiers if identifiers.count(identifier) > 1)
    if duplicates:
        raise ValueError(f"Duplicate task ID: {', '.join(sorted(duplicates))}")


def _cmd_add(args, root, path):
    specs = _task_specs(args.task)
    with _lock(root, path):
        path, text = _owned_text(args, root, path)
        items, start, end = _parse(text)
        version, width = _format(text)
        _validate_add(specs, items, version, args.parent)
        for spec in specs:
            added = _item(spec["id"], spec["status"], spec["title"], spec["note"], parent=args.parent or "", version=version)
            items.append(added)
        if version == "v2":
            task_rules.validate_parents(items)
        if len(items) > MAX_ROWS:
            raise ValueError(f"Task table exceeds {MAX_ROWS} rows")
        logs = [task_rules.log_line(spec["id"], "add", status=spec["status"], parent=spec["parent"], title=spec["title"]) for spec in items[-len(specs):]] if version == "v2" else []
        changed = _mutated(text, items, start, end, version, logs)
        if version == "v2" and not args.parent:
            import task_evidence
            if done_ids := [spec["id"] for spec in specs if spec["status"] == "done"]:
                block = task_evidence.load_block(text)
                for identifier in done_ids:
                    for line in task_evidence.require_done(block, identifier, root, path):
                        changed = _append_log(changed, line)
                changed = task_evidence.splice_block(changed, task_evidence.render_block(block))
            if len(changed.encode()) > MAX_BYTES:
                raise ValueError("ledger too large: close or split it")
        path = _file(root, args.file)
        _atomic(path, changed)
    return {"file": str(path), "updated": path.stat().st_mtime}


def _set_item(args, item, items, version):
    status = item["status"] if args.status is None else args.status
    status = "in_progress" if status == "running" else status
    if version == "v2" and item["status"] == "done" and status != "done" and not args.reason:
        raise ValueError(f"Reopening done task {item['id']} requires set --reason")
    owner = item["owner"] if args.owner is None else args.owner
    activity = (item["activity"] if owner == item["owner"] else "") if args.activity is None else args.activity
    active_until = item["active_until"] if owner == item["owner"] else ""
    if args.active_for is not None:
        if args.active_for and status not in ("in_progress", "verifying"):
            raise ValueError("Active execution requires in_progress or verifying status")
        active_until = datetime.fromtimestamp(time.time() + args.active_for, timezone.utc).isoformat() if args.active_for else ""
    title = item["title"] if args.title is None else args.title
    replacement = _item(item["id"], status, title, item["note"] if args.note is None else args.note,
                        owner, activity, active_until, item.get("parent", ""), version)
    return replacement


def _set_logs(args, old, new, version):
    if version != "v2":
        return []
    logs = []
    if old["status"] != new["status"]:
        logs.append(task_rules.log_line(old["id"], "status", **{"from": old["status"], "to": new["status"], "reason": args.reason or ""}))
    if old["title"] != new["title"]:
        logs.append(task_rules.log_line(old["id"], "title", **{"from": old["title"], "to": new["title"]}))
    return logs


def _apply_set_rows(args, items, version, blk):
    import task_blockers
    logs, reopened = [], []
    for identifier in dict.fromkeys(args.id):
        item = next((item for item in items if item["id"] == identifier), None)
        if item is None:
            raise ValueError(f"Unknown task ID: {identifier}")
        if (version == "v2" and item["status"] == "blocked" and args.status not in (None, "blocked")
                and task_blockers.row_has_open_blocker(blk, identifier)):
            raise ValueError(f"{identifier} has an open blocker; resolve or withdraw it first")
        replacement = _set_item(args, item, items, version)
        if version == "v2" and not item.get("parent") and item["status"] == "done" and replacement["status"] != "done":
            reopened.append(identifier)
        logs.extend(_set_logs(args, item, replacement, version))
        item.update(replacement)
    if version == "v2" and blk is not None:
        done_ids = [i for i in dict.fromkeys(args.id) if next(item for item in items if item["id"] == i)["status"] == "done"]
        logs.extend(task_blockers.auto_resolve_rows(blk, items, done_ids))
    return logs, reopened


def _cmd_set(args, root, path):
    if args.active_for is not None and not 0 <= args.active_for <= MAX_ACTIVE_SECONDS:
        raise ValueError("--active-for must be between 0 and 300 seconds")
    with _lock(root, path):
        path, text = _owned_text(args, root, path)
        items, start, end = _parse(text)
        version, width = _format(text)
        if args.status == "verifying" and version != "v2":
            raise ValueError("verifying requires a v2 ledger; run fsa-task upgrade")
        blk = None
        if version == "v2":
            import task_blockers
            if args.status == "blocked":
                raise ValueError("set cannot move a row to blocked; use `fsa-task block`")
            if task_blockers.has_block(text):
                blk = task_blockers.load_block(text)
        logs, reopened = _apply_set_rows(args, items, version, blk)
        changed = _mutated(text, items, start, end, version, logs)
        if version == "v2":
            import task_evidence
            if args.status == "done":
                block = task_evidence.load_block(text)
                deliverables = [i for i in dict.fromkeys(args.id) if not next(item for item in items if item["id"] == i).get("parent")]
                for identifier in deliverables:
                    for line in task_evidence.require_done(block, identifier, root, path):
                        changed = _append_log(changed, line)
                changed = task_evidence.splice_block(changed, task_evidence.render_block(block))
            elif reopened and task_evidence.has_block(text):
                try:
                    block = task_evidence.load_block(text)
                except ValueError as error:
                    for identifier in reopened:
                        changed = _append_log(changed, task_rules.log_line(
                            identifier, "evidence_malformed", action="reopen", error=str(error)))
                else:
                    for identifier in reopened:
                        (block["deliverables"].get(identifier) or {}).pop("completed", None)
                    changed = task_evidence.splice_block(changed, task_evidence.render_block(block))
            if blk is not None:
                changed = task_blockers.splice_block(changed, task_blockers.render_block(blk))
            if len(changed.encode()) > MAX_BYTES:
                raise ValueError("ledger too large: close or split it")
        path = _file(root, args.file)
        _atomic(path, changed)
    return {"file": str(path), "updated": path.stat().st_mtime}


def _dispatch(args, root, path):
    import task_ownership
    import task_format
    commands = {"bind": lambda: bind_tasks(args.session, root, path, args.takeover),
                "release": lambda: release_ownership(args.session, root, args.file),
                "checkpoint": lambda: _cmd_checkpoint(args, root, path), "adopt": lambda: _cmd_adopt(args, root, path),
                "close": lambda: _cmd_close(args, root, path), "upgrade": lambda: task_format._cmd_upgrade(args, root, path),
                "downgrade": lambda: task_format._cmd_downgrade(args, root, path), "add": lambda: _cmd_add(args, root, path),
                "set": lambda: _cmd_set(args, root, path)}
    if args.command in ("accept", "baseline", "check", "verify"):
        import task_evidence
        import task_evidence_cli
        if args.command == "verify":
            task_evidence.print_verify(args, root, path)
            return None
        commands[args.command] = lambda: task_evidence_cli.dispatch(args, root, path)
    import task_blockers
    if args.command in task_blockers.COMMANDS:
        commands[args.command] = lambda: task_blockers.dispatch(args, root, path)
    if args.command != "show":
        return commands[args.command]()
    record, state = task_ownership.current_owner(root, path)
    owner = {"session_id": record["session_id"], "state": state} if record else None
    summary = {"file": str(path), "owner": owner, **_summary(path)}
    print(json.dumps(summary, ensure_ascii=False) if args.json else _show_text(summary))
    return None


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        x, c = _session_vars(os.environ)
        if args.command not in ("show", "recover") and args.session is None and x and c:
            raise ValueError("cannot determine the session id (CODEX_THREAD_ID and CLAUDE_CODE_SESSION_ID both set and ambiguous); pass --session")
        if args.command == "recover":
            import task_recovery
            info = task_recovery.collect(args.session, args.cwd)
            print(task_recovery.render(info))
            return 2 if "fatal" in info else 0
        root = _root(args.root)
        if args.command in ("init", "bind"):
            _binding_path(args.session)
        path = _file(root, args.file, existing=args.command != "init")
        result = _cmd_init(args, root, path) if args.command == "init" else _dispatch(args, root, path)
        if result is None:
            return 0
        if "error" in result:
            raise ValueError(result["error"])
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
