"""Scoped, append-only control records (pause/approval/deploy_hold): only the lead sets or lifts them against a
captured request; hooks only append candidates. See docs/TASK_LIFECYCLE_DESIGN.md §15."""
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coordination_log
import request_inbox

KINDS = ("pause", "approval", "deploy_hold")
SCOPE_LEVELS = ("project", "task", "rows")
CONTROL_ID = re.compile(r"C(\d+)")
FENCE = re.compile(r"```.*?```", re.DOTALL)
BLOCKQUOTE = re.compile(r"^[ \t]*>.*$", re.MULTILINE)
QUOTED_SPAN = re.compile(r'"[^"\n]{1,500}"|“[^”\n]{1,500}”|`[^`\n]{1,500}`')


def strip_quoted(text):
    """Fenced code, `>` lines and quoted spans removed, so pasted/quoted material cannot forge a candidate."""
    cleaned = FENCE.sub(" ", text)
    cleaned = BLOCKQUOTE.sub(" ", cleaned)
    return QUOTED_SPAN.sub(" ", cleaned)


def _normalize(text):
    return " ".join(text.split())


def quote_ok(text, quote):
    if not isinstance(quote, str):
        return False
    normalized = _normalize(quote)
    return len(normalized) >= 8 and normalized in _normalize(text)


# ---------------------------------------------------------------- row/task identity


def _project_top(cwd):
    return Path(coordination_log._project_root(cwd)).resolve()


def bound_task_id(session_id, cwd):
    """<ledger path relative to the project top-level>, realpathed; None when unbound or unreadable."""
    import task_tracking
    ledger = task_tracking.load_tasks(session_id, cwd)
    if not ledger or ledger.get("error") or "file" not in ledger:
        return None
    try:
        return str(Path(ledger["file"]).resolve().relative_to(_project_top(cwd)))
    except ValueError:
        return None


def _row_keys(task_id, rows):
    return [f"{task_id}#{row}" for row in rows]


def _build_scope(kind, level, task_id, rows):
    if level not in SCOPE_LEVELS:
        raise ValueError(f"Unknown scope level: {level}")
    if level == "rows" and kind == "deploy_hold":
        raise ValueError("deploy_hold scope cannot be rows; a Bash command has no row context")
    if level == "project":
        return {"level": "project"}
    if task_id is None:
        raise ValueError(f"scope {level} requires a bound task ledger for this session")
    if level == "task":
        return {"level": "task", "task": task_id}
    return {"level": "rows", "task": task_id, "rows": _row_keys(task_id, rows)}


def _parse_rows(raw):
    rows = [row.strip() for row in (raw or "").split(",") if row.strip()]
    if not rows:
        raise ValueError("--rows must name at least one row id")
    return rows


# ---------------------------------------------------------------- folding


def _fold(events):
    controls, candidates = {}, {}
    for event in events:
        etype = event.get("type")
        if etype == "control.set":
            cid = event.get("id")
            if not isinstance(cid, str):
                continue
            controls[cid] = {"id": cid, "kind": event.get("kind"), "scope": event.get("scope") or {},
                              "quote": event.get("quote", ""), "request": event.get("request"),
                              "provenance": event.get("provenance") or {}, "set_seq": event.get("seq"),
                              "lifted": False}
            if event.get("request"):
                key = (event["request"], event.get("kind"))
                candidates.setdefault(key, {"resolved": False})["resolved"] = True
        elif etype == "control.narrow":
            control = controls.get(event.get("id"))
            if control and not control["lifted"]:
                control["scope"] = event.get("scope") or control["scope"]
        elif etype == "control.lift":
            control = controls.get(event.get("id"))
            if control:
                control["lifted"] = True
        elif etype == "control.candidate":
            key = (event.get("request"), event.get("kind"))
            entry = candidates.setdefault(key, {"resolved": False})
            entry.setdefault("sentence", event.get("sentence", ""))
            entry.setdefault("seq", event.get("seq"))
        elif etype == "control.dismiss":
            key = (event.get("request"), event.get("kind"))
            entry = candidates.setdefault(key, {"resolved": False})
            entry.update(resolved=True, dismissed=True, reason=event.get("reason", ""))
            entry.setdefault("sentence", event.get("sentence", ""))
    return controls, candidates


def active_controls(cwd, session_id, kind=None):
    """Controls applicable to this session: project always; task when unbound or matching; rows when matching."""
    controls, _ = _fold(coordination_log.read(cwd)["events"])
    task_id = bound_task_id(session_id, cwd)
    result = []
    for control in controls.values():
        if control["lifted"] or (kind is not None and control["kind"] != kind):
            continue
        level = control["scope"].get("level")
        if level == "project":
            result.append(control)
        elif level in ("task", "rows") and control["scope"].get("task") == task_id:
            result.append(control)
        elif level == "task" and task_id is None:
            result.append(control)
    return result


def active_deploy_hold(cwd, session_id):
    controls = active_controls(cwd, session_id, kind="deploy_hold")
    return max(controls, key=lambda c: c["set_seq"]) if controls else None


def unresolved_project_candidate(cwd, kind):
    """Oldest unresolved candidate of `kind` anywhere in the project (deploy_hold fail-closed is project-wide)."""
    _, candidates = _fold(coordination_log.read(cwd)["events"])
    pending = [{"request": req, "sentence": info.get("sentence", ""), "seq": info.get("seq", 0)}
               for (req, candidate_kind), info in candidates.items()
               if candidate_kind == kind and req and not info.get("resolved")]
    return min(pending, key=lambda c: c["seq"]) if pending else None


def unresolved_session_candidate(cwd, session_id, kind):
    """Oldest unresolved candidate of `kind` among requests this session captured (mirrors oldest_unclassified)."""
    events = coordination_log.read(cwd)["events"]
    requests = request_inbox._fold(events)
    _, candidates = _fold(events)
    pending = [{"request": req, "sentence": info.get("sentence", ""), "seq": info.get("seq", 0)}
               for (req, candidate_kind), info in candidates.items()
               if candidate_kind == kind and req and not info.get("resolved")
               and requests.get(req, {}).get("session") == session_id]
    return min(pending, key=lambda c: c["seq"]) if pending else None


def record_candidate(cwd, session, request, kind, sentence):
    """Append one `control.candidate`; idempotent per (request, kind), never rewrites a resolved one."""
    if not request:
        return
    with coordination_log.locked(cwd) as path:
        events = coordination_log.read_path(path)["events"]
        _, candidates = _fold(events)
        if (request, kind) in candidates:
            return
        coordination_log.append_locked(path, session, "control.candidate", request=request, kind=kind,
                                        sentence=sentence[:200])


# ---------------------------------------------------------------- legacy mirror (deploy-holds/<session>.json)


def mirror_deploy_hold(cwd, session_id):
    """Write the per-session mirror only when there is no hold file yet, or the existing one is already a mirror
    (carries `control_id`); a legacy hold file with no `control_id` is never overwritten."""
    import deploy_hold
    control = active_deploy_hold(cwd, session_id)
    if control is None:
        return
    held = deploy_hold.read_hold(session_id)
    if held is not None and not held.get("control_id"):
        return
    deploy_hold.set_hold(session_id, control["quote"], control["id"])


def remove_mirrors_for_control(control_id):
    import deploy_hold
    directory = deploy_hold.hold_dir()
    if not directory.is_dir():
        return
    for file in directory.glob("*.json"):
        try:
            data = json.loads(file.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("control_id") == control_id:
            file.unlink(missing_ok=True)


# ---------------------------------------------------------------- CLI


def _next_control_id(events):
    numbers = [int(match.group(1)) for event in events if event.get("type") == "control.set"
               for match in [CONTROL_ID.fullmatch(str(event.get("id", "")))] if match]
    return f"C{max(numbers, default=0) + 1}"


def _require_control(controls, cid):
    control = controls.get(cid)
    if control is None or control["lifted"]:
        raise ValueError(f"Unknown or already-lifted control: {cid}")
    return control


def _quote_against_request(events, rid, quote):
    requests = request_inbox._fold(events)
    if rid not in requests:
        raise ValueError(f"Unknown request id: {rid}")
    entry = requests[rid]
    if not quote_ok(entry["text"], quote):
        raise ValueError("--quote does not occur in the captured request text")
    return entry


def cmd_set(args, root):
    if args.kind not in KINDS:
        raise ValueError(f"Unknown control kind: {args.kind}")
    if bool(args.request) == bool(args.evidence):
        raise ValueError("control set requires exactly one of --request or --evidence")
    if args.evidence and args.kind != "deploy_hold":
        raise ValueError("--evidence is only accepted for --kind deploy_hold; pause and approval need --request")
    if args.scope_ambiguous and not args.evidence:
        raise ValueError("--scope-ambiguous requires --evidence")
    rows = _parse_rows(args.rows) if args.scope == "rows" else None
    with coordination_log.locked(root) as path:
        events = coordination_log.read_path(path)["events"]
        task_id = bound_task_id(args.session, root) if args.scope in ("task", "rows") else None
        scope = _build_scope(args.kind, args.scope, task_id, rows)
        if args.request:
            _quote_against_request(events, args.request, args.quote)
            provenance = {"source": "user_prompt", "session": args.session}
        else:
            text = Path(args.evidence).read_text()
            if not quote_ok(text, args.quote):
                raise ValueError("--quote does not occur in the evidence file")
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            provenance = {"source": "lead_recovery", "session": args.session, "evidence": str(args.evidence),
                          "evidence_sha256": digest}
        if args.scope_ambiguous:
            scope["scope_ambiguous"] = True
        cid = _next_control_id(events)
        coordination_log.append_locked(path, args.session, "control.set", id=cid, kind=args.kind, scope=scope,
                                        quote=args.quote, request=args.request, provenance=provenance)
        if args.kind == "deploy_hold":
            mirror_deploy_hold(root, args.session)
    return {"id": cid, "kind": args.kind, "scope": scope}


def cmd_lift(args, root):
    with coordination_log.locked(root) as path:
        events = coordination_log.read_path(path)["events"]
        controls, _ = _fold(events)
        control = _require_control(controls, args.id)
        entry = _quote_against_request(events, args.request, args.quote)
        if entry["seq"] < control["set_seq"]:
            raise ValueError("lift refused: the request predates the control")
        coordination_log.append_locked(path, args.session, "control.lift", id=args.id, request=args.request,
                                        quote=args.quote)
        remove_mirrors_for_control(args.id)
    return {"id": args.id, "lifted": True}


def _strictly_inside(old, new):
    """project > task > rows of that task, rows a subset: the only relations `narrow` may apply."""
    old_rank, new_rank = SCOPE_LEVELS.index(old["level"]), SCOPE_LEVELS.index(new["level"])
    if new_rank <= old_rank:
        if old["level"] != new["level"] or old["level"] != "rows":
            return False
        return set(new["rows"]) < set(old["rows"])
    if old["level"] == "project":
        return True
    return new.get("task") == old.get("task")


def cmd_narrow(args, root):
    rows = _parse_rows(args.rows) if args.scope == "rows" else None
    with coordination_log.locked(root) as path:
        events = coordination_log.read_path(path)["events"]
        controls, _ = _fold(events)
        control = _require_control(controls, args.id)
        entry = _quote_against_request(events, args.request, args.quote)
        if entry["seq"] < control["set_seq"]:
            raise ValueError("narrow refused: the request predates the control")
        task_id = bound_task_id(args.session, root) if args.scope in ("task", "rows") else None
        scope = _build_scope(control["kind"], args.scope, task_id, rows)
        if not _strictly_inside(control["scope"], scope):
            raise ValueError("narrow refused: the new scope is not strictly inside the current scope")
        coordination_log.append_locked(path, args.session, "control.narrow", id=args.id, scope=scope,
                                        request=args.request, quote=args.quote)
    return {"id": args.id, "scope": scope}


def cmd_dismiss(args, root):
    with coordination_log.locked(root) as path:
        events = coordination_log.read_path(path)["events"]
        requests = request_inbox._fold(events)
        if args.request not in requests:
            raise ValueError(f"Unknown request id: {args.request}")
        if not args.reason or not args.reason.strip():
            raise ValueError("control dismiss requires --reason")
        _, candidates = _fold(events)
        candidate = candidates.get((args.request, args.kind))
        if candidate is None or candidate.get("resolved"):
            raise ValueError(f"No unresolved {args.kind} candidate for request {args.request}")
        coordination_log.append_locked(path, args.session, "control.dismiss", request=args.request, kind=args.kind,
                                        reason=args.reason, sentence=candidate.get("sentence", ""))
    return {"request": args.request, "kind": args.kind, "dismissed": True}


def _quote_unreliable(quote):
    return coordination_log.is_notification(quote) or len(re.findall(r"[.!?]", quote)) > 1


def _session_owns_project(session, root, events):
    """This project's log captured a request from `session`, or a ledger binding points under this project root."""
    requests = request_inbox._fold(events)
    if any(entry["session"] == session for entry in requests.values()):
        return True
    import task_tracking
    try:
        record, _binding = task_tracking._load_binding(session)
    except (OSError, ValueError):
        return False
    try:
        return Path(record["root"]).resolve().is_relative_to(_project_top(root))
    except (KeyError, OSError, ValueError):
        return False


def cmd_migrate(args, root):
    import deploy_hold
    directory = deploy_hold.hold_dir()
    migrated, skipped_other_project = [], []
    if not directory.is_dir():
        return {"migrated": migrated, "skipped_other_project": skipped_other_project}
    with coordination_log.locked(root) as path:
        events = coordination_log.read_path(path)["events"]
        already = {(e.get("provenance") or {}).get("session") for e in events if e.get("type") == "control.set"
                   and (e.get("provenance") or {}).get("source") == "legacy_migration"}
        for file in sorted(directory.glob("*.json")):
            session = file.stem
            if session in already:
                continue
            try:
                data = json.loads(file.read_text())
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict) or data.get("control_id"):
                continue
            quote = data.get("quote")
            if not isinstance(quote, str) or not quote:
                continue
            if not _session_owns_project(session, root, events):
                skipped_other_project.append(session)
                continue
            task_id = bound_task_id(session, root)
            scope = {"level": "task", "task": task_id} if task_id else {"level": "project", "scope_ambiguous": True}
            cid = _next_control_id(events)
            provenance = {"source": "legacy_migration", "session": session, "quote_unreliable": _quote_unreliable(quote)}
            event = coordination_log.append_locked(path, args.session, "control.set", id=cid, kind="deploy_hold",
                                                    scope=scope, quote=quote, request=None, provenance=provenance)
            events.append(event)
            migrated.append(cid)
    return {"migrated": migrated, "skipped_other_project": skipped_other_project}


def _legacy_still_enforcing(controls):
    """Lifted migrated controls whose legacy file (never touched by migrate or lift) still enforces its session."""
    import deploy_hold
    entries = []
    for control in controls.values():
        if not control["lifted"] or control["provenance"].get("source") != "legacy_migration":
            continue
        session = control["provenance"].get("session")
        held = deploy_hold.read_hold(session) if session else None
        if held and not held.get("control_id"):
            entries.append({"session": session, "path": str(deploy_hold.hold_path(session))})
    return entries


def cmd_list(args, root):
    controls, candidates = _fold(coordination_log.read(root)["events"])
    if args.dismissed:
        items = [{"request": req, "kind": kind, "sentence": info.get("sentence", ""), "reason": info.get("reason", "")}
                 for (req, kind), info in candidates.items() if info.get("dismissed")]
        return {"dismissed": items}
    if args.candidates:
        items = [{"request": req, "kind": kind, "sentence": info.get("sentence", "")}
                 for (req, kind), info in candidates.items() if not info.get("resolved")]
        return {"candidates": items}
    active = sorted((c for c in controls.values() if not c["lifted"]), key=lambda c: c["set_seq"])
    result = {"controls": active}
    legacy = _legacy_still_enforcing(controls)
    if legacy:
        result["legacy_still_enforcing"] = legacy
    return result


def session_start_line(cwd, session_id):
    controls = active_controls(cwd, session_id)
    if not controls:
        return None
    ordered = sorted(controls, key=lambda c: c["set_seq"])
    parts = [f'{c["id"]} {c["kind"]} {c["scope"]["level"]} "{c["quote"][:80]}"' for c in ordered]
    return "Active controls: " + "; ".join(parts)


def add_arguments(command, sub):
    if command != "control":
        return
    actions = sub.add_subparsers(dest="control_action", required=True)
    listing = actions.add_parser("list")
    listing.add_argument("--dismissed", action="store_true")
    listing.add_argument("--candidates", action="store_true")
    setter = actions.add_parser("set")
    setter.add_argument("--kind", required=True, choices=KINDS)
    setter.add_argument("--scope", required=True, choices=SCOPE_LEVELS)
    setter.add_argument("--rows")
    setter.add_argument("--quote", required=True)
    setter.add_argument("--request")
    setter.add_argument("--evidence")
    setter.add_argument("--scope-ambiguous", dest="scope_ambiguous", action="store_true")
    lifter = actions.add_parser("lift")
    lifter.add_argument("--id", required=True)
    lifter.add_argument("--request", required=True)
    lifter.add_argument("--quote", required=True)
    narrower = actions.add_parser("narrow")
    narrower.add_argument("--id", required=True)
    narrower.add_argument("--scope", required=True, choices=SCOPE_LEVELS)
    narrower.add_argument("--rows")
    narrower.add_argument("--request", required=True)
    narrower.add_argument("--quote", required=True)
    dismisser = actions.add_parser("dismiss")
    dismisser.add_argument("--request", required=True)
    dismisser.add_argument("--kind", required=True, choices=KINDS)
    dismisser.add_argument("--reason", required=True)
    actions.add_parser("migrate")


def dispatch(args, root):
    handlers = {"list": cmd_list, "set": cmd_set, "lift": cmd_lift, "narrow": cmd_narrow,
                "dismiss": cmd_dismiss, "migrate": cmd_migrate}
    return handlers[args.control_action](args, root)
