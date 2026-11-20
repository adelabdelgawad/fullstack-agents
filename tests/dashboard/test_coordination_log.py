"""Append-only per-project coordination log; see docs/TASK_LIFECYCLE_DESIGN.md §15."""
import importlib.util
import multiprocessing
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "plugins/fullstack-agents/scripts/lib"
sys.path.insert(0, str(LIB))
SPEC = importlib.util.spec_from_file_location("coordination_log_test", LIB / "coordination_log.py")
coordination_log = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coordination_log)


def git(args, cwd):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _append_batch(tasks_dir, cwd, worker, count):
    os.environ["FSA_TASKS_DIR"] = tasks_dir
    for index in range(count):
        coordination_log.append(cwd, f"worker-{worker}", "request.received", id=f"{worker}-{index}")


class CoordinationLogTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-coordlog-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name) / "repo"
        self.root.mkdir()
        git(["init", "-q"], self.root)
        git(["config", "user.email", "a@example.com"], self.root)
        git(["config", "user.name", "Test"], self.root)
        (self.root / "README.md").write_text("doc\n")
        git(["add", "-A"], self.root)
        git(["commit", "-q", "-m", "initial"], self.root)
        self.state_dir = Path(self.scratch.name) / "state"
        self.env = patch.dict(os.environ, {"FSA_TASKS_DIR": str(self.state_dir)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_append_assigns_increasing_seq(self):
        first = coordination_log.append(str(self.root), "s1", "request.received", id="R1")
        second = coordination_log.append(str(self.root), "s1", "request.received", id="R2")
        self.assertEqual((first["seq"], second["seq"]), (1, 2))
        events = coordination_log.read(str(self.root))["events"]
        self.assertEqual([e["id"] for e in events], ["R1", "R2"])

    def test_read_skips_torn_final_line_and_a_later_append_still_parses(self):
        coordination_log.append(str(self.root), "s1", "request.received", id="R1")
        path = coordination_log._log_path(str(self.root))
        with path.open("ab") as stream:
            stream.write(b'{"seq": 2, "at": "x", "type": "request.received", "id"')  # torn, no trailing newline
        result = coordination_log.read(str(self.root))
        self.assertTrue(result["torn"])
        self.assertEqual([e["id"] for e in result["events"]], ["R1"])
        coordination_log.append(str(self.root), "s1", "request.received", id="R3")
        result = coordination_log.read(str(self.root))
        self.assertTrue(result["torn"])
        self.assertEqual([e["id"] for e in result["events"]], ["R1", "R3"])
        self.assertEqual(result["events"][-1]["seq"], 2)

    def test_project_key_is_shared_by_a_worktree_and_the_main_checkout(self):
        worktree = Path(self.scratch.name) / "wt"
        git(["worktree", "add", "-q", "-b", "feature", str(worktree)], self.root)
        coordination_log.append(str(self.root), "s1", "request.received", id="R1")
        coordination_log.append(str(worktree), "s1", "request.received", id="R2")
        events = coordination_log.read(str(self.root))["events"]
        self.assertEqual([e["id"] for e in events], ["R1", "R2"])
        self.assertEqual(events, coordination_log.read(str(worktree))["events"])

    def test_non_git_cwd_falls_back_to_resolved_cwd_and_is_distinct_per_directory(self):
        one = Path(self.scratch.name) / "plain-one"
        two = Path(self.scratch.name) / "plain-two"
        one.mkdir()
        two.mkdir()
        coordination_log.append(str(one), "s1", "request.received", id="R1")
        coordination_log.append(str(two), "s1", "request.received", id="R2")
        self.assertEqual([e["id"] for e in coordination_log.read(str(one))["events"]], ["R1"])
        self.assertEqual([e["id"] for e in coordination_log.read(str(two))["events"]], ["R2"])

    def test_is_notification_matches_the_four_markers(self):
        self.assertTrue(coordination_log.is_notification("<task-notification>done</task-notification>"))
        self.assertTrue(coordination_log.is_notification("SYSTEM NOTIFICATION - NOT USER INPUT: x"))
        self.assertTrue(coordination_log.is_notification('<teammate-message teammate_id="x">hi'))
        self.assertTrue(coordination_log.is_notification("Another Claude session sent a message: hi"))
        self.assertFalse(coordination_log.is_notification("please fix the bug"))

    def test_log_file_and_capture_failed_marker_are_mode_0600(self):
        coordination_log.append(str(self.root), "s1", "request.received", id="R1")
        path = coordination_log._log_path(str(self.root))
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        coordination_log.mark_capture_failed(str(self.root))
        marker = coordination_log._coordination_dir() / f"{coordination_log._key(str(self.root))}.capture_failed"
        self.assertEqual(stat.S_IMODE(marker.stat().st_mode), 0o600)

    def test_two_processes_appending_fifty_events_each_lose_none(self):
        processes = [multiprocessing.Process(target=_append_batch, args=(str(self.state_dir), str(self.root), worker, 50))
                     for worker in range(2)]
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=60)
            self.assertEqual(process.exitcode, 0)
        events = coordination_log.read(str(self.root))["events"]
        self.assertEqual(len(events), 100)
        seqs = [e["seq"] for e in events]
        self.assertEqual(sorted(seqs), list(range(1, 101)))
        self.assertEqual(len(set(seqs)), 100)
        ids = {e["id"] for e in events}
        self.assertEqual(len(ids), 100)


if __name__ == "__main__":
    unittest.main()
