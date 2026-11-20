"""Durable request inbox: captures genuine prompts at UserPromptSubmit and folds them for `fsa-task request`; see docs/TASK_LIFECYCLE_DESIGN.md §15."""
from datetime import datetime
import hashlib
import re
import sys
import time

import coordination_log

CAP_BYTES = 64 * 1024
DUP_WINDOW = 2.0
CLASSES = ("supplementary", "queued", "correction", "status", "pause", "cancel", "approval", "answer", "other")
AS_VALUES = CLASSES + ("ambiguous",)


def _cap(text):
    encoded = text.encode("utf-8")
    return text if len(encoded) <= CAP_BYTES else encoded[:CAP_BYTES].decode("utf-8", "ignore")


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_at(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError, TypeError):
        return None


def _duplicate(events, session, host_id, digest, now):
    """Same session + host_id + text matches regardless of age; with no host_id, same text within DUP_WINDOW
    matches. The same host_id with different text is not a duplicate: it is a mid-turn message (see _mid_turn)."""
    received = [event for event in events if event.get("type") == "request.received" and event.get("session") == session]
    if host_id:
        return next((event for event in reversed(received)
                     if event.get("host_id") == host_id and event.get("text_sha256") == digest), None)
    for event in reversed(received):
        if event.get("host_id") or event.get("text_sha256") != digest:
            continue
        at = _parse_at(event.get("at"))
        if at is not None and now - at <= DUP_WINDOW:
            return event
    return None


def _mid_turn(events, session, host_id):
    """True when this host_id already delivered a request for this session: a message sent while that turn is
    still running, carrying its running prompt_id and different text (see _duplicate)."""
    return any(event.get("type") == "request.received" and event.get("session") == session
               and event.get("host_id") == host_id for event in events)


def _next_request_id(events):
    numbers = [int(match.group(1)) for event in events if event.get("type") == "request.received"
               for match in [re.fullmatch(r"R(\d+)", str(event.get("id", "")))] if match]
    return f"R{max(numbers, default=0) + 1}"


def _mark_capture_failed(cwd, error):
    print(f"fsa-request-inbox: capture failed: {error}", file=sys.stderr)
    try:
        coordination_log.mark_capture_failed(cwd)
    except OSError:
        pass


def capture(hook):
    """Append `request.received` for a genuine prompt; idempotent on duplicate hook delivery. The read, duplicate
    check and append all happen under one held lock so two concurrent captures can neither pick the same id nor
    both miss a duplicate. Never raises: a storage failure is reported on stderr and marked, and the hook keeps
    running."""
    if not isinstance(hook, dict):
        return None
    session, cwd, text = hook.get("session_id"), hook.get("cwd"), hook.get("prompt")
    if not isinstance(session, str) or not isinstance(cwd, str) or not isinstance(text, str) or not text.strip():
        return None
    if coordination_log.is_notification(text):
        return None
    capped = _cap(text)
    digest = _digest(capped)
    host_id = hook.get("prompt_id")
    host_id = host_id if isinstance(host_id, str) and host_id else None
    moment = time.time()
    try:
        with coordination_log.locked(cwd) as path:
            events = coordination_log.read_path(path)["events"]
            duplicate = _duplicate(events, session, host_id, digest, moment)
            if duplicate is not None:
                coordination_log.append_locked(path, session, "request.duplicate_delivery", id=duplicate["id"])
                return duplicate["id"]
            rid = _next_request_id(events)
            fields = {"id": rid, "text": capped, "text_sha256": digest, "host_id": host_id, "origin": None}
            if host_id is not None and _mid_turn(events, session, host_id):
                fields["mid_turn"] = True
            coordination_log.append_locked(path, session, "request.received", **fields)
            return rid
    except OSError as error:
        _mark_capture_failed(cwd, error)
        return None


# ---------------------------------------------------------------- folding


OPEN_CLASSES = ("unclassified", "ambiguous")


def _execution(entry):
    done = entry["_done"]
    if done is not None:
        return "dropped" if done["dropped"] else "done"
    if entry["class"] == "queued":
        return "queued"
    if entry["linked_rows"]:
        return "active"
    return "none"


def _fold(events):
    requests = {}
    for event in events:
        etype, rid = event.get("type"), event.get("id")
        if etype == "request.received" and isinstance(rid, str):
            requests[rid] = {"id": rid, "seq": event.get("seq"), "session": event.get("session"),
                              "at": event.get("at"), "text": event.get("text", ""),
                              "text_sha256": event.get("text_sha256"), "host_id": event.get("host_id"),
                              "mid_turn": bool(event.get("mid_turn")),
                              "class": "unclassified", "note": "", "rows": [], "linked_rows": [], "_done": None}
            continue
        entry = requests.get(rid)
        if entry is None:
            continue
        if etype == "request.classified":
            as_value = event.get("as")
            entry["class"], entry["note"] = as_value, event.get("note") or ""
            if as_value != "ambiguous":
                entry["rows"] = event.get("rows") or []
        elif etype == "request.linked":
            entry["linked_rows"] = sorted(set(entry["linked_rows"]) | set(event.get("rows") or []))
        elif etype == "request.done":
            entry["_done"] = {"dropped": bool(event.get("dropped")), "reason": event.get("reason") or ""}
    for entry in requests.values():
        entry["open"] = entry["class"] in OPEN_CLASSES
        entry["execution"] = _execution(entry)
    return requests


def oldest_unclassified(cwd, session):
    candidates = [r for r in _fold(coordination_log.read(cwd)["events"]).values()
                  if r["session"] == session and r["class"] == "unclassified"]
    if not candidates:
        return None
    return min(candidates, key=lambda entry: entry["seq"])["id"]


def open_requests(cwd):
    """Unclassified or ambiguous requests of the project, oldest first, regardless of session."""
    requests = _fold(coordination_log.read(cwd)["events"]).values()
    return sorted((r for r in requests if r["class"] in OPEN_CLASSES), key=lambda entry: entry["seq"])


# ---------------------------------------------------------------- CLI


def _parse_rows(raw):
    rows = [row.strip() for row in raw.split(",") if row.strip()]
    if not rows:
        raise ValueError("--rows must name at least one row id")
    return rows


def _preview(text):
    return text if len(text) <= 80 else text[:79] + "…"


def _require(requests, rid):
    if rid not in requests:
        raise ValueError(f"Unknown request id: {rid}")


def cmd_list(args, root):
    if getattr(args, "ack_capture_failure", False):
        coordination_log.ack_capture_failed(root)
    requests = _fold(coordination_log.read(root)["events"])
    ordered = sorted(requests.values(), key=lambda entry: entry["seq"])
    return {"requests": [{"id": r["id"], "class": r["class"], "execution": r["execution"], "open": r["open"],
                           "preview": _preview(r["text"])} for r in ordered]}


def cmd_show(args, root):
    requests = _fold(coordination_log.read(root)["events"])
    _require(requests, args.id)
    return {key: value for key, value in requests[args.id].items() if key not in ("seq", "_done")}


def cmd_classify(args, root):
    if args.as_class not in AS_VALUES:
        raise ValueError(f"Unknown classification: {args.as_class}")
    requests = _fold(coordination_log.read(root)["events"])
    _require(requests, args.id)
    rows = _parse_rows(args.rows) if args.rows else []
    coordination_log.append(root, args.session, "request.classified",
                             **{"id": args.id, "as": args.as_class, "rows": rows, "note": args.note or ""})
    return {"id": args.id, "as": args.as_class}


def cmd_link(args, root):
    requests = _fold(coordination_log.read(root)["events"])
    _require(requests, args.id)
    rows = _parse_rows(args.rows)
    coordination_log.append(root, args.session, "request.linked", id=args.id, rows=rows)
    return {"id": args.id, "rows": rows}


def cmd_done(args, root):
    requests = _fold(coordination_log.read(root)["events"])
    _require(requests, args.id)
    if args.dropped and not (args.reason and args.reason.strip()):
        raise ValueError("--dropped requires --reason")
    coordination_log.append(root, args.session, "request.done", id=args.id,
                             dropped=bool(args.dropped), reason=args.reason or "")
    return {"id": args.id, "execution": "dropped" if args.dropped else "done"}


def add_arguments(command, sub):
    if command != "request":
        return
    actions = sub.add_subparsers(dest="request_action", required=True)
    listing = actions.add_parser("list")
    listing.add_argument("--ack-capture-failure", dest="ack_capture_failure", action="store_true")
    show = actions.add_parser("show")
    show.add_argument("--id", required=True)
    classify = actions.add_parser("classify")
    classify.add_argument("--id", required=True)
    classify.add_argument("--as", dest="as_class", required=True)
    classify.add_argument("--rows")
    classify.add_argument("--note")
    link = actions.add_parser("link")
    link.add_argument("--id", required=True)
    link.add_argument("--rows", required=True)
    done = actions.add_parser("done")
    done.add_argument("--id", required=True)
    done.add_argument("--dropped", action="store_true")
    done.add_argument("--reason")


def dispatch(args, root):
    handlers = {"list": cmd_list, "show": cmd_show, "classify": cmd_classify, "link": cmd_link, "done": cmd_done}
    return handlers[args.request_action](args, root)
