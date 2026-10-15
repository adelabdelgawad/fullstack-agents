#!/usr/bin/env python3
"""Record explicit Codex workflow progress for the optional shared dashboard."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time

PHASES = ("investigate", "plan", "implement", "validate", "audit", "complete")


def valid_event(event):
    return (isinstance(event, dict) and event.get("phase") in PHASES
            and type(event.get("timestamp")) in (int, float)
            and math.isfinite(event["timestamp"]) and event["timestamp"] > 0)


def safe_id(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", value) is not None


def configured_model(root):
    """Use an explicitly configured model; an unknown inherited model stays null."""
    try:
        import tomllib
        home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        config = tomllib.loads((home / "config.toml").read_text())
        profile = config.get("profile")
        model = config.get("profiles", {}).get(profile, {}).get("model", config.get("model"))
        return model if isinstance(model, str) else None
    except (ImportError, OSError, ValueError, TypeError, AttributeError):
        return None


def child_thread(events):
    try:
        with Path(events).open() as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                    if event.get("type") == "thread.started" and safe_id(event.get("thread_id")):
                        return event["thread_id"]
                except (ValueError, AttributeError):
                    continue
    except OSError:
        pass
    return None


def publish_run(record, **updates):
    """Best-effort telemetry, never evidence that the underlying task succeeded."""
    if record is None:
        return
    record.update(updates, updated=time.time())
    temporary = None
    try:
        home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        directory = home / "fsa-flow" / "runs" / record["session_id"]
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(record, stream, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, directory / (record["run_id"] + ".json"))
    except (OSError, ValueError, TypeError) as error:
        import sys
        print(f"run telemetry unavailable: {error}", file=sys.stderr)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def start_run(session, run, root, role, engine, model, brief=None, events_path=None):
    if not safe_id(session) or not safe_id(run.name):
        return None
    record = {"session_id": session, "run_id": run.name, "role": role, "engine": engine,
              "model": model, "root": str(root), "state": "running", "started": time.time(),
              "artifact": str(run), "brief": brief, "summary": "", "verdict": None,
              "events_path": str(events_path) if events_path else None, "child_session_id": None}
    publish_run(record)
    return record


def main():
    import sys
    if not Path(__file__).with_name("task_tracking.py").is_file():
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "plugins/fullstack-agents/scripts/lib"))
    from task_tracking import bind_tasks, load_tasks

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--tasks", help="Repository Markdown task file to bind to this session")
    parser.add_argument("--phase", required=True, choices=PHASES)
    parser.add_argument("--session", default=os.environ.get("CODEX_THREAD_ID"))
    parser.add_argument("--state-dir", type=Path, default=Path(
        os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "fsa-flow")
    parser.add_argument("--check", action="append", help="Lead-reported verification text, not proof")
    parser.add_argument("--summary", help="Lead-reported result summary")
    parser.add_argument("--auditor-model", default=os.environ.get("FSA_CLAUDE_AUDIT_MODEL") or "opus")
    args = parser.parse_args()
    if not args.session:
        parser.error("--session or CODEX_THREAD_ID is required")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", args.session):
        parser.error("session ID must be a safe filename (letters, digits, _, ., -)")
    cwd = str(args.root.expanduser().resolve())
    if args.tasks:
        try:
            bind_tasks(args.session, cwd, args.tasks)
        except (OSError, ValueError, TypeError, KeyError) as error:
            parser.error(f"task registration failed: {error}")
    tracked = load_tasks(args.session, cwd)
    if args.phase == "complete" and tracked:
        if tracked.get("error"):
            parser.error(f"cannot complete with an invalid task list: {tracked['error']}")
        unfinished = [item["id"] for item in tracked["items"] if item["status"] in {"pending", "in_progress", "running", "blocked"}]
        if unfinished:
            parser.error("cannot complete while tasks remain unfinished: " + ", ".join(unfinished))
    path = args.state_dir.expanduser() / f"{args.session}.json"
    history = []
    checks, summary = [], ""
    try:
        prior = json.loads(path.read_text(encoding="utf-8"))
        if (isinstance(prior, dict) and prior.get("session_id") == args.session
                and prior.get("cwd") == cwd and prior.get("engine") == "codex"
                and isinstance(prior.get("history"), list)
                and all(valid_event(event) for event in prior["history"])
                and prior["history"]
                and prior["history"][-1] == {"phase": prior.get("phase"), "timestamp": prior.get("updated")}
                and all(a["timestamp"] <= b["timestamp"] for a, b in zip(prior["history"], prior["history"][1:]))):
            history = prior["history"][-99:]
            if isinstance(prior.get("checks"), list) and all(isinstance(c, str) for c in prior["checks"]):
                checks = prior["checks"]
            if isinstance(prior.get("summary"), str):
                summary = prior["summary"]
    except (OSError, ValueError):
        pass
    now = time.time()
    if history and history[-1]["timestamp"] > now:
        history = []
        checks, summary = [], ""
    if args.phase == "investigate":
        checks, summary = [], ""
    if args.check is not None:
        checks = args.check
    if args.summary is not None:
        summary = args.summary
    history.append({"phase": args.phase, "timestamp": now})
    record = {"session_id": args.session, "engine": "codex", "lead": "codex",
              "auditor": args.auditor_model, "checks": checks, "summary": summary,
              "cwd": cwd, "phase": args.phase,
              "updated": now, "history": history,
              "task_tracking": {k: tracked[k] for k in ("file", "counts", "total", "completed", "error") if k in tracked}}
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{args.session}.", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(record, stream, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    except OSError as exc:
        parser.exit(1, f"phase journal write failed: {exc}\n")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
