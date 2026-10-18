"""Python twin of runs-dir.sh: the run registry is FSA_CODEX_RUNS_DIR, then the project binding, then the default."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import team_conf  # noqa: E402


def binding(root, key):
    """Typed value of <root>/.claude/fsa-team.conf's `key`, or None; ':'-joined for list keys."""
    value = team_conf.get(root, key)
    if isinstance(value, list):
        return ":".join(value) if value else None
    return value


def runs_dir(root, explicit=None, fallback=None):
    """Primary registry directory; `fallback` covers projects whose binding is still only a wrapper script."""
    chosen = explicit or os.environ.get("FSA_CODEX_RUNS_DIR") or binding(root, "runs_dir") or fallback
    return Path(os.path.expanduser(chosen)) if chosen else Path.home() / ".codex" / "fsa-runs"


def read_dirs(root, primary):
    """Primary first, then the binding's existing legacy directories, without duplicates."""
    out = [Path(primary)]
    for raw in (binding(root, "legacy_runs_dirs") or "").split(":"):
        path = Path(os.path.expanduser(raw)) if raw else None
        if path and path not in out and path.is_dir():
            out.append(path)
    return out
