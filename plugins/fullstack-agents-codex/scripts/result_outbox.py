"""Result outbox: a report is saved before it is sent, evidence records only what the host proves was emitted
(never received), and a pending or uncertain report can be offered again after a handover without rerunning work.
See docs/TASK_LIFECYCLE_DESIGN.md §15 (Unit D)."""
import hashlib
import os
from pathlib import Path
import re
import sys

import coordination_log

ID = re.compile(r"O(\d+)")
EVIDENCE_EVENTS = ("report.emitted", "report.uncertain")


def _outbox_dir(cwd):
    return coordination_log._coordination_dir() / f"{coordination_log._key(cwd)}.outbox"


def _ensure_outbox_dir(cwd):
    directory = _outbox_dir(cwd)
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    return directory


def _report_path(cwd, report_id):
    return _outbox_dir(cwd) / f"{report_id}.md"


def _write_outbox_file(cwd, report_id, data):
    _ensure_outbox_dir(cwd)
    fd = os.open(_report_path(cwd, report_id), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def _normalize(text):
    return " ".join(text.split())


def _read_body(cwd, report_id):
    try:
        return _report_path(cwd, report_id).read_text()
    except OSError:
        return ""


# ---------------------------------------------------------------- folding


def _fold(events):
    reports = {}
    for event in events:
        etype, rid = event.get("type"), event.get("id")
        if etype == "report.prepared" and isinstance(rid, str):
            reports[rid] = {"id": rid, "seq": event.get("seq"), "session": event.get("session"),
                             "sha256": event.get("sha256"), "request": event.get("request"),
                             "rows": event.get("rows") or [], "evidence": []}
            continue
        entry = reports.get(rid)
        if entry is None or etype not in EVIDENCE_EVENTS:
            continue
        entry["evidence"].append({"type": etype, "evidence": event.get("evidence"),
                                   "session": event.get("session"), "at": event.get("at"), "seq": event.get("seq")})
    return reports


def _state(entry):
    if any(item["type"] == "report.emitted" for item in entry["evidence"]):
        return "emitted"
    return "uncertain" if entry["evidence"] else "prepared"


def oldest_unconfirmed(cwd, session):
    """Oldest report this session prepared that carries no evidence event yet (stop guard hold, §ACCEPTANCE 3)."""
    candidates = [r for r in _fold(coordination_log.read(cwd)["events"]).values()
                  if r["session"] == session and not r["evidence"]]
    if not candidates:
        return None
    return min(candidates, key=lambda entry: entry["seq"])["id"]


# ---------------------------------------------------------------- emission evidence (Stop hook)


def _detect_evidence(report, final_message, earlier_texts, body):
    marker = f"[report {report['id']}]"
    normalized_body = _normalize(body)
    if marker in final_message:
        if not normalized_body:
            return "body_unavailable"
        return "final_reply" if normalized_body in _normalize(final_message) else "marker_only"
    for text in earlier_texts:
        if marker in text or (normalized_body and normalized_body in _normalize(text)):
            return "mid_turn_text"
    return None


def record_emission(cwd, session, final_message, earlier_texts=()):
    """Append `report.emitted`/`report.uncertain` from what the host proves was in the reply; never raises."""
    if not isinstance(cwd, str) or not cwd or not isinstance(session, str) or not session:
        return
    final_message = final_message if isinstance(final_message, str) else ""
    earlier_texts = [text for text in earlier_texts if isinstance(text, str)]
    try:
        with coordination_log.locked(cwd) as path:
            events = coordination_log.read_path(path)["events"]
            for report in _fold(events).values():
                if _state(report) == "emitted":
                    continue
                evidence = _detect_evidence(report, final_message, earlier_texts, _read_body(cwd, report["id"]))
                if evidence is None:
                    continue
                if any(item["evidence"] == evidence and item["session"] == session for item in report["evidence"]):
                    continue
                etype = "report.emitted" if evidence == "final_reply" else "report.uncertain"
                coordination_log.append_locked(path, session, etype, id=report["id"], evidence=evidence)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"result_outbox: emission capture failed: {error}", file=sys.stderr)


# ---------------------------------------------------------------- SessionStart notice


def _preview(cwd, report_id):
    text = _normalize(_read_body(cwd, report_id))
    return text if len(text) <= 80 else text[:79] + "…"


def session_start_line(cwd):
    pending = [r for r in _fold(coordination_log.read(cwd)["events"]).values() if _state(r) in ("prepared", "uncertain")]
    if not pending:
        return None
    ordered = sorted(pending, key=lambda entry: entry["seq"])
    parts = [f'{r["id"]} {_state(r)} "{_preview(cwd, r["id"])}"' for r in ordered]
    return "Pending reports: " + "; ".join(parts)


# ---------------------------------------------------------------- CLI


def _parse_rows(raw):
    rows = [row.strip() for row in raw.split(",") if row.strip()]
    if not rows:
        raise ValueError("--rows must name at least one row id")
    return rows


def _next_report_id(events):
    numbers = [int(match.group(1)) for event in events if event.get("type") == "report.prepared"
               for match in [ID.fullmatch(str(event.get("id", "")))] if match]
    return f"O{max(numbers, default=0) + 1}"


def cmd_save(args, root):
    if not args.file:
        raise ValueError("report save requires --file")
    data = Path(args.file).expanduser().read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    rows = _parse_rows(args.rows) if args.rows else []
    with coordination_log.locked(root) as path:
        events = coordination_log.read_path(path)["events"]
        existing = next((r for r in _fold(events).values() if r["sha256"] == digest), None)
        if existing is not None:
            if not _report_path(root, existing["id"]).is_file():
                _write_outbox_file(root, existing["id"], data)
            print(f"[report {existing['id']}]")
            return {"id": existing["id"], "created": False}
        rid = _next_report_id(events)
        _write_outbox_file(root, rid, data)
        coordination_log.append_locked(path, args.session, "report.prepared", id=rid, sha256=digest,
                                        request=args.request, rows=rows)
    print(f"[report {rid}]")
    return {"id": rid, "created": True}


def cmd_list(_args, root):
    reports = _fold(coordination_log.read(root)["events"])
    ordered = sorted(reports.values(), key=lambda entry: entry["seq"])
    items = []
    for report in ordered:
        try:
            _report_path(root, report["id"]).read_bytes()
            state = _state(report)
        except OSError:
            state = "missing_file"
        items.append({"id": report["id"], "state": state, "request": report["request"], "rows": report["rows"]})
    return {"reports": items}


def cmd_show(args, root):
    reports = _fold(coordination_log.read(root)["events"])
    if args.id not in reports:
        raise ValueError(f"Unknown report id: {args.id}")
    report = reports[args.id]
    try:
        text = _report_path(root, args.id).read_text()
    except OSError as error:
        raise ValueError(f"report file missing or unreadable: {error}") from error
    if report["evidence"]:
        first = min(report["evidence"], key=lambda item: item["seq"])
        print(f"REPEAT of {args.id} (first emitted {first['at']}, delivery unconfirmed)")
    print(text, end="" if text.endswith("\n") else "\n")
    return None


def add_arguments(command, sub):
    if command != "report":
        return
    actions = sub.add_subparsers(dest="report_action", required=True)
    save = actions.add_parser("save")
    save.add_argument("--request")
    save.add_argument("--rows")
    actions.add_parser("list")
    show = actions.add_parser("show")
    show.add_argument("--id", required=True)


def dispatch(args, root):
    handlers = {"save": cmd_save, "list": cmd_list, "show": cmd_show}
    return handlers[args.report_action](args, root)
