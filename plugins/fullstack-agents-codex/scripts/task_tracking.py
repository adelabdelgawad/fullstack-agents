"""Bounded, explicit Markdown task ledgers shared by dashboard and agent CLIs."""
import argparse
from collections import Counter
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

START = "<!-- fsa:tasks:start -->"
END = "<!-- fsa:tasks:end -->"
STATUSES = ("pending", "running", "blocked", "done", "skipped", "canceled")
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
    if len(cells) != 4:
        raise ValueError("Malformed task table row: expected exactly four columns")
    return cells


def _item(identifier, status, title, note):
    if not isinstance(identifier, str) or not TASK_ID.fullmatch(identifier):
        raise ValueError("Task ID must be a safe nonempty identifier of at most 64 characters")
    if status not in STATUSES:
        raise ValueError(f"Invalid task status: {status}")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Task title must be nonempty")
    for value in (identifier, status, title, note):
        if not isinstance(value, str) or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Task cells must be single-line text without control characters")
        if START in value or END in value:
            raise ValueError("Task cells cannot contain ledger markers")
    return {"id": identifier, "status": status, "title": title.strip(), "note": note.strip()}


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
    if len(rows) < 2 or _cells(rows[0]) != ["ID", "Status", "Task", "Note"]:
        raise ValueError("Task table header must be ID | Status | Task | Note")
    if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in _cells(rows[1])):
        raise ValueError("Malformed task table separator")
    if len(rows) - 2 > MAX_ROWS:
        raise ValueError(f"Task table exceeds {MAX_ROWS} rows")
    items, identifiers = [], set()
    for row in rows[2:]:
        item = _item(*_cells(row))
        if item["id"] in identifiers:
            raise ValueError(f"Duplicate task ID: {item['id']}")
        identifiers.add(item["id"])
        items.append(item)
    return items, start + len(START), end


def _render(items):
    def cell(value):
        return value.replace("\\", "\\\\").replace("|", "\\|")
    lines = ["| ID | Status | Task | Note |", "| --- | --- | --- | --- |"]
    lines.extend("| " + " | ".join(cell(item[key]) for key in ("id", "status", "title", "note")) + " |" for item in items)
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


def bind_tasks(session_id, root, filename):
    binding = _binding_path(session_id)
    root = _root(root)
    path = _file(root, filename)
    _parse(_read(path))
    _atomic(binding, json.dumps({"session_id": session_id, "root": str(root), "file": str(path)}, ensure_ascii=False) + "\n")
    return load_tasks(session_id, root)


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
        if _root(cwd) != root:
            raise ValueError("Task registration root does not match the session cwd")
        path = _file(root, record["file"])
        info = {"file": str(path), "relative_file": str(path.relative_to(root))}
        text = _read(path)
        items, _, _ = _parse(text)
        title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), path.stem)
        counts = dict.fromkeys(STATUSES, 0)
        counts.update(Counter(item["status"] for item in items))
        return {**info, "title": title, "updated": path.stat().st_mtime, "items": items,
                "counts": counts, "total": len(items), "completed": counts["done"]}
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        return {**info, "error": str(error)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Register and update an explicit Markdown task ledger")
    actions = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "bind", "set"):
        sub = actions.add_parser(command)
        sub.add_argument("--root", required=True)
        sub.add_argument("--file", required=True)
        sub.add_argument("--session", default=os.environ.get("CODEX_THREAD_ID") or os.environ.get("CLAUDE_SESSION_ID"))
        if command == "init":
            sub.add_argument("--title", default="Tasks")
            sub.add_argument("--task", action="append", default=[], help="ID|status|title|note (repeatable)")
        if command == "set":
            sub.add_argument("--id", required=True)
            sub.add_argument("--status", required=True, choices=STATUSES)
            sub.add_argument("--note")
    args = parser.parse_args(argv)
    try:
        root = _root(args.root)
        if args.command in ("init", "bind"):
            _binding_path(args.session)
        path = _file(root, args.file, existing=args.command != "init")
        if args.command == "init":
            _item("title", "pending", args.title, "")
            items = []
            for task in args.task:
                values = task.split("|", 3)
                if len(values) != 4:
                    raise ValueError("--task requires ID|status|title|note")
                items.append(_item(*(value.strip() for value in values)))
            text = f"# {args.title}\n\n{START}{_render(items)}{END}\n"
            _parse(text)
            with _lock(root, path):
                if path.exists() or path.is_symlink():
                    raise ValueError("Task file already exists; init never overwrites it")
                _file(root, path, existing=False)
                _atomic(path, text, exclusive=True)
            result = bind_tasks(args.session, root, path)
        elif args.command == "bind":
            result = bind_tasks(args.session, root, path)
        else:
            with _lock(root, path):
                path = _file(root, args.file)
                text = _read(path)
                items, start, end = _parse(text)
                task = next((item for item in items if item["id"] == args.id), None)
                if task is None:
                    raise ValueError(f"Unknown task ID: {args.id}")
                task.update(_item(task["id"], args.status, task["title"], task["note"] if args.note is None else args.note))
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
