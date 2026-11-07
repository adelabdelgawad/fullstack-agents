#!/usr/bin/env python3
"""`claude` on a sandbox PATH: runs the real CLI unchanged and appends one start and one end record per process."""
import json
import os
import signal
import subprocess
import sys
import time

KEEP = ("type", "subtype", "is_error", "session_id", "total_cost_usd", "modelUsage", "usage", "num_turns",
        "terminal_reason", "subagent_stats", "permission_denials", "duration_ms", "duration_api_ms")


def record(entry):
    with open(os.environ["FSA_EXP_LEDGER"], "a") as fh:
        fh.write(json.dumps(entry) + "\n")


def result_of(line):
    try:
        data = json.loads(line)
    except ValueError:
        return None
    if isinstance(data, dict) and (data.get("type") == "result" or "total_cost_usd" in data):
        return {k: data[k] for k in KEEP if k in data}
    return None


def role():
    if os.environ.get("FSA_CLASSIFIER_RUN"):
        return "classifier"
    return os.environ.get("FSA_ROLE") or os.environ.get("FSA_EXP_ROLE", "unknown")


def main():
    argv = [os.environ["FSA_EXP_REAL_CLAUDE"], *sys.argv[1:]]
    started = time.time()
    record({"event": "start", "pid": os.getpid(), "ppid": os.getppid(), "cwd": os.getcwd(), "at": started, "role": role(),
            "argv": [a if len(a) <= 300 else a[:300] + "…" for a in sys.argv[1:]]})
    child = subprocess.Popen(argv, stdout=subprocess.PIPE)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, lambda s, _f: child.send_signal(s))
    result = None
    for line in child.stdout:
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()
        result = result_of(line) or result
    code = child.wait()
    record({"event": "end", "pid": os.getpid(), "exit": code, "at": time.time(), "seconds": round(time.time() - started, 2),
            "result": result})
    return code if code >= 0 else 128 - code


if __name__ == "__main__":
    sys.exit(main())
