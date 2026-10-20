"""One owner record per ledger: computed liveness, acquire/release/write-guard, never trusting a bare PID."""
import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
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
import task_ownership as ownership
CLI = REPO / "plugins/fullstack-agents/scripts/fsa-task"

STALE_PID = 2**22 + 7


class TaskOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-owners-")
        self.base = Path(self.scratch.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.state = self.base / "state"
        self.env = patch.dict(os.environ, {"FSA_TASKS_DIR": str(self.state), "CLAUDE_PID": str(os.getpid())})
        self.env.start()
        self.path = self.root / "TASKS.md"
        self.path.write_text("# T\n\n" + tasks.START + tasks._render([tasks._item("T1", "pending", "Task", "")]) + tasks.END + "\n")

    def tearDown(self):
        self.env.stop()
        self.scratch.cleanup()

    def record_path(self):
        return ownership._record_path(self.root, self.path)

    def write_record(self, **overrides):
        record = {"session_id": "other", "claude_pid": os.getpid(), "pid_start": ownership._pid_start(os.getpid()),
                  "host": ownership.socket.gethostname(), "checkout": str(self.root), "file": str(self.path),
                  "acquired_at": ownership._now(), "released_at": None}
        record.update(overrides)
        path = self.record_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record))
        return record

    def test_acquire_on_empty_record(self):
        record = ownership.acquire("session-1", self.root, self.path)
        self.assertEqual(record["session_id"], "session-1")
        self.assertIsNone(record["released_at"])
        self.assertEqual(json.loads(self.record_path().read_text())["session_id"], "session-1")

    def test_same_session_reacquires(self):
        ownership.acquire("session-1", self.root, self.path)
        record = ownership.acquire("session-1", self.root, self.path)
        self.assertEqual(record["session_id"], "session-1")

    def test_live_other_owner_refuses(self):
        self.write_record()
        with self.assertRaises(ValueError) as ctx:
            ownership.acquire("session-1", self.root, self.path)
        self.assertIn("other", str(ctx.exception))
        self.assertIn("live", str(ctx.exception))

    def test_dead_pid_is_stale_refused_without_takeover_and_accepted_with_it(self):
        self.write_record(claude_pid=STALE_PID, pid_start=1)
        with self.assertRaises(ValueError) as ctx:
            ownership.acquire("session-1", self.root, self.path)
        self.assertIn("takeover", str(ctx.exception))
        record = ownership.acquire("session-1", self.root, self.path, takeover="other")
        self.assertEqual(record["session_id"], "session-1")
        self.assertEqual(record["previous"]["session_id"], "other")

    def test_live_pid_with_wrong_start_time_is_stale(self):
        self.write_record(pid_start=1)
        with self.assertRaises(ValueError):
            ownership.acquire("session-1", self.root, self.path)
        record = ownership.acquire("session-1", self.root, self.path, takeover="other")
        self.assertEqual(record["previous"]["pid_start"], 1)

    def test_different_host_is_unknown_refused_without_takeover_accepted_with_it(self):
        self.write_record(host="other-host")
        with self.assertRaises(ValueError) as ctx:
            ownership.acquire("session-1", self.root, self.path)
        self.assertIn("unknown", str(ctx.exception))
        record = ownership.acquire("session-1", self.root, self.path, takeover="other")
        self.assertEqual(record["session_id"], "session-1")
        self.assertEqual(record["previous"]["host"], "other-host")

    def test_live_other_owner_accepted_with_takeover_keeps_previous(self):
        self.write_record()
        record = ownership.acquire("session-1", self.root, self.path, takeover="other")
        self.assertEqual(record["session_id"], "session-1")
        self.assertEqual(record["previous"]["session_id"], "other")

    def test_cas_takeover_wrong_expected_refused_right_accepted(self):
        self.write_record()
        with self.assertRaises(ValueError) as ctx:
            ownership.acquire("session-1", self.root, self.path, takeover="wrong-session")
        self.assertIn("other", str(ctx.exception))
        record = ownership.acquire("session-1", self.root, self.path, takeover="other")
        self.assertEqual(record["session_id"], "session-1")
        self.assertEqual(record["previous"]["session_id"], "other")

    def test_released_record_is_free(self):
        self.write_record(released_at=ownership._now())
        record = ownership.acquire("session-1", self.root, self.path)
        self.assertEqual(record["session_id"], "session-1")
        self.assertNotIn("previous", record)

    def test_identity_ignores_a_non_ancestor_claude_pid(self):
        with patch.dict(os.environ, {"CLAUDE_PID": str(STALE_PID)}):
            pid, _start, _host, _checkout = ownership._identity(self.root)
        self.assertEqual(pid, os.getppid())

    def test_identity_uses_claude_pid_when_it_is_a_deeper_ancestor(self):
        grandparent = ownership.ancestors()[1]
        with patch.dict(os.environ, {"CLAUDE_PID": str(grandparent)}):
            pid, _start, _host, _checkout = ownership._identity(self.root)
        self.assertEqual(pid, grandparent)

    def test_malformed_owner_record_is_explicit_error_never_free(self):
        path = self.record_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not JSON")
        with self.assertRaises(ValueError):
            ownership.acquire("session-1", self.root, self.path)
        with self.assertRaises(ValueError):
            ownership.check_write("session-1", self.root, self.path)

    def test_release_only_clears_owning_sessions_record(self):
        ownership.acquire("session-1", self.root, self.path)
        ownership.release("session-2", self.root, self.path)
        self.assertIsNone(json.loads(self.record_path().read_text())["released_at"])
        ownership.release("session-1", self.root, self.path)
        self.assertIsNotNone(json.loads(self.record_path().read_text())["released_at"])

    def test_release_from_resumed_process_with_different_identity_is_a_noop(self):
        ownership.acquire("session-1", self.root, self.path)
        record = json.loads(self.record_path().read_text())
        record["pid_start"] = record["pid_start"] + 1
        self.record_path().write_text(json.dumps(record))
        self.assertFalse(ownership.release("session-1", self.root, self.path))
        self.assertIsNone(json.loads(self.record_path().read_text())["released_at"])

    def test_release_is_idempotent_after_success(self):
        ownership.acquire("session-1", self.root, self.path)
        self.assertTrue(ownership.release("session-1", self.root, self.path))
        self.assertFalse(ownership.release("session-1", self.root, self.path))

    def test_fork_like_caller_same_pid_other_session_cannot_release_or_write(self):
        ownership.acquire("session-1", self.root, self.path)
        self.assertFalse(ownership.release("session-2", self.root, self.path))
        with self.assertRaises(ValueError) as ctx:
            ownership.check_write("session-2", self.root, self.path)
        self.assertIn("session-1", str(ctx.exception))
        self.assertIsNone(json.loads(self.record_path().read_text())["released_at"])

    def test_release_session_releases_only_matching_live_identity_records_and_skips_malformed(self):
        ownership.acquire("session-1", self.root, self.path)
        other_path = self.root / "OTHER.md"
        other_path.write_text(self.path.read_text())
        ownership.acquire("session-1", self.root, other_path)
        malformed = ownership._record_path(self.root, self.root / "BROKEN.md")
        malformed.parent.mkdir(parents=True, exist_ok=True)
        malformed.write_text("not JSON")
        released = ownership.release_session("session-1")
        self.assertEqual(sorted(released), sorted(str(p) for p in (self.path, other_path)))
        self.assertIsNotNone(json.loads(self.record_path().read_text())["released_at"])

    def test_write_guard_refuses_non_owner_allows_owner_and_legacy_unowned(self):
        ownership.check_write("whoever", self.root, self.path)
        ownership.acquire("session-1", self.root, self.path)
        ownership.check_write("session-1", self.root, self.path)
        ownership.release("session-1", self.root, self.path)
        ownership.check_write("session-1", self.root, self.path)
        with self.assertRaises(ValueError) as ctx:
            ownership.check_write("session-2", self.root, self.path)
        self.assertIn("session-1", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            ownership.check_write(None, self.root, self.path)
        self.assertIn("--session", str(ctx.exception))

    def invoke(self, *args):
        return subprocess.run([sys.executable, str(CLI), *args], text=True, capture_output=True)

    def test_cli_bind_takeover_and_write_guard_end_to_end(self):
        bound = self.invoke("bind", "--root", str(self.root), "--file", "TASKS.md", "--session", "owner-session")
        self.assertEqual(bound.returncode, 0, bound.stderr)
        allowed = self.invoke("set", "--root", str(self.root), "--file", "TASKS.md", "--session", "owner-session", "--id", "T1", "--status", "blocked")
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        refused = self.invoke("set", "--root", str(self.root), "--file", "TASKS.md", "--session", "intruder", "--id", "T1", "--status", "done")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("owner-session", refused.stderr)
        self.write_record(session_id="crashed", claude_pid=STALE_PID, pid_start=1)
        stale_refused = self.invoke("bind", "--root", str(self.root), "--file", "TASKS.md", "--session", "new-session")
        self.assertNotEqual(stale_refused.returncode, 0)
        wrong_expected = self.invoke("bind", "--root", str(self.root), "--file", "TASKS.md", "--session", "new-session", "--takeover", "someone-else")
        self.assertNotEqual(wrong_expected.returncode, 0)
        taken_over = self.invoke("bind", "--root", str(self.root), "--file", "TASKS.md", "--session", "new-session", "--takeover", "crashed")
        self.assertEqual(taken_over.returncode, 0, taken_over.stderr)
        released = self.invoke("release", "--root", str(self.root), "--file", "TASKS.md", "--session", "new-session")
        self.assertEqual(released.returncode, 0, released.stderr)
        self.assertTrue(json.loads(self.record_path().read_text())["released_at"])

    def test_cli_release_by_non_owner_reports_released_false(self):
        bound = self.invoke("bind", "--root", str(self.root), "--file", "TASKS.md", "--session", "owner-session")
        self.assertEqual(bound.returncode, 0, bound.stderr)
        released = self.invoke("release", "--root", str(self.root), "--file", "TASKS.md", "--session", "intruder")
        self.assertEqual(released.returncode, 0, released.stderr)
        self.assertFalse(json.loads(released.stdout)["released"])
        self.assertIsNone(json.loads(self.record_path().read_text())["released_at"])

    def test_reacquire_with_no_record_is_unowned_and_creates_nothing(self):
        self.assertEqual(ownership.reacquire("session-1", self.root, self.path), "unowned")
        self.assertFalse(self.record_path().exists())

    def test_reacquire_another_sessions_free_record_is_other_owner_and_untouched(self):
        self.write_record(session_id="other", released_at=ownership._now())
        before = self.record_path().read_text()
        self.assertEqual(ownership.reacquire("session-1", self.root, self.path), "other-owner")
        self.assertEqual(self.record_path().read_text(), before)

    def test_reacquire_another_sessions_live_record_is_other_owner_and_untouched(self):
        self.write_record(session_id="other")
        before = self.record_path().read_text()
        self.assertEqual(ownership.reacquire("session-1", self.root, self.path), "other-owner")
        self.assertEqual(self.record_path().read_text(), before)

    def test_reacquire_another_sessions_stale_record_is_other_owner_and_untouched(self):
        self.write_record(session_id="other", claude_pid=STALE_PID, pid_start=1)
        before = self.record_path().read_bytes()
        self.assertEqual(ownership.reacquire("session-1", self.root, self.path), "other-owner")
        self.assertEqual(self.record_path().read_bytes(), before)

    def test_reacquire_own_free_record_acquires(self):
        self.write_record(session_id="session-1", released_at=ownership._now())
        self.assertEqual(ownership.reacquire("session-1", self.root, self.path), "acquired")
        self.assertIsNone(json.loads(self.record_path().read_text())["released_at"])

    def test_reacquire_own_stale_record_acquires(self):
        self.write_record(session_id="session-1", claude_pid=STALE_PID, pid_start=1)
        self.assertEqual(ownership.reacquire("session-1", self.root, self.path), "acquired")
        current = json.loads(self.record_path().read_text())
        self.assertEqual(current["claude_pid"], ownership._identity(self.root)[0])

    def test_reacquire_own_record_live_with_this_exact_identity_acquires(self):
        ownership.acquire("session-1", self.root, self.path)
        self.assertEqual(ownership.reacquire("session-1", self.root, self.path), "acquired")

    def test_reacquire_own_record_live_elsewhere_is_untouched(self):
        child = subprocess.Popen(["sleep", "30"])
        try:
            self.write_record(session_id="session-1", claude_pid=child.pid, pid_start=ownership._pid_start(child.pid))
            before = self.record_path().read_text()
            self.assertEqual(ownership.reacquire("session-1", self.root, self.path), "live-elsewhere")
            self.assertEqual(self.record_path().read_text(), before)
        finally:
            child.kill()
            child.wait()

    def test_two_concurrent_binds_on_one_file_exactly_one_wins(self):
        children = [subprocess.Popen([sys.executable, str(CLI), "bind", "--root", str(self.root), "--file", "TASKS.md", "--session", f"racer-{index}"],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for index in range(2)]
        outcomes = [child.communicate(timeout=10) for child in children]
        codes = [child.returncode for child in children]
        self.assertEqual(sorted(codes), [0, 2], outcomes)
        winner = f"racer-{codes.index(0)}"
        self.assertEqual(json.loads(self.record_path().read_text())["session_id"], winner)


if __name__ == "__main__":
    unittest.main()
