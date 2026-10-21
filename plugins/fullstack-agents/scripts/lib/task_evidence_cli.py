"""CLI wiring (argument definitions and dispatch) for completion evidence commands.

Moved out of task_evidence.py so that module stays under the line budget; behaviour is unchanged.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import task_evidence

# --root/--file/--session are required on the "check" parser itself; repeating them here, optional and
# SUPPRESS-defaulted, lets `fsa-task check <action> --root ...` work the same as `check --root ... <action>`
# since argparse hands everything after the action token to this sub-parser.
SHARED_FLAGS = ("--root", "--file", "--session")


def _accept_shared_flags(sub):
    for flag in SHARED_FLAGS:
        sub.add_argument(flag, default=argparse.SUPPRESS)


def _relax_required(sub, *dests):
    """Let the given already-added options on `sub` go unset here; the check-action sub-parser may supply
    them instead (both before and after the action name are valid positions)."""
    for action in sub._actions:
        if action.dest in dests:
            action.required = False


def add_arguments(command, sub):
    if command == "accept":
        sub.add_argument("--id", required=True)
        group = sub.add_mutually_exclusive_group(required=True)
        group.add_argument("--input", help="Spec JSON file path, or - for stdin")
        group.add_argument("--from-brief", help="Brief file path to parse into a spec")
        sub.add_argument("--reason")
    elif command == "baseline":
        sub.add_argument("--id", required=True)
        # dest renamed: the top-level dispatch already uses args.command for the subcommand name itself.
        sub.add_argument("--command", dest="baseline_command", required=True)
        sub.add_argument("--ref", required=True)
        sub.add_argument("--log", required=True)
        sub.add_argument("--signature", action="append", default=[], required=True)
        sub.add_argument("--reason", required=True)
    elif command == "verify":
        sub.add_argument("--id", required=True)
        sub.add_argument("--json", action="store_true")
    elif command == "check":
        _relax_required(sub, "root", "file")
        checks = sub.add_subparsers(dest="check_action", required=True)
        start = checks.add_parser("start")
        start.add_argument("--id", required=True)
        start.add_argument("--check", required=True)
        finish = checks.add_parser("finish")
        finish.add_argument("--id", required=True)
        finish.add_argument("--check", required=True)
        finish.add_argument("--run", required=True)
        finish.add_argument("--result", required=True, choices=task_evidence.EXTERNAL_RESULTS)
        finish.add_argument("--evidence", action="append", default=[])
        finish.add_argument("--reason")
        run = checks.add_parser("run")
        run.add_argument("--id", required=True)
        run.add_argument("--check", required=True)
        run.add_argument("--log")
        run.add_argument("--timeout", type=int, default=task_evidence.DEFAULT_TIMEOUT)
        attribute = checks.add_parser("attribute")
        attribute.add_argument("--id", required=True)
        attribute.add_argument("--check", required=True)
        attribute.add_argument("--baseline", required=True)
        attribute.add_argument("--reason", required=True)
        for action in (start, finish, run, attribute):
            _accept_shared_flags(action)


def dispatch(args, root, path):
    if args.command == "accept":
        return task_evidence.cmd_accept(args, root, path)
    if args.command == "baseline":
        return task_evidence.cmd_baseline(args, root, path)
    if args.command == "check":
        handler = {"start": task_evidence.cmd_check_start, "finish": task_evidence.cmd_check_finish,
                   "run": task_evidence.cmd_check_run, "attribute": task_evidence.cmd_check_attribute}[args.check_action]
        return handler(args, root, path)
    raise ValueError(f"Unknown completion evidence command: {args.command}")
