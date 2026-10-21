"""Resumable-ledger candidates in a checkout: `python3 -I task_candidates.py --cwd <dir>` is the CLI.

See docs/TASK_LIFECYCLE_DESIGN.md §14.3 item 5, §14.6 item 5.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import task_checkpoint
import task_ownership
import task_rules
import task_tracking

MAX_CANDIDATES = 3


def _git(args, cwd):
    try:
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10)
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _checkout_identity(cwd):
    """(toplevel, common-dir), both realpaths, or None when `cwd` is not a readable git checkout."""
    toplevel = _git(["rev-parse", "--show-toplevel"], cwd)
    if toplevel is None:
        return None
    common = _git(["rev-parse", "--git-common-dir"], cwd)
    if common is None:
        return None
    common_abs = common if os.path.isabs(common) else os.path.join(toplevel, common)
    return os.path.realpath(toplevel), os.path.realpath(common_abs)


def _ledger_state(summary, open_rows):
    if summary.get("format") == "v2":
        return summary.get("session_state", {}).get("state", "?")
    counts = summary["counts"]
    return f"{open_rows} open ({counts.get('in_progress', 0)} in progress)"


def _candidate(record, owner_state, root, path):
    try:
        text = task_tracking._read(path)
        items, _start, _end = task_tracking._parse(text)
    except (OSError, ValueError):
        return None
    open_rows = sum(1 for item in items if item["status"] in task_rules.OPEN)
    if not open_rows:
        return None
    checkpoint, error = task_checkpoint.load_checkpoint(text)
    if error is not None or (checkpoint is not None and checkpoint.get("status") != "active"):
        return None
    try:
        summary = task_tracking._summary(path)
    except (OSError, ValueError):
        return None
    try:
        relpath = path.relative_to(root)
    except ValueError:
        relpath = path
    command = f"fsa-task bind --root {shlex.quote(str(root))} --file {shlex.quote(str(relpath))}"
    if owner_state == "stale":
        command += f" --takeover {shlex.quote(record['session_id'])}"
    return {"file": str(relpath), "title": summary["title"], "state": _ledger_state(summary, open_rows),
            "owner": record["session_id"], "owner_state": owner_state, "command": command,
            "mtime": path.stat().st_mtime}


def candidates(cwd):
    """Resumable ledgers in `cwd`'s checkout: open rows, a valid ledger, checkpoint absent or active, owner
    free or stale (never live or unknown); most recently modified ledger first."""
    identity = _checkout_identity(cwd)
    if identity is None:
        return []
    directory = task_tracking._state_dir() / "owners"
    if not directory.is_dir():
        return []
    results = []
    for record_path in sorted(directory.glob("*.json")):
        try:
            record = json.loads(task_tracking._read(record_path, 16384))
        except (OSError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        try:
            owner_state = task_ownership.owner_state(record)
        except ValueError:
            continue
        if owner_state not in ("free", "stale"):
            continue
        if _checkout_identity(record.get("checkout", "")) != identity:
            continue
        candidate = _candidate(record, owner_state, Path(record["checkout"]), Path(record["file"]))
        if candidate is not None:
            results.append(candidate)
    results.sort(key=lambda c: c["mtime"], reverse=True)
    for candidate in results:
        del candidate["mtime"]
    return results


def candidate_line(candidate):
    return (f"{candidate['file']} — {candidate['title']} ({candidate['state']}; owner "
            f"{candidate['owner'][:8]} {candidate['owner_state']}) — {candidate['command']}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="task_candidates")
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    results = candidates(args.cwd)
    if args.json:
        print(json.dumps(results))
        return 0
    if not results:
        print("No resumable ledgers in this checkout.")
        return 0
    print("Resumable ledgers in this checkout (most recently changed first):")
    for candidate in results:
        print(candidate_line(candidate))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
