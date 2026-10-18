#!/usr/bin/env python3
"""Whether a dispatched run can still edit files: running, stopped, uncertain, or legacy (a v1 record)."""
import json
import os
import sqlite3
import sys
from pathlib import Path

PROC = Path("/proc")
# Codex may run tool commands through a shared app-server and code-mode host instead of the exec process.
DELEGATES = ("codex-code-mode-host", "app-server")


def _read(path, mode="r"):
    try:
        with open(path, mode) as fh:
            return fh.read()
    except OSError:
        return None


def _processes():
    """(pid, ppid, cmdline, cwd, environ-or-None) for every visible process of this user."""
    uid, out = os.getuid(), []
    for entry in PROC.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != uid:
                continue
        except OSError:
            continue
        stat = _read(entry / "stat") or ""
        fields = stat.rsplit(")", 1)[-1].split()
        ppid = int(fields[1]) if len(fields) > 1 else 0
        cmd = (_read(entry / "cmdline", "rb") or b"").replace(b"\0", b" ").decode(errors="replace").strip()
        try:
            cwd = os.readlink(entry / "cwd")
        except OSError:
            cwd = ""
        env = _read(entry / "environ", "rb")
        out.append((int(entry.name), ppid, cmd, cwd, env))
    return out


def _descendants(procs, roots):
    children, found, todo = {}, set(), list(roots)
    for pid, ppid, *_ in procs:
        children.setdefault(ppid, []).append(pid)
    while todo:
        for child in children.get(todo.pop(), []):
            if child not in found:
                found.add(child)
                todo.append(child)
    return found


def _under(path, root):
    return bool(path) and (path == root or path.startswith(root.rstrip("/") + "/"))


def editing_processes(run_id, root, pgid=None, engine=""):
    """Processes that may still edit for this run; `unreadable` counts candidates whose environment is hidden."""
    procs, marker = _processes(), f"FSA_RUN_ID={run_id}".encode()
    by_pid = {p[0]: p for p in procs}
    # The asking process and its ancestors (e.g. the dispatcher collecting its own run) are not editors.
    me = os.getpid()
    while me in by_pid:
        me = by_pid.pop(me)[1]
    procs = [p for p in procs if p[0] in by_pid]
    hits, unreadable = set(), 0
    for pid, ppid, cmd, cwd, env in procs:
        if env is None:
            unreadable += _under(cwd, root)
        elif marker in env.split(b"\0"):
            hits.add(pid)
    if pgid:
        for pid in by_pid:
            try:
                if os.getpgid(pid) == pgid:
                    hits.add(pid)
            except OSError:
                continue
    delegated = set()
    if engine == "codex":
        hosts = [p[0] for p in procs if any(d in p[2] for d in DELEGATES) and "codex" in p[2]]
        delegated = {pid for pid in _descendants(procs, hosts) if _under(by_pid[pid][3], root)}
    return sorted(hits), sorted(delegated), unreadable


def codex_completed(session_id, codex_home):
    if not session_id:
        return None
    files = sorted(Path(codex_home, "sessions").glob(f"*/*/*/rollout-*{session_id}*.jsonl"))
    if not files:
        return None
    for line in (_read(files[-1]) or "").splitlines():
        if '"task_complete"' in line:
            return True
    return False


def opencode_completed(session_id, db):
    if not session_id or not Path(db).exists():
        return None
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute("select data from message where session_id=? order by time_created", (session_id,)).fetchall()
    except sqlite3.Error:
        return None
    last = [json.loads(r[0]) for r in rows if json.loads(r[0]).get("role") == "assistant"][-1:]
    return bool(last and last[0].get("time", {}).get("completed") and last[0].get("finish"))


def claude_completed(log):
    text = _read(log)
    if text is None:
        return None
    return any('"type":"result"' in line or '"type": "result"' in line for line in text.splitlines())


def engine_completed(meta, runs, run_id):
    engine, sid = meta.get("engine"), meta.get("engine_session_id")
    if engine == "codex":
        return codex_completed(sid, os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    if engine == "grok":
        data = os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")
        return opencode_completed(sid, Path(data) / "opencode" / "opencode.db")
    if engine == "claude":
        return claude_completed(Path(runs) / f"{run_id}.log")
    return None


def run_state(runs, run_id):
    runs = Path(runs)
    meta_text = _read(runs / f"{run_id}.meta.json")
    meta = json.loads(meta_text) if meta_text else {}
    if meta.get("schema", 1) < 2:
        return {"state": "legacy", "reasons": ["v1 record: callers apply the log-recency rule"]}
    root = meta.get("cwd") or meta.get("root") or ""
    hits, delegated, unreadable = editing_processes(run_id, root, meta.get("runner_pgid"), meta.get("engine", ""))
    if hits:
        return {"state": "running", "processes": hits, "reasons": ["processes carry the run marker or group"]}
    reasons = []
    if delegated:
        reasons.append(f"delegated executor processes under the root: {delegated}")
    if unreadable:
        reasons.append(f"{unreadable} process(es) under the root hide their environment")
    done = engine_completed(meta, runs, run_id)
    if done is None:
        reasons.append("engine completion record unavailable")
    elif not done:
        reasons.append("engine record shows no completion")
    if (runs / f"{run_id}.released").exists() and not delegated and not unreadable:
        return {"state": "stopped", "reasons": ["explicitly released after process checks"]}
    return {"state": "uncertain" if reasons else "stopped", "processes": delegated, "reasons": reasons}


def release(runs, run_id, confirm):
    """Release only when nothing can still edit; `confirm` overrides a missing engine record, never live processes."""
    state = run_state(runs, run_id)
    if state["state"] == "running" or state.get("processes"):
        return 2, f"refused: processes may still edit: {state.get('processes')}"
    if state["state"] == "uncertain" and not confirm:
        return 2, "refused: " + "; ".join(state["reasons"]) + " (re-run with --confirm after checking)"
    if any("hide their environment" in r for r in state.get("reasons", [])):
        return 2, "refused: processes under the root hide their environment"
    Path(runs, f"{run_id}.released").write_text(json.dumps({"reasons": state.get("reasons", [])}) + "\n")
    return 0, f"released ({state['state']})"


def main(argv):
    if len(argv) >= 3 and argv[0] == "state":
        print(json.dumps(run_state(argv[1], argv[2])))
        return 0
    if len(argv) >= 3 and argv[0] == "release":
        code, message = release(argv[1], argv[2], "--confirm" in argv[3:])
        print(message)
        return code
    print("usage: liveness.py state|release <runs-dir> <run-id> [--confirm]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
