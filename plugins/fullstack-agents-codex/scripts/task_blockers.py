"""Typed blockers for v2 task ledgers: block, resolve, withdraw and row resumption.

See docs/TASK_LIFECYCLE_DESIGN.md §13.1-13.2 (§13.10 and §14.6 items 1-3 win).
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import task_tracking
import task_rules
import task_checkpoint

BLK_START = "<!-- fsa:blockers:start -->"
BLK_END = "<!-- fsa:blockers:end -->"
SCHEMA = 1
KINDS = ("user", "row", "worker", "external")
EXTERNAL_CLASSES = ("capacity", "infrastructure", "other")
STATUSES = ("open", "resolved", "withdrawn")
KEYS_BASE = {"kind", "rows", "text", "why", "next", "created_at", "status", "resumes", "resolution"}
KEYS_EXTERNAL = KEYS_BASE | {"class"}
KEYS_CAPACITY = KEYS_EXTERNAL | {"engine", "until", "offer"}
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,31}\Z")
COMMANDS = ("block", "resolve", "withdraw")


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------- block I/O

def has_block(text):
    return BLK_START in text


def _find_block(text):
    start = text.find(BLK_START)
    if start == -1:
        return None
    end = text.find(BLK_END)
    if end == -1:
        raise ValueError("Blockers section missing its end marker")
    return start, end


def _validate_entry(identifier, entry):
    if not isinstance(entry, dict) or entry.get("kind") not in KINDS:
        raise ValueError(f"Blocker {identifier} has an invalid kind")
    kind, allowed = entry["kind"], KEYS_BASE
    if kind == "external":
        allowed = KEYS_CAPACITY if entry.get("class") == "capacity" else KEYS_EXTERNAL
    if not set(entry).issubset(allowed):
        raise ValueError(f"Blocker {identifier} has unknown keys: {sorted(set(entry) - allowed)}")
    if (allowed - {"offer"}) - set(entry):
        raise ValueError(f"Blocker {identifier} missing keys: {sorted((allowed - {'offer'}) - set(entry))}")
    if not isinstance(entry["rows"], list) or not entry["rows"] or not all(isinstance(r, str) and r for r in entry["rows"]):
        raise ValueError(f"Blocker {identifier}.rows must be a nonempty list of row ids")
    if not isinstance(entry["text"], str) or not entry["text"].strip():
        raise ValueError(f"Blocker {identifier}.text must be nonempty")
    if kind == "user" and not (isinstance(entry.get("why"), str) and entry["why"].strip()):
        raise ValueError(f"Blocker {identifier}.why is required for user blockers")
    if entry["status"] not in STATUSES:
        raise ValueError(f"Blocker {identifier}.status is invalid")
    if not isinstance(entry["resumes"], dict):
        raise ValueError(f"Blocker {identifier}.resumes must be an object")
    resolution = entry["resolution"]
    if resolution is not None and (not isinstance(resolution, dict) or set(resolution) != {"at", "by", "evidence", "reason"}):
        raise ValueError(f"Blocker {identifier}.resolution must have at, by, evidence, reason")
    if kind == "external":
        if entry.get("class") not in EXTERNAL_CLASSES:
            raise ValueError(f"Blocker {identifier}.class is invalid")
        if entry["class"] == "capacity" and not (isinstance(entry.get("engine"), str) and entry["engine"].strip()):
            raise ValueError(f"Blocker {identifier}.engine is required for capacity blockers")
    return entry


def load_block(text):
    """Always returns a well-shaped dict; a missing block is an empty one. Malformed is a clear error."""
    found = _find_block(text)
    if found is None:
        return {"schema": SCHEMA, "blockers": {}}
    start, end = found
    match = re.search(r"```json\s*\n(.*?)\n```", text[start:end], re.DOTALL)
    if not match:
        raise ValueError("Blockers section must contain a fenced json block")
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise ValueError(f"Blockers JSON is invalid: {error}") from error
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA or set(payload) != {"schema", "blockers"}:
        raise ValueError("Blockers block has an invalid schema")
    blockers = payload["blockers"]
    if not isinstance(blockers, dict):
        raise ValueError("Blockers block must map ids to entries")
    for identifier, entry in blockers.items():
        _validate_entry(identifier, entry)
    return {"schema": SCHEMA, "blockers": blockers}


def render_block(block):
    body = {"schema": SCHEMA, "blockers": block.get("blockers", {})}
    text = json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False)
    return f"{BLK_START}\n```json\n{text}\n```\n{BLK_END}\n"


def splice_block(text, section):
    """Replace an existing block in place, or insert one right after the task log."""
    found = _find_block(text)
    if found is not None:
        start, end = found
        end += len(BLK_END)
        if end < len(text) and text[end] == "\n":
            end += 1
        return text[:start] + section + text[end:]
    anchor = text.find(task_tracking.LOG_END)
    if anchor == -1:
        raise ValueError("Task log end marker not found")
    anchor += len(task_tracking.LOG_END)
    newline = text.find("\n", anchor)
    anchor = newline + 1 if newline != -1 else len(text)
    return text[:anchor] + "\n" + section + text[anchor:]


# ---------------------------------------------------------------- row helpers

def row_has_open_blocker(block, row):
    if block is None:
        return False
    return any(entry["status"] == "open" and row in entry["rows"] for entry in block["blockers"].values())


def _resume_status(block, row, current_status):
    if current_status != "blocked":
        return current_status
    for entry in block["blockers"].values():
        if entry["status"] == "open" and row in entry.get("resumes", {}):
            return entry["resumes"][row]
    return current_status


def _update_row_status(item, status):
    return task_tracking._item(item["id"], status, item["title"], item["note"], item["owner"], item["activity"],
                                item["active_until"], item.get("parent", ""), "v2")


def _resume_rows(block, items, entry, blocker_id, event):
    by_id = {item["id"]: item for item in items}
    resumed, logs = [], []
    for row in entry["rows"]:
        if row_has_open_blocker(block, row):
            continue
        item = by_id.get(row)
        if item is None or item["status"] != "blocked":
            continue
        target = entry["resumes"].get(row, "pending")
        item.update(_update_row_status(item, target))
        resumed.append(row)
        logs.append(task_rules.log_line(row, "status", **{"from": "blocked", "to": target,
                                                            "reason": f"blocker {blocker_id} {event}"}))
    return resumed, logs


def auto_resolve_rows(block, items, done_ids):
    """Resolve open `row` blockers whose prerequisite just became done, in the caller's same write."""
    if block is None or not done_ids:
        return []
    done_set, logs = set(done_ids), []
    for blocker_id, entry in block["blockers"].items():
        if entry["status"] != "open" or entry["kind"] != "row" or entry["text"] not in done_set:
            continue
        entry["status"] = "resolved"
        entry["resolution"] = {"at": _now(), "by": "tool", "evidence": f"{entry['text']} done_gate", "reason": ""}
        logs.append(task_rules.log_line(blocker_id, "resolve", kind="row", reason=""))
        _resumed, resume_logs = _resume_rows(block, items, entry, blocker_id, "resolved")
        logs.extend(resume_logs)
    return logs


# ---------------------------------------------------------------- write (ledger + checkpoint refresh)

def _open_lines(block):
    lines = []
    for identifier, entry in sorted(block["blockers"].items()):
        if entry["status"] != "open":
            continue
        rows = ",".join(entry["rows"])
        if entry["kind"] == "external" and entry.get("class") == "capacity":
            until = f" until {entry['until']}" if entry.get("until") else ""
            lines.append(f"{identifier}: capacity {entry['engine']}{until} — blocks {rows}")
        else:
            lines.append(f"{identifier}: {entry['kind']} {entry['text']} — blocks {rows}")
    return lines


def _write(path, text, items, start, end, block, logs, root, session, next_action=None):
    changed = task_tracking._mutated(text, items, start, end, "v2", logs)
    changed = splice_block(changed, render_block(block))
    refreshed, error = task_checkpoint.refresh_blockers(changed, root, path.stem, session, _open_lines(block), next_action)
    if error is not None:
        print(f"fsa-task: checkpoint not refreshed: {error}", file=sys.stderr)
    else:
        changed = refreshed
    task_tracking._atomic(path, changed)
    return changed


# ---------------------------------------------------------------- block

def _parse_rows(raw):
    rows = [row.strip() for row in raw.split(",") if row.strip()]
    if not rows:
        raise ValueError("--rows must name at least one task ID")
    return rows


def _next_id(block):
    numbers = [int(match.group(1)) for key in block["blockers"] if (match := re.fullmatch(r"B(\d+)", key))]
    return f"B{max(numbers, default=0) + 1}"


def _validate_block_args(args, rows):
    capacity = args.kind == "external" and args.cls == "capacity"
    if not args.text and not capacity:
        raise ValueError("--text is required")
    if args.kind == "user" and not args.why:
        raise ValueError("user blockers require --why")
    if args.kind == "external":
        if args.cls not in EXTERNAL_CLASSES:
            raise ValueError(f"--class must be one of {EXTERNAL_CLASSES} for external blockers")
        if args.cls == "capacity" and not args.engine:
            raise ValueError("capacity blockers require --engine")
        if args.cls != "capacity" and (args.engine or args.until or args.offer):
            raise ValueError("--engine/--until/--offer apply only to capacity blockers")
    elif args.cls or args.engine or args.until or args.offer:
        raise ValueError("--class/--engine/--until/--offer apply only to external blockers")
    if args.kind == "row" and args.text in rows:
        raise ValueError("a row cannot depend on itself")
    if args.id is not None and not ID_RE.fullmatch(args.id):
        raise ValueError("--id must be a short safe identifier")


def cmd_block(args, root, path):
    rows = _parse_rows(args.rows)
    _validate_block_args(args, rows)
    blocker_text = args.text or f"{args.engine} capacity exhausted"
    with task_tracking._lock(root, path):
        path, text = task_tracking._owned_text(args, root, path)
        items, start, end = task_tracking._parse(text)
        version, _width = task_tracking._format(text)
        if version != "v2":
            raise ValueError("Blockers require a v2 ledger")
        by_id = {item["id"]: item for item in items}
        for row in rows:
            if row not in by_id:
                raise ValueError(f"Unknown task ID: {row}")
        if args.kind == "row" and args.text not in by_id:
            raise ValueError(f"Unknown prerequisite row ID: {args.text}")
        block = load_block(text)
        identifier = args.id or _next_id(block)
        if identifier in block["blockers"]:
            raise ValueError(f"Blocker id already exists: {identifier}")
        entry = {"kind": args.kind, "rows": rows, "text": blocker_text, "why": args.why or "", "next": args.next or "",
                 "created_at": _now(), "status": "open",
                 "resumes": {row: _resume_status(block, row, by_id[row]["status"]) for row in rows}, "resolution": None}
        if args.kind == "external":
            entry["class"] = args.cls
            if args.cls == "capacity":
                entry["engine"], entry["until"] = args.engine, args.until or ""
                if args.offer:
                    entry["offer"] = args.offer
        block["blockers"][identifier] = _validate_entry(identifier, entry)
        logs = [task_rules.log_line(identifier, "block", kind=args.kind, rows=",".join(rows))]
        for row in rows:
            by_id[row].update(_update_row_status(by_id[row], "blocked"))
        _write(path, text, items, start, end, block, logs, root, args.session, args.next)
    return {"file": str(path), "id": identifier}


# ---------------------------------------------------------------- resolve

def _existing_file(root, raw):
    candidate = Path(raw).expanduser()
    candidate = candidate if candidate.is_absolute() else root / candidate
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise ValueError(f"Evidence file not found: {raw}")
    return resolved


def _reset_passed(resets_at, now):
    if not resets_at:
        return False
    try:
        parsed = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return False
    return parsed.tzinfo is not None and parsed.timestamp() < now


def _capacity_status(engine):
    try:
        import plan_usage
    except ImportError:
        return "unknown", None
    if engine == "claude":
        data = plan_usage.claude_plan(wait=False)
    elif engine == "codex":
        data = plan_usage.codex_plan()
    else:
        return "unknown", None
    if data.get("stale") or data.get("error"):
        return "unknown", None
    now = datetime.now(timezone.utc).timestamp()
    windows = data.get("windows") or []
    if any(w.get("pct") is not None and _reset_passed(w.get("resets_at"), now) for w in windows):
        return "unknown", None
    pcts = [window["pct"] for window in windows if window.get("pct") is not None]
    if not pcts:
        return "unknown", None
    tightest = max(pcts)
    return ("available" if tightest < 100 else "full"), tightest


def _resolve_capacity(args, entry, root):
    if args.quote:
        raise ValueError("capacity blockers resolve with --evidence, not --quote")
    status, pct = _capacity_status(entry["engine"])
    if status == "available":
        return f"plan_usage {entry['engine']} tightest window {pct:.0f}%"
    if args.evidence and args.reason:
        _existing_file(root, args.evidence)
        return args.evidence
    cause = "at or above 100%" if status == "full" else "unknown"
    raise ValueError(f"capacity blocker refused: {entry['engine']} window is {cause}; "
                      "resolve with --evidence <file> --reason for a manual observation")


def _resolve_evidence(args, entry, root, session):
    kind = entry["kind"]
    if kind == "row":
        raise ValueError("row blockers resolve automatically when the target row is marked done")
    if kind == "user":
        if args.evidence:
            raise ValueError("user blockers resolve with --quote, not --evidence")
        if not args.quote:
            raise ValueError("user blockers resolve with --quote")
        import prompt_history
        if not prompt_history.contains(session, args.quote):
            raise ValueError("quote not found in prompts recorded for this session")
        return args.quote
    if kind == "worker":
        if args.quote:
            raise ValueError("worker blockers resolve with --evidence, not --quote")
        if not args.evidence:
            raise ValueError("worker blockers resolve with --evidence <result.json>")
        found = _existing_file(root, args.evidence)
        try:
            data = json.loads(found.read_text())
        except (OSError, ValueError) as error:
            raise ValueError(f"worker evidence must be a readable JSON file: {error}") from error
        if not isinstance(data, dict) or "state" not in data:
            raise ValueError("worker evidence must be a result.json with a state field")
        return f"{args.evidence}: state={data['state']}"
    if entry.get("class") == "capacity":
        return _resolve_capacity(args, entry, root)
    if args.quote:
        raise ValueError("external blockers resolve with --evidence, not --quote")
    if not args.evidence or not args.reason:
        raise ValueError("external blockers resolve with --evidence <file> and --reason")
    _existing_file(root, args.evidence)
    return args.evidence


def cmd_resolve(args, root, path):
    with task_tracking._lock(root, path):
        path, text = task_tracking._owned_text(args, root, path)
        items, start, end = task_tracking._parse(text)
        version, _width = task_tracking._format(text)
        if version != "v2":
            raise ValueError("Blockers require a v2 ledger")
        block = load_block(text)
        entry = block["blockers"].get(args.id)
        if entry is None:
            raise ValueError(f"Unknown blocker id: {args.id}")
        if entry["status"] != "open":
            raise ValueError(f"Blocker {args.id} is not open")
        evidence_text = _resolve_evidence(args, entry, root, args.session)
        entry["status"] = "resolved"
        entry["resolution"] = {"at": _now(), "by": "tool", "evidence": evidence_text, "reason": args.reason or ""}
        logs = [task_rules.log_line(args.id, "resolve", kind=entry["kind"], reason=args.reason or "")]
        resumed, resume_logs = _resume_rows(block, items, entry, args.id, "resolved")
        logs.extend(resume_logs)
        _write(path, text, items, start, end, block, logs, root, args.session)
    result = {"file": str(path), "resumed": resumed}
    if entry["kind"] == "user":
        result["note"] = ("quote matched a recorded prompt; resolving records the lead's interpretation of the "
                          "user's answer and authorizes nothing else")
    return result


# ---------------------------------------------------------------- withdraw

def cmd_withdraw(args, root, path):
    if not args.reason:
        raise ValueError("withdraw requires --reason")
    with task_tracking._lock(root, path):
        path, text = task_tracking._owned_text(args, root, path)
        items, start, end = task_tracking._parse(text)
        version, _width = task_tracking._format(text)
        if version != "v2":
            raise ValueError("Blockers require a v2 ledger")
        block = load_block(text)
        entry = block["blockers"].get(args.id)
        if entry is None:
            raise ValueError(f"Unknown blocker id: {args.id}")
        if entry["status"] != "open":
            raise ValueError(f"Blocker {args.id} is not open")
        entry["status"] = "withdrawn"
        entry["resolution"] = {"at": _now(), "by": "tool", "evidence": "", "reason": args.reason}
        logs = [task_rules.log_line(args.id, "withdraw", kind=entry["kind"], reason=args.reason)]
        resumed, resume_logs = _resume_rows(block, items, entry, args.id, "withdrawn")
        logs.extend(resume_logs)
        _write(path, text, items, start, end, block, logs, root, args.session)
    return {"file": str(path), "resumed": resumed}


# ---------------------------------------------------------------- CLI wiring

def add_arguments(command, sub):
    if command == "block":
        sub.add_argument("--rows", required=True)
        sub.add_argument("--kind", required=True, choices=KINDS)
        sub.add_argument("--text", help="Required unless --kind external --class capacity (defaults to "
                                         "'<engine> capacity exhausted')")
        sub.add_argument("--why")
        sub.add_argument("--class", dest="cls", choices=EXTERNAL_CLASSES)
        sub.add_argument("--engine")
        sub.add_argument("--until")
        sub.add_argument("--offer")
        sub.add_argument("--next")
        sub.add_argument("--id")
    elif command == "resolve":
        sub.add_argument("--id", required=True)
        sub.add_argument("--quote")
        sub.add_argument("--evidence")
        sub.add_argument("--reason")
    elif command == "withdraw":
        sub.add_argument("--id", required=True)
        sub.add_argument("--reason", required=True)


def dispatch(args, root, path):
    if args.command == "block":
        return cmd_block(args, root, path)
    if args.command == "resolve":
        return cmd_resolve(args, root, path)
    if args.command == "withdraw":
        return cmd_withdraw(args, root, path)
    raise ValueError(f"Unknown blocker command: {args.command}")
