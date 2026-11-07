"""Shared helpers for the workflow-comparison runner: files, hashes, git, bounded commands and process sweeps."""
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLUGIN_LIB = REPO / "plugins/fullstack-agents/scripts/lib"
sys.path.insert(0, str(PLUGIN_LIB))
import liveness
import usage

__all__ = ["liveness", "usage"]

MARKER = "FSA_EXP_SESSION"
FINAL_STATES = ("succeeded", "failed", "timed_out", "interrupted", "budget_exhausted", "needs_human")


def experiments_dir():
    return Path(os.environ.get("FSA_EXPERIMENTS_DIR") or Path.home() / ".local/share/fullstack-agents/experiments")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    tmp.replace(path)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def manifest(root):
    """Relative path -> sha256 for every regular file, skipping bytecode caches."""
    root = Path(root)
    return {str(p.relative_to(root)): sha256_file(p) for p in sorted(root.rglob("*"))
            if p.is_file() and not p.is_symlink() and "__pycache__" not in p.parts}


def manifest_sha(files):
    return sha256_text(json.dumps(files, sort_keys=True))


def git(args, cwd, check=True):
    proc = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=False)
    if check and proc.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def run_bounded(command, cwd, env, timeout, log):
    """Run a shell command in its own process group; returns (status, exit_code, seconds)."""
    started = time.monotonic()
    with open(log, "w") as out:
        try:
            proc = subprocess.Popen(["bash", "-c", command], cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=True)
        except OSError as error:
            out.write(f"unavailable: {error}\n")
            return "unavailable", None, 0.0
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_group(proc.pid)
            proc.wait()
            return "timeout", None, round(time.monotonic() - started, 2)
    return ("pass" if code == 0 else "fail"), code, round(time.monotonic() - started, 2)


def kill_group(pgid, sig=signal.SIGKILL):
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def marked_pids(value):
    """Pids whose environment carries MARKER=value, including detached (setsid) descendants."""
    needle = f"{MARKER}={value}".encode()
    return [pid for pid, _pp, _c, _cwd, env in liveness._processes()
            if env and needle in env.split(b"\0") and pid != os.getpid()]


def sweep(value, wait_s=5):
    """TERM then KILL every process carrying the session marker; returns the pids signalled."""
    pids = marked_pids(value)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline and marked_pids(value):
        time.sleep(0.2)
    for pid in marked_pids(value):
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    return pids
