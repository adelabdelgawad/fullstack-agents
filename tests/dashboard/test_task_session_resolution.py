"""task_tracking.default_session resolves the right engine's session id across a real OS process tree.

Existing tests in test_task_tracking.py inject the ancestor chain directly; these spawn genuine
process trees (a `codex`-named process, nested bash wrappers) so the walk in default_session/
task_ownership.ancestors is proven against /proc, not a mock.
"""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "plugins/fullstack-agents/scripts/lib"
sys.path.insert(0, str(LIB))
SPEC = importlib.util.spec_from_file_location("task_tracking", LIB / "task_tracking.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)
CLI = REPO / "plugins/fullstack-agents/scripts/fsa-task"
QUOTED_CLI = shlex.quote(str(CLI))


class SessionResolutionProcessTreeTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-session-tree-")
        self.addCleanup(self.scratch.cleanup)
        self.base = Path(self.scratch.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=self.root, check=True)
        ledger = "# Tasks\n\n" + tasks.START + tasks._render([tasks._item("T1", "pending", "Implement API", "")]) + tasks.END + "\n"
        (self.root / "TASKS.md").write_text(ledger)
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=self.root, check=True)
        self.state = self.base / "state"
        self.base_env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/root"),
                          "FSA_TASKS_DIR": str(self.state)}
        # Plain invocation (no `exec`) so this script forks a child and survives as a genuine,
        # "codex"-looking ancestor by the time the child's default_session() walks /proc.
        self.codex = self._script(self.base / "bin", "codex", f'#!/usr/bin/env bash\npython3 -I {QUOTED_CLI} "$@"\n')

    def _script(self, directory, name, body):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_text(body)
        os.chmod(path, 0o755)
        return path

    def _run(self, argv, extra_env):
        return subprocess.run(argv, cwd=self.root, env={**self.base_env, **extra_env},
                               text=True, capture_output=True, timeout=30)

    def _binding(self, session_id):
        path = self.state / f"{session_id}.json"
        return json.loads(path.read_text()) if path.exists() else None

    def test_codex_wins_when_invoked_through_the_codex_script(self):
        sleeper = subprocess.Popen(["sleep", "30"], env=self.base_env)
        try:
            result = self._run([str(self.codex), "bind", "--root", str(self.root), "--file", "TASKS.md"],
                                {"CODEX_THREAD_ID": "codex-lead", "CLAUDE_CODE_SESSION_ID": "stale-claude",
                                 "CLAUDE_PID": str(sleeper.pid)})
        finally:
            sleeper.kill()
            sleeper.wait()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._binding("codex-lead")["session_id"], "codex-lead")
        self.assertIsNone(self._binding("stale-claude"))

    def test_claude_wins_through_an_intermediate_bash_dash_c_wrapper(self):
        # `exit $?` after the python3 call stops bash's `-c` single-last-command optimization
        # from replacing this shell in place, so it stays alive as the CLAUDE_PID ancestor.
        wrapper = f'export CLAUDE_PID=$$\npython3 -I {QUOTED_CLI} "$@"\nexit $?\n'
        result = subprocess.run(["bash", "-c", wrapper, "wrapper", "bind", "--root", str(self.root),
                                  "--file", "TASKS.md"], cwd=self.root,
                                 env={**self.base_env, "CODEX_THREAD_ID": "stale-codex",
                                      "CLAUDE_CODE_SESSION_ID": "claude-id"},
                                 text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._binding("claude-id")["session_id"], "claude-id")
        self.assertIsNone(self._binding("stale-codex"))

    def test_nearest_wins_codex_inner_under_a_claude_outer_wrapper(self):
        wrapper = self._script(self.base / "c1", "claude-outer.sh",
                                f'#!/usr/bin/env bash\nexport CLAUDE_PID=$$\n{shlex.quote(str(self.codex))} "$@"\n')
        result = self._run([str(wrapper), "bind", "--root", str(self.root), "--file", "TASKS.md"],
                            {"CODEX_THREAD_ID": "codex-lead-c1", "CLAUDE_CODE_SESSION_ID": "claude-outer-stale"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._binding("codex-lead-c1")["session_id"], "codex-lead-c1")
        self.assertIsNone(self._binding("claude-outer-stale"))

    def test_nearest_wins_claude_inner_under_a_codex_outer_script(self):
        claude_inner = self._script(self.base / "c2", "claude-inner.sh",
                                     f'#!/usr/bin/env bash\nexport CLAUDE_PID=$$\npython3 -I {QUOTED_CLI} "$@"\n')
        codex_outer = self._script(self.base / "c2", "codex",
                                    f'#!/usr/bin/env bash\n{shlex.quote(str(claude_inner))} "$@"\n')
        result = self._run([str(codex_outer), "bind", "--root", str(self.root), "--file", "TASKS.md"],
                            {"CODEX_THREAD_ID": "codex-outer-stale", "CLAUDE_CODE_SESSION_ID": "claude-inner-id"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self._binding("claude-inner-id")["session_id"], "claude-inner-id")
        self.assertIsNone(self._binding("codex-outer-stale"))

    def test_ambiguous_without_a_claude_pid_ancestor_or_codex_refuses(self):
        result = self._run([sys.executable, str(CLI), "bind", "--root", str(self.root), "--file", "TASKS.md"],
                            {"CODEX_THREAD_ID": "stale-codex-d", "CLAUDE_CODE_SESSION_ID": "stale-claude-d",
                             "CLAUDE_PID": str(2 ** 22 + 7)})
        self.assertEqual(result.returncode, 2)
        self.assertIn("pass --session", result.stderr)
        self.assertIsNone(self._binding("stale-codex-d"))
        self.assertIsNone(self._binding("stale-claude-d"))

    def test_single_variable_each_way_registers_that_id(self):
        cases = (
            ({"CODEX_THREAD_ID": "codex-solo"}, "codex-solo"),
            ({"CLAUDE_CODE_SESSION_ID": "cc-solo"}, "cc-solo"),
            ({"CLAUDE_SESSION_ID": "legacy-solo"}, "legacy-solo"),
        )
        previous = None
        for overrides, session_id in cases:
            with self.subTest(session_id=session_id):
                argv = [sys.executable, str(CLI), "bind", "--root", str(self.root), "--file", "TASKS.md"]
                if previous is not None:
                    argv += ["--takeover", previous]
                result = self._run(argv, overrides)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self._binding(session_id)["session_id"], session_id)
                previous = session_id


if __name__ == "__main__":
    unittest.main()
