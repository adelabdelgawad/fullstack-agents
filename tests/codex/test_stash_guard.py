"""Regression checks for the shared-checkout git-stash guard."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "plugins/fullstack-agents/scripts"
FENCE = SCRIPTS / "lib/allowed-paths-fence"


def run(command, **kwargs):
    return subprocess.run(command, capture_output=True, text=True, **kwargs)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class StashGuardTests(unittest.TestCase):
    def setUp(self):
        self.case = tempfile.TemporaryDirectory(prefix="fsa-stash-")
        base = Path(self.case.name)
        self.root = base / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        write(self.root / "app.py", "value = 1\n")
        git = ["git", "-C", str(self.root), "-c", "user.email=t@example.invalid", "-c", "user.name=T"]
        subprocess.run([*git, "add", "app.py"], check=True)
        subprocess.run([*git, "commit", "-qm", "base"], check=True)
        self.allow = base / "allow"
        self.allow.write_text("app.py\n")
        inherited = {key: value for key, value in os.environ.items()
                     if not key.startswith(("FSA_", "CLAUDE_CODE_SESSION"))}
        self.env = {**inherited, "FSA_IMPLEMENTER_ROOT": str(self.root),
                    "FSA_ALLOWED_PATHS_FILE": str(self.allow)}

    def tearDown(self):
        self.case.cleanup()

    def fence(self, tool_name, tool_input):
        payload = {"tool_name": tool_name, "tool_input": tool_input}
        return run([sys.executable, "-I", str(FENCE)], input=json.dumps(payload), env=self.env)

    def test_refuses_git_stash_variants(self):
        commands = (
            "git stash", "git stash pop", "git stash list", "git -C /x stash",
            'git -C "/a b" stash push', "git -c user.name=x stash", "cd r && git stash",
            "make x; git stash", 'bash -c "git stash"', "sh -c 'git -C . stash'",
            "GIT_DIR=.git git stash", "command git stash", r"\git stash",
        )
        for command in commands:
            with self.subTest(command=command):
                result = self.fence("Bash", {"command": command})
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("Nothing ran", result.stderr)
                self.assertIn("isolated fixture", result.stderr)

    def test_allows_unrelated_bash_commands(self):
        commands = ("git status", "git log --grep stash", "git diff -- docs/stash.md",
                    "grep -r stash .", "echo stash", "mygit stash")
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(self.fence("Bash", {"command": command}).returncode, 0)

    def test_edit_path_fence_is_unchanged(self):
        self.assertEqual(self.fence("Edit", {"file_path": "app.py"}).returncode, 0)
        blocked = self.fence("Edit", {"file_path": "other.py"})
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("ALLOWED_PATHS", blocked.stderr)


class DispatcherStashTests(unittest.TestCase):
    def setUp(self):
        self.case = tempfile.TemporaryDirectory(prefix="fsa-stash-dispatch-")
        base = Path(self.case.name)
        self.root = base / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        write(self.root / "app.py", "value = 1\n")
        git = ["git", "-C", str(self.root), "-c", "user.email=t@example.invalid", "-c", "user.name=T"]
        subprocess.run([*git, "add", "app.py"], check=True)
        subprocess.run([*git, "commit", "-qm", "base"], check=True)
        self.brief = base / "brief.md"
        self.brief.write_text("IMPLEMENTER: claude\nPLAN: none: test\nALLOWED_PATHS:\napp.py\n\nGOAL: x\n")
        self.call = base / "call.json"
        self.home = base / "home"
        write(self.home / ".bashrc", "alias cc='claude --dangerously-skip-permissions'\n")
        fake_claude = r'''import json, os, sys
open(os.environ["FSA_TEST_CALL"], "w").write(json.dumps({"args": sys.argv[1:]}))
if os.environ.get("FSA_TEST_STASH_OUTPUT"):
    print("Saved working directory and index state WIP on main: abc base")
print(json.dumps({"type": "result", "is_error": False, "structured_output": {"summary": "done"}}))
'''
        write(base / "bin/claude", "#!" + sys.executable + "\n" + fake_claude)
        (base / "bin/claude").chmod(0o755)
        inherited = {key: value for key, value in os.environ.items()
                     if not key.startswith(("FSA_", "CLAUDE_CODE_SESSION"))}
        self.env = {**inherited, "HOME": str(self.home),
                    "PATH": f"{base / 'bin'}{os.pathsep}{os.environ['PATH']}",
                    "FSA_TEST_CALL": str(self.call), "FSA_CODEX_ROOT": str(self.root),
                    "FSA_CODEX_RUNS_DIR": str(base / "runs")}

    def tearDown(self):
        self.case.cleanup()

    def dispatch(self, env=None):
        return run(["bash", str(SCRIPTS / "codex-task.sh"), "implement", str(self.brief)],
                   env=env or self.env)

    def test_claude_fence_matcher_includes_bash(self):
        result = self.dispatch()
        self.assertEqual(result.returncode, 0, result.stderr)
        call = json.loads(self.call.read_text())
        settings = json.loads(call["args"][call["args"].index("--settings") + 1])
        self.assertEqual(settings["hooks"]["PreToolUse"][0]["matcher"],
                         "Edit|Write|MultiEdit|NotebookEdit|Bash")

    def test_opencode_denies_stash_with_and_without_tests(self):
        base = Path(self.case.name)
        fake = base / "bin/opencode"
        fake_code = r'''import json, os
config = json.load(open(os.environ["OPENCODE_CONFIG"]))
open(os.environ["FSA_TEST_CALL"], "w").write(json.dumps(config))
print('```json')
print(json.dumps({"summary": "done", "files": [], "tests": [], "open_risks": []}))
print('```')
'''
        write(fake, "#!" + sys.executable + "\n" + fake_code)
        fake.chmod(0o755)
        self.brief.write_text(self.brief.read_text().replace("IMPLEMENTER: claude", "IMPLEMENTER: grok"))
        for allow_tests in ("0", "1"):
            with self.subTest(allow_tests=allow_tests):
                env = {**self.env, "FSA_OPENCODE_BIN": str(fake), "XAI_API_KEY": "test",
                       "FSA_IMPLEMENTER_ALLOW_TESTS": allow_tests}
                result = self.dispatch(env)
                self.assertEqual(result.returncode, 0, result.stderr)
                bash = json.loads(self.call.read_text())["permission"]["bash"]
                self.assertEqual(bash["*"], "allow")
                for pattern in ("*git stash*", "*git -C * stash*", "*git -c * stash*"):
                    self.assertEqual(bash[pattern], "deny")

    def test_stash_output_marks_manifest_and_result(self):
        result = self.dispatch({**self.env, "FSA_TEST_STASH_OUTPUT": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STATUS=SHARED_CHECKOUT_VIOLATION", result.stdout)
        record = json.loads(next((Path(self.case.name) / "runs").glob("*.result.json")).read_text())
        self.assertIn("stash_used", record["details"])


if __name__ == "__main__":
    unittest.main()
