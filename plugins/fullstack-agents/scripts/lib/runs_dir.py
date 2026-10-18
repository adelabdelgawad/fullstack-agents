"""Python twin of runs-dir.sh: the run registry is FSA_CODEX_RUNS_DIR, then the project binding, then the default."""
import os
from pathlib import Path


def binding(root, key):
    """Last `key=value` line of <root>/.claude/fsa-team.conf, or None."""
    try:
        lines = (Path(root) / ".claude" / "fsa-team.conf").read_text().splitlines()
    except OSError:
        return None
    values = [line.split("=", 1)[1] for line in lines if line.startswith(f"{key}=")]
    return values[-1] if values else None


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
