"""One execution session's sandbox: its own clone, HOME, Claude config, FSA state, PATH shim and allowlisted env."""
import contextlib
import os
import shutil
from pathlib import Path

from common import MARKER, git, sha256_text

HERE = Path(__file__).resolve().parent
PASS_ENV = ("LANG", "LC_ALL", "LC_CTYPE", "TERM", "USER", "LOGNAME", "SHELL", "PATH")
SECRET_ENV = ("CLAUDE_CODE_OAUTH_TOKEN",)
STATE_ENV = {"FSA_STATE_HOME": "state/fsa", "FSA_TASKS_DIR": "state/tasks", "FSA_STOP_GUARD_DIR": "state/stop-guard",
             "FSA_CODEX_RUNS_DIR": "state/runs", "FSA_RELEASES_DIR": "state/releases", "TMPDIR": "tmp",
             "XDG_DATA_HOME": "xdg/data", "XDG_CACHE_HOME": "xdg/cache", "XDG_CONFIG_HOME": "xdg/config",
             "XDG_STATE_HOME": "xdg/state", "CLAUDE_CONFIG_DIR": "config", "HOME": "home"}


class Sandbox:
    def __init__(self, root):
        self.root = Path(root)
        self.repo = self.root / "repo"
        self.ledger = self.root / "processes.jsonl"
        self.marker = sha256_text(str(self.root.resolve()))[:16]

    def create(self, source, commit, label):
        for rel in STATE_ENV.values():
            (self.root / rel).mkdir(parents=True, exist_ok=True)
        bin_dir = self.root / "bin"
        bin_dir.mkdir(exist_ok=True)
        shutil.copy2(HERE / "claude_shim.py", bin_dir / "claude")
        (self.root / "home/.bashrc").write_text("alias cc='claude --dangerously-skip-permissions'\n")
        self.ledger.touch()
        git(["clone", "-q", "--no-local", "--no-checkout", str(source), str(self.repo)], cwd=self.root)
        git(["checkout", "-q", "-B", f"fsa-exp/{label}", commit], cwd=self.repo)
        git(["remote", "remove", "origin"], cwd=self.repo)
        return {"tree": git(["rev-parse", "HEAD^{tree}"], cwd=self.repo).strip(),
                "clean": git(["status", "--porcelain"], cwd=self.repo) == ""}

    def env(self, real_claude, token=None, extra=()):
        env = {k: os.environ[k] for k in (*PASS_ENV, *extra) if k in os.environ}
        env.update({k: str(self.root / rel) for k, rel in STATE_ENV.items()})
        env["PATH"] = f"{self.root / 'bin'}:{env.get('PATH', '/usr/local/bin:/usr/bin:/bin')}"
        env["FSA_TEAM_BOARD"] = str(self.root / "state/board.json")
        env.update(FSA_EXP_LEDGER=str(self.ledger), FSA_EXP_REAL_CLAUDE=str(real_claude), DISABLE_AUTOUPDATER="1",
                   **{MARKER: self.marker})
        if token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = token
        return env

    @staticmethod
    def recorded(env):
        """The env as it may be stored: secret values replaced by a presence flag."""
        return {k: ("[set]" if k in SECRET_ENV else v) for k, v in sorted(env.items())}

    def worktrees(self):
        out = git(["worktree", "list", "--porcelain"], cwd=self.repo)
        return [Path(line[9:]) for line in out.splitlines() if line.startswith("worktree ")]

    def capture(self, commit, dest):
        """Patch of every worktree against `commit`; the deliverable is the single worktree that changed anything."""
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        found = []
        for i, tree in enumerate(self.worktrees()):
            git(["add", "-A"], cwd=tree)
            patch = git(["diff", "--cached", "--binary", commit], cwd=tree)
            names = git(["diff", "--cached", "--name-only", commit], cwd=tree).split()
            commits = git(["log", "--format=%H %s", f"{commit}..HEAD"], cwd=tree).splitlines()
            path = dest / f"worktree-{i}.patch"
            path.write_text(patch)
            found.append({"worktree": str(tree), "patch": str(path), "files": names, "commits": commits})
        changed = [f for f in found if f["files"]]
        deliverable = changed[0]["patch"] if len(changed) == 1 else None
        status = "no_changes" if not changed else ("ok" if deliverable else "ambiguous_deliverable")
        return {"status": status, "deliverable": deliverable, "worktrees": found}


def _others(exp_dir, current, arm):
    """Everything a session may not read, children before parents: other sandboxes, run records, notes, eval output."""
    arms, mine = Path(exp_dir) / "arms", Path(exp_dir) / "arms" / arm
    stages = [p for p in arms.glob("*/stages/*") if p.is_dir() and p.resolve() != Path(current).resolve()]
    records = [p for p in mine.iterdir() if p.name not in ("stages", "workflows")] if mine.is_dir() else []
    notes = [p for p in mine.glob("workflows/*/*") if p.name not in ("tree", "manifest.json")]
    others = [p for p in arms.iterdir() if p.is_dir() and p.name != arm]
    return stages + records + notes + others + [p for p in [Path(exp_dir) / "eval"] if p.is_dir()]


def unlock_all(exp_dir):
    """Undo locks a killed runner left behind (parents first, so children are reachable)."""
    arms = Path(exp_dir) / "arms"
    if not arms.is_dir():
        return
    for p in [*(q for q in [*arms.glob("*"), Path(exp_dir) / "eval"] if q.exists()), *arms.glob("*/*"),
              *arms.glob("*/stages/*"), *arms.glob("*/workflows/*/*")]:
        if p.name == "tree":
            continue
        p.chmod(p.stat().st_mode | (0o700 if p.is_dir() else 0o600))


@contextlib.contextmanager
def others_locked(exp_dir, current, arm):
    """Make other sessions' directories untraversable while one session runs; a mitigation, not access control."""
    locked = []
    try:
        for p in _others(exp_dir, current, arm):
            locked.append((p, p.stat().st_mode))
            p.chmod(0)
        yield [str(p) for p, _ in locked]
    finally:
        for p, mode in reversed(locked):
            p.chmod(mode)
