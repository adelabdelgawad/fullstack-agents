"""Business goals: a registry in the coordination log that requests and sessions link to; `fsa-task goal`."""
import re

import coordination_log
import request_inbox

STATUSES = ("active", "done", "dropped")


def _next_id(goals):
    numbers = [int(match.group(1)) for gid in goals for match in [re.fullmatch(r"G(\d+)", gid)] if match]
    return f"G{max(numbers, default=0) + 1}"


def fold(events):
    """Goals by id: title, owner, status and the sessions and requests linked to each."""
    goals = {}
    for event in events:
        etype, gid = event.get("type"), event.get("id")
        if etype == "goal.created" and isinstance(gid, str):
            goals[gid] = {"id": gid, "title": event.get("title", ""), "owner": event.get("owner", ""),
                          "status": "active", "at": event.get("at"), "sessions": [], "requests": []}
            continue
        goal = goals.get(gid)
        if goal is None:
            continue
        if etype == "goal.updated":
            goal.update({key: event[key] for key in ("title", "owner", "status") if event.get(key)})
        elif etype == "goal.linked":
            for key in ("sessions", "requests"):
                goal[key] = sorted(set(goal[key]) | set(event.get(key) or []))
    return goals


def linked_sessions(goal, requests):
    """A goal's sessions: those linked directly plus the session of every linked request."""
    via_requests = {requests[rid]["session"] for rid in goal["requests"] if rid in requests}
    return set(goal["sessions"]) | {session for session in via_requests if session}


def for_cards(cwd, cards):
    """Dashboard rows: each goal with the cards of its sessions and done/total progress; tags each card with its goals."""
    events = coordination_log.read(cwd)["events"]
    goals, requests = fold(events), request_inbox._fold(events)
    rows = []
    for goal in goals.values():
        sessions = linked_sessions(goal, requests)
        mine = [card for card in cards if any(s.get("id") in sessions for s in card.get("sessions") or [])]
        for card in mine:
            card.setdefault("goals", []).append(goal["id"])
        done = sum(1 for card in mine if card.get("phase") == "complete")
        rows.append({key: goal[key] for key in ("id", "title", "owner", "status", "requests")}
                    | {"cards": [card["key"] for card in mine], "done": done, "total": len(mine)})
    return rows


# ---------------------------------------------------------------- CLI


def _require(goals, gid):
    if gid not in goals:
        raise ValueError(f"Unknown goal id: {gid}")


def _split(raw):
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def cmd_add(args, root):
    title = (args.title or "").strip()
    if not title:
        raise ValueError("--title must not be empty")
    with coordination_log.locked(root) as path:
        gid = _next_id(fold(coordination_log.read_path(path)["events"]))
        coordination_log.append_locked(path, args.session, "goal.created", id=gid, title=title,
                                       owner=(args.owner or "").strip())
    return {"id": gid, "title": title}


def cmd_list(args, root):
    return {"goals": list(fold(coordination_log.read(root)["events"]).values())}


def cmd_set(args, root):
    goals = fold(coordination_log.read(root)["events"])
    _require(goals, args.id)
    if args.status and args.status not in STATUSES:
        raise ValueError(f"--status must be one of {', '.join(STATUSES)}")
    fields = {key: value for key, value in (("title", args.title), ("owner", args.owner), ("status", args.status)) if value}
    if not fields:
        raise ValueError("set needs --title, --owner or --status")
    coordination_log.append(root, args.session, "goal.updated", id=args.id, **fields)
    return {"id": args.id, **fields}


def cmd_link(args, root):
    events = coordination_log.read(root)["events"]
    goals, requests = fold(events), request_inbox._fold(events)
    _require(goals, args.id)
    linked = _split(args.requests)
    for rid in linked:
        if rid not in requests:
            raise ValueError(f"Unknown request id: {rid}")
    sessions = _split(args.sessions) or ([] if linked or not args.session else [args.session])
    if not sessions and not linked:
        raise ValueError("link needs --requests or --sessions (or a current session)")
    coordination_log.append(root, args.session, "goal.linked", id=args.id, sessions=sessions, requests=linked)
    return {"id": args.id, "sessions": sessions, "requests": linked}


def add_arguments(command, sub):
    if command != "goal":
        return
    actions = sub.add_subparsers(dest="goal_action", required=True)
    add = actions.add_parser("add")
    add.add_argument("--title", required=True)
    add.add_argument("--owner")
    actions.add_parser("list")
    update = actions.add_parser("set")
    update.add_argument("--id", required=True)
    update.add_argument("--title")
    update.add_argument("--owner")
    update.add_argument("--status")
    link = actions.add_parser("link")
    link.add_argument("--id", required=True)
    link.add_argument("--requests", help="Comma-separated request ids (R12,R13)")
    link.add_argument("--sessions", help="Comma-separated session ids; default: the current session")


def dispatch(args, root):
    handlers = {"add": cmd_add, "list": cmd_list, "set": cmd_set, "link": cmd_link}
    return handlers[args.goal_action](args, root)
