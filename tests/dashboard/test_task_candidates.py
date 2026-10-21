"""Resumable-ledger candidates: scoped to the checkout, filtered to eligible owners, newest ledger first."""
import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "plugins/fullstack-agents/scripts/lib"
sys.path.insert(0, str(LIB))
SPEC = importlib.util.spec_from_file_location("task_tracking", LIB / "task_tracking.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)
import task_candidates as candidates
import task_ownership as ownership

GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}


class CandidatesTestCase(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-candidates-")
        self.addCleanup(self.scratch.cleanup)
        self.base = Path(self.scratch.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, env=GIT_ENV, check=True)
        self.state = self.base / "state"
        self.env = patch.dict(os.environ, {"FSA_TASKS_DIR": str(self.state), "CLAUDE_PID": str(os.getpid())})
        self.env.start()
        self.addCleanup(self.env.stop)

    def ledger(self, name, items, version="legacy"):
        path = self.root / name
        path.write_text("# " + name + "\n\n" + tasks.START + tasks._render(items, version) + tasks.END + "\n")
        return path

    def bind_and_release(self, session_id, root, path):
        tasks.bind_tasks(session_id, root, path)
        ownership.release(session_id, root, path)

    def bind_live(self, session_id, root, path):
        tasks.bind_tasks(session_id, root, path)


class EligibilityTests(CandidatesTestCase):
    def test_mixed_ledgers_keep_only_the_eligible_two_newest_first(self):
        older = self.ledger("older.md", [tasks._item("T1", "pending", "Older", "")])
        self.bind_and_release("sess-older", self.root, older)
        os.utime(older, (older.stat().st_atime, older.stat().st_mtime - 100))

        newer = self.ledger("newer.md", [tasks._item("T1", "pending", "Newer", "")])
        self.bind_and_release("sess-newer", self.root, newer)

        completed = self.ledger("completed.md", [tasks._item("T1", "done", "Done", "")])
        self.bind_and_release("sess-completed", self.root, completed)

        canceled = self.ledger("canceled.md", [tasks._item("T1", "canceled", "Canceled", "")])
        self.bind_and_release("sess-canceled", self.root, canceled)

        malformed = self.ledger("malformed.md", [tasks._item("T1", "pending", "Bad", "")])
        self.bind_and_release("sess-malformed", self.root, malformed)
        malformed.write_text("not a ledger at all")

        live = self.ledger("live.md", [tasks._item("T1", "pending", "Live", "")])
        self.bind_live("sess-live", self.root, live)

        other_root = self.base / "other-repo"
        other_root.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=other_root, env=GIT_ENV, check=True)
        elsewhere = other_root / "elsewhere.md"
        elsewhere.write_text("# elsewhere\n\n" + tasks.START
                             + tasks._render([tasks._item("T1", "pending", "Elsewhere", "")]) + tasks.END + "\n")
        self.bind_and_release("sess-elsewhere", other_root, elsewhere)

        results = candidates.candidates(str(self.root))
        self.assertEqual([c["file"] for c in results], ["newer.md", "older.md"])
        self.assertEqual(results[0]["owner"], "sess-newer")
        self.assertIn("fsa-task bind --root", results[0]["command"])
        self.assertNotIn("--takeover", results[0]["command"])

    def test_stale_owner_candidate_offers_takeover_command(self):
        path = self.ledger("stale.md", [tasks._item("T1", "pending", "Stale", "")])
        tasks.bind_tasks("sess-stale", self.root, path)
        key_path = candidates.task_tracking._state_dir() / "owners"
        record_path = next(key_path.glob("*.json"))
        import json
        record = json.loads(record_path.read_text())
        record["claude_pid"] = 2**22 + 7
        record_path.write_text(json.dumps(record))
        results = candidates.candidates(str(self.root))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["owner_state"], "stale")
        self.assertIn("--takeover sess-stale", results[0]["command"])

    def test_root_and_file_with_a_space_are_shell_quoted(self):
        root = self.base / "repo with space"
        root.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, env=GIT_ENV, check=True)
        path = root / "with space.md"
        path.write_text("# ledger\n\n" + tasks.START
                         + tasks._render([tasks._item("T1", "pending", "A", "")]) + tasks.END + "\n")
        self.bind_and_release("sess-space", root, path)
        results = candidates.candidates(str(root))
        self.assertEqual(len(results), 1)
        parts = shlex.split(results[0]["command"])
        self.assertIn(str(root), parts)
        self.assertIn("with space.md", parts)

    def test_no_owner_records_is_empty(self):
        self.assertEqual(candidates.candidates(str(self.root)), [])

    def test_non_git_cwd_is_empty(self):
        outside = self.base / "not-a-repo"
        outside.mkdir()
        self.assertEqual(candidates.candidates(str(outside)), [])


class CliTests(CandidatesTestCase):
    def test_main_prints_a_line_per_candidate(self):
        path = self.ledger("a.md", [tasks._item("T1", "pending", "A", "")])
        self.bind_and_release("sess-a", self.root, path)
        result = subprocess.run([sys.executable, "-I", str(LIB / "task_candidates.py"), "--cwd", str(self.root)],
                                env={**os.environ, "FSA_TASKS_DIR": str(self.state)},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("a.md", result.stdout)
        self.assertIn("fsa-task bind --root", result.stdout)

    def test_main_json_mode(self):
        result = subprocess.run([sys.executable, "-I", str(LIB / "task_candidates.py"), "--cwd", str(self.root),
                                 "--json"], env={**os.environ, "FSA_TASKS_DIR": str(self.state)},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "[]")


if __name__ == "__main__":
    unittest.main()
