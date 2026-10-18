"""Temp repository, temp HOME and fake engine CLIs for codex-task.sh tests; no fake ever calls a model."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "plugins/fullstack-agents/scripts"

# Each fake records argv, selected env and stdin to $FSA_TEST_CALL, then behaves as $FSA_FAKE_MODE says.
FAKE = r'''import json, os, sys, time
engine = os.path.basename(sys.argv[0])
mode = os.environ.get("FSA_FAKE_MODE", "ok")
stdin = "" if sys.stdin.isatty() else sys.stdin.read()
keys = ("FSA_RUN_ID", "FSA_ROLE", "FSA_IMPLEMENTER_RUN", "FSA_IMPLEMENTER_ROOT", "FSA_ALLOWED_PATHS_FILE", "OPENCODE_CONFIG")
calls = os.environ["FSA_TEST_CALL"]
with open(calls, "a") as fh:
    fh.write(json.dumps({"engine": engine, "args": sys.argv[1:], "env": {k: os.environ.get(k) for k in keys},
                         "stdin": stdin, "cwd": os.getcwd()}) + "\n")
if engine == "opencode" and sys.argv[1:3] == ["session", "list"]:
    runs = [json.loads(line)["args"] for line in open(calls) if '"opencode"' in line and '"--title"' in line]
    title = runs[-1][runs[-1].index("--title") + 1] if runs else ""
    print(json.dumps([{"id": "ses_other", "title": "unrelated", "directory": os.getcwd()},
                      {"id": "ses_fake1", "title": title, "directory": os.getcwd()}]))
    sys.exit(0)
if mode == "touch":
    for p in os.environ.get("FSA_FAKE_TOUCH", "").split(":"):
        if p:
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
            open(p, "a").write("x\n")
if mode == "sleep":
    time.sleep(float(os.environ.get("FSA_FAKE_SLEEP", "30")))
if mode == "fail":
    print("engine failed", file=sys.stderr)
    sys.exit(3)
result = {"summary": "done", "files": [], "tests": [], "open_risks": []}
if mode == "malformed":
    result = None
if engine == "codex":
    print("session id: 01a14614-0000-7000-8000-000000000001")
    print("reasoning effort: none")
    if result is not None:
        out = sys.argv[sys.argv.index("-o") + 1]
        open(out, "w").write(json.dumps(result))
elif engine == "claude":
    if result is not None:
        print(json.dumps({"type": "result", "is_error": False, "structured_output": result}))
else:
    print("working")
    if result is not None:
        print("```json\n" + json.dumps(result) + "\n```")
'''


def write(path, text, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if mode:
        path.chmod(mode)


class DispatchCase:
    """A temp git repository with a brief, fake engines on PATH and an isolated HOME."""

    def __init__(self, engine="codex"):
        self.tmp = tempfile.TemporaryDirectory(prefix="fsa-dispatch-")
        self.base = Path(self.tmp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        git = ["git", "-C", str(self.root), "-c", "user.email=t@example.invalid", "-c", "user.name=T"]
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        write(self.root / "app.py", "value = 1\n")
        subprocess.run([*git, "add", "app.py"], check=True)
        subprocess.run([*git, "commit", "-qm", "base"], check=True)
        self.brief = self.base / "brief.md"
        self.brief.write_text(f"IMPLEMENTER: {engine}\nPLAN: none: test\nALLOWED_PATHS:\napp.py\n\nGOAL: x\n")
        self.home = self.base / "home"
        write(self.home / ".bashrc", "alias cc='claude --dangerously-skip-permissions'\n")
        write(self.home / ".local/share/opencode/auth.json", json.dumps({"xai": {"type": "api"}}))
        for name in ("claude", "codex", "opencode"):
            write(self.base / "bin" / name, "#!" + sys.executable + "\n" + FAKE, 0o755)
        self.calls = self.base / "calls.jsonl"
        env = {k: v for k, v in os.environ.items() if not k.startswith(("FSA_", "CLAUDE_CODE_SESSION", "KC_"))}
        self.env = {**env, "HOME": str(self.home), "PATH": f"{self.base / 'bin'}{os.pathsep}{env['PATH']}",
                    "FSA_TEST_CALL": str(self.calls), "FSA_CODEX_ROOT": str(self.root),
                    "XDG_DATA_HOME": str(self.home / ".local/share")}

    def binding(self, **values):
        write(self.root / ".claude/fsa-team.conf", "".join(f"{k}={v}\n" for k, v in values.items()))

    def dispatch(self, *extra, env=None, mode="implement", timeout=120):
        return subprocess.run(["bash", str(SCRIPTS / "codex-task.sh"), *extra, mode, str(self.brief)],
                              env={**self.env, **(env or {})}, capture_output=True, text=True, timeout=timeout,
                              cwd=self.root, stdin=subprocess.DEVNULL)

    def call_log(self):
        if not self.calls.exists():
            return []
        return [json.loads(line) for line in self.calls.read_text().splitlines() if line.strip()]

    def manifest(self, result):
        return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line and not line.startswith(" "))

    def cleanup(self):
        self.tmp.cleanup()
