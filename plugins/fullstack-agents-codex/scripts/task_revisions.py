"""Links a dispatched worker run to its ledger row and instruction revision: a stale or cancelled dispatch is
refused before any run file is written, a stale finish is recorded but never applied, and a stale worker-blocker
acceptance is refused. See docs/TASK_LIFECYCLE_DESIGN.md §15 (Unit C)."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coordination_log

KINDS = ("correction", "cancel")


def _project_top(cwd):
    return Path(coordination_log._project_root(cwd)).resolve()


def task_key(cwd, task_file):
    """<ledger path relative to the project top-level>, realpathed; raises ValueError when it lies outside."""
    path = Path(task_file).expanduser()
    if not path.is_absolute():
        path = Path(cwd).expanduser() / path
    return str(path.resolve().relative_to(_project_top(cwd)))


def row_key(task, row):
    return f"{task}#{row}"


def _fold(events):
    rows = {}
    for event in events:
        if event.get("type") == "revision.bump":
            rows[row_key(event.get("task"), event.get("row"))] = {"revision": event.get("revision"),
                                                                    "kind": event.get("kind")}
    return rows


def current(cwd, task_id, row):
    """{'revision': int, 'kind': str|None} for one row; a row never bumped is revision 0, kind None."""
    entry = _fold(coordination_log.read(cwd)["events"]).get(row_key(task_id, row))
    return dict(entry) if entry else {"revision": 0, "kind": None}


# ---------------------------------------------------------------- dispatch-side fence and finish-side check


def check_dispatch(cwd, task_id, row, brief_revision):
    """One-line STATUS reason to refuse the dispatch with, or None to let it proceed."""
    state = current(cwd, task_id, row)
    if state["kind"] == "cancel":
        return "STATUS=ROW_CANCELLED"
    if state["revision"] > 0:
        brief_revision = (brief_revision or "").strip()
        if brief_revision != str(state["revision"]):
            shown = brief_revision or "none"
            return f"STATUS=STALE_REVISION (brief revision {shown}, row revision {state['revision']})"
    return None


def is_stale_finish(cwd, task_id, row, recorded_revision):
    """True once the row has moved past the revision this run was dispatched against."""
    return current(cwd, task_id, row)["revision"] > int(recorded_revision or 0)


def refuse_worker_evidence(cwd, result_path, rows):
    """One-line refusal reason for a result.json that cannot back a worker blocker's resolution, else None."""
    try:
        data = json.loads(result_path.read_text())
    except (OSError, ValueError):
        return None
    if data.get("state") == "stale_revision":
        return "worker evidence refused: the run ended stale_revision (must reconcile)"
    if not result_path.name.endswith(".result.json"):
        return None
    meta_path = result_path.with_name(result_path.name[: -len(".result.json")] + ".meta.json")
    meta = _read_json(meta_path)
    if meta is None:
        return None
    task_id, recorded = meta.get("task_file"), meta.get("instruction_revision")
    if task_id is None or recorded is None:
        return None
    for row in rows:
        if is_stale_finish(cwd, task_id, row, recorded):
            return f"worker evidence refused: row {row} revision moved past this run (must reconcile)"
    return None


def _read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- runs bound to a row


def runs_for_row(root, task_id, row):
    import liveness
    import runs_dir as runs_dir_mod
    found = []
    for directory in runs_dir_mod.read_dirs(root, runs_dir_mod.runs_dir(root)):
        for meta_path in sorted(directory.glob("*.meta.json")):
            meta = _read_json(meta_path)
            if meta is None or meta.get("task_file") != task_id or meta.get("task_row") != row:
                continue
            run_id = meta_path.name[: -len(".meta.json")]
            state = liveness.run_state(directory, run_id)["state"]
            found.append({"run": run_id, "state": state, "stop": f"codex-task.sh stop {run_id}"})
    return found


# ---------------------------------------------------------------- CLI (fsa-task revise)


def _parse_rows(raw):
    rows = [row.strip() for row in raw.split(",") if row.strip()]
    if not rows:
        raise ValueError("--rows must name at least one row id")
    return rows


def cmd_revise(args, root):
    if args.reconciled:
        coordination_log.append(root, args.session, "revision.reconciled", run=args.reconciled, note=args.note or "")
        return {"run": args.reconciled, "reconciled": True}
    if args.kind not in KINDS:
        raise ValueError(f"--kind must be one of {KINDS}")
    if not args.rows:
        raise ValueError("--rows is required unless --reconciled")
    import task_controls
    task_id = task_controls.bound_task_id(args.session, root)
    if task_id is None:
        raise ValueError("revise requires a bound task ledger for this session")
    rows = _parse_rows(args.rows)
    results = []
    with coordination_log.locked(root) as path:
        events = coordination_log.read_path(path)["events"]
        for row in rows:
            prior = _fold(events).get(row_key(task_id, row))
            revision = (prior["revision"] if prior else 0) + 1
            event = coordination_log.append_locked(path, args.session, "revision.bump", task=task_id, row=row,
                                                    revision=revision, request=args.request, kind=args.kind,
                                                    note=args.note or "")
            events.append(event)
            results.append({"row": row, "revision": revision})
    for result in results:
        result["runs"] = runs_for_row(root, task_id, result["row"])
    return {"revisions": results}


def add_arguments(command, sub):
    if command != "revise":
        return
    sub.add_argument("--rows")
    sub.add_argument("--request")
    sub.add_argument("--kind", choices=KINDS)
    sub.add_argument("--note")
    sub.add_argument("--reconciled", help="Run id to mark reconciled instead of bumping a revision")


def dispatch(args, root):
    return cmd_revise(args, root)


# ---------------------------------------------------------------- CLI (dispatch-side, invoked from task-row.sh)


def main(argv):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    id_cmd = sub.add_parser("task-id")
    id_cmd.add_argument("--root", required=True)
    id_cmd.add_argument("--task", required=True)
    for name in ("check", "current"):
        p = sub.add_parser(name)
        p.add_argument("--root", required=True)
        p.add_argument("--task-id", required=True)
        p.add_argument("--row", required=True)
        if name == "check":
            p.add_argument("--revision", default="")
    args = parser.parse_args(argv)
    if args.command == "task-id":
        try:
            print(task_key(args.root, args.task))
        except ValueError:
            pass
        return 0
    if args.command == "current":
        print(json.dumps(current(args.root, args.task_id, args.row)))
        return 0
    try:
        reason = check_dispatch(args.root, args.task_id, args.row, args.revision)
    except OSError as error:
        print(f"STATUS=STALE_REVISION (coordination log unreadable: {error})")
        return 2
    if reason is None:
        return 0
    print(reason)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
