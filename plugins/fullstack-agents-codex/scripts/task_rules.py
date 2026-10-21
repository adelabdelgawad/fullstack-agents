"""Pure lifecycle rules shared by task-ledger consumers."""
from collections import Counter
from datetime import datetime, timezone

LEGACY_STATUSES = ("pending", "in_progress", "blocked", "done", "skipped", "canceled")
V2_STATUSES = ("pending", "in_progress", "verifying", "blocked", "done", "skipped", "canceled")
OPEN = frozenset(("pending", "in_progress", "verifying", "blocked"))
TERMINAL = frozenset(("done", "skipped", "canceled"))
HOLDS_TURN = frozenset(("pending", "in_progress", "verifying"))


def validate_parents(items):
    by_id = {item["id"]: item for item in items}
    parents = {item["parent"] for item in items if item.get("parent")}
    for item in items:
        parent_id = item.get("parent", "")
        if not parent_id:
            continue
        if parent_id == item["id"]:
            raise ValueError(f"Task {item['id']} cannot parent itself")
        parent = by_id.get(parent_id)
        if parent is None:
            raise ValueError(f"Unknown parent task ID: {parent_id}")
        if parent.get("parent"):
            raise ValueError(f"Child task {parent_id} cannot be a parent")
        if item["id"] in parents:
            raise ValueError(f"Parent task {item['id']} cannot be given a parent")


def validate_open_steps(items):
    by_id = {item["id"]: item for item in items}
    invalid = [(item["id"], item["parent"]) for item in items
               if item.get("parent") and item["status"] in OPEN and by_id[item["parent"]]["status"] in TERMINAL]
    if invalid:
        rows = ", ".join(f"step {step} / parent {parent}" for step, parent in invalid)
        raise ValueError(
            f"Open steps cannot have terminal parents: {rows}; reopen the parent "
            f"(set --status in_progress --reason …) or close the steps first"
        )


def counts(items, version):
    statuses = V2_STATUSES if version == "v2" else LEGACY_STATUSES
    status_counts = dict.fromkeys(statuses, 0)
    status_counts.update(Counter(item["status"] for item in items))
    if version == "legacy":
        return status_counts, {"total": len(items), "completed": status_counts["done"]}
    deliverables = [item for item in items if not item.get("parent")]
    included = [item for item in deliverables if item["status"] not in ("skipped", "canceled")]
    steps = [item for item in items if item.get("parent")]
    return status_counts, {
        "total": len(included), "completed": sum(item["status"] == "done" for item in included),
        "deliverables": _group(included, statuses), "steps": _group(steps, statuses),
    }


def _group(items, statuses):
    values = dict.fromkeys(statuses, 0)
    values.update(Counter(item["status"] for item in items))
    return {"total": len(items), "completed": values["done"], "counts": values}


def _epoch(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.timestamp() if parsed.tzinfo else None
    except (ValueError, OverflowError, TypeError):
        return None


def _live_lease(item, now):
    if item["status"] not in ("in_progress", "verifying") or not item.get("owner") or item["owner"] == "lead":
        return False
    if "is_active" in item:
        return bool(item["is_active"])
    deadline = _epoch(item.get("active_until"))
    return deadline is not None and deadline > now


def _external_entry(identifier, entry):
    info = {"id": identifier, "text": entry["text"], "rows": entry["rows"],
            "class": "dependency" if entry["kind"] == "row" else entry.get("class", "other")}
    if entry.get("class") == "capacity":
        info["engine"], info["until"] = entry.get("engine", ""), entry.get("until", "")
        if entry.get("offer"):
            info["offer"] = entry["offer"]
    return info


def session_state(items, blockers, now):
    """§13.3 as reduced by §13.10: one derived state plus the lists that explain it."""
    open_items = [item for item in items if item["status"] in OPEN]
    if not open_items:
        return {"state": "done", "executable": [], "questions": [], "workers": [], "external": []}
    open_blockers = {bid: entry for bid, entry in blockers.items() if entry["status"] == "open"}
    questions = [{"id": bid, "text": e["text"], "why": e["why"], "rows": e["rows"]}
                 for bid, e in sorted(open_blockers.items()) if e["kind"] == "user"]
    workers = [{"id": bid, "text": e["text"], "rows": e["rows"]}
               for bid, e in sorted(open_blockers.items()) if e["kind"] == "worker"]
    external = [_external_entry(bid, e) for bid, e in sorted(open_blockers.items()) if e["kind"] in ("external", "row")]
    live_workers = [{"row": item["id"], "owner": item["owner"], "activity": item["activity"]}
                    for item in open_items if _live_lease(item, now)]
    executable = [item["id"] for item in open_items if item["status"] != "blocked" and not _live_lease(item, now)]
    if executable:
        state = "executable"
    elif live_workers or workers:
        state = "waiting_worker"
    elif questions:
        state = "waiting_user"
    else:
        state = "waiting_external"
    return {"state": state, "executable": executable, "questions": questions,
            "workers": workers + live_workers, "external": external}


def log_line(identifier, event, **values):
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    fields = " ".join(f'{key}="{_quote(str(value))}"' for key, value in values.items())
    return f"- {stamp} {identifier or '-'} {event}" + (f" {fields}" if fields else "") + "\n"


def _quote(value):
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
