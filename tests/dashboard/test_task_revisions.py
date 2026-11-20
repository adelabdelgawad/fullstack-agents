"""`fsa-task revise`, the dispatch/finish revision fence and worker-blocker resolution refusal.
See docs/TASK_LIFECYCLE_DESIGN.md §15 (Unit C)."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import sys
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "plugins/fullstack-agents/scripts/lib"
sys.path.insert(0, str(LIB))
import coordination_log  # noqa: E402
import task_revisions  # noqa: E402

SPEC = importlib.util.spec_from_file_location("task_tracking_revision_test", LIB / "task_tracking.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)

SESSION = "rev-session"


def git(args, cwd):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


class RevisionTestCase(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-revisions-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name) / "repo"
        self.root.mkdir()
        git(["init", "-q"], self.root)
        git(["config", "user.email", "a@example.com"], self.root)
        git(["config", "user.name", "Test"], self.root)
        (self.root / "README.md").write_text("doc\n")
        git(["add", "-A"], self.root)
        git(["commit", "-q", "-m", "initial"], self.root)
        self.env = patch.dict(os.environ, {"FSA_TASKS_DIR": str(Path(self.scratch.name) / "tasks"),
                                            "CODEX_THREAD_ID": SESSION})
        self.env.start()
        self.addCleanup(self.env.stop)

    def bind(self, filename="TASKS.md"):
        argv = ["init", "--root", str(self.root), "--file", filename, "--session", SESSION,
                "--task", "R1|pending|Row one|", "--task", "R2|pending|Row two|"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tasks.main(argv), 0)
        return filename

    def run_command(self, command, *args, session=SESSION):
        argv = [command, "--root", str(self.root), "--session", session, *args]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(argv), 0)
        text = output.getvalue()
        return json.loads(text) if text.strip() else None

    def run_command_fail(self, command, *args, session=SESSION):
        argv = [command, "--root", str(self.root), "--session", session, *args]
        error = io.StringIO()
        with contextlib.redirect_stderr(error), self.assertRaises(SystemExit):
            tasks.main(argv)
        return error.getvalue()

    def revise(self, *args, **kwargs):
        return self.run_command("revise", *args, **kwargs)

    def revise_fail(self, *args, **kwargs):
        return self.run_command_fail("revise", *args, **kwargs)


class ReviseCliTests(RevisionTestCase):
    def test_first_revision_is_one_and_an_untouched_row_stays_zero(self):
        self.bind()
        result = self.revise("--rows", "R1", "--request", "R1", "--kind", "correction")
        self.assertEqual(result["revisions"], [{"row": "R1", "revision": 1, "runs": []}])
        self.assertEqual(task_revisions.current(self.root, "TASKS.md", "R1")["revision"], 1)
        self.assertEqual(task_revisions.current(self.root, "TASKS.md", "R2")["revision"], 0)

    def test_second_revision_increments_from_the_prior_one(self):
        self.bind()
        self.revise("--rows", "R1", "--request", "R1", "--kind", "correction")
        result = self.revise("--rows", "R1", "--request", "R2", "--kind", "correction", "--note", "retry")
        self.assertEqual(result["revisions"][0]["revision"], 2)

    def test_multiple_rows_bump_together(self):
        self.bind()
        result = self.revise("--rows", "R1,R2", "--request", "R1", "--kind", "correction")
        self.assertEqual([entry["row"] for entry in result["revisions"]], ["R1", "R2"])
        self.assertTrue(all(entry["revision"] == 1 for entry in result["revisions"]))

    def test_cancel_kind_is_recorded_and_still_counts_as_a_revision(self):
        self.bind()
        result = self.revise("--rows", "R2", "--request", "R3", "--kind", "cancel")
        self.assertEqual(result["revisions"][0]["revision"], 1)
        self.assertEqual(task_revisions.current(self.root, "TASKS.md", "R2")["kind"], "cancel")

    def test_revise_requires_a_bound_ledger(self):
        error = self.revise_fail("--rows", "R1", "--request", "R1", "--kind", "correction")
        self.assertIn("requires a bound task ledger", error)

    def test_revise_lists_runs_bound_to_the_row_with_their_stop_command(self):
        self.bind()
        runs = Path(self.scratch.name) / "runs"
        runs.mkdir()
        (runs / "run-1.meta.json").write_text(json.dumps({"schema": 2, "cwd": str(self.root), "engine": "claude",
                                                            "task_file": "TASKS.md", "task_row": "R1"}))
        with patch.dict(os.environ, {"FSA_CODEX_RUNS_DIR": str(runs)}):
            result = self.revise("--rows", "R1", "--request", "R1", "--kind", "correction")
        self.assertEqual(result["revisions"][0]["runs"],
                          [{"run": "run-1", "state": "uncertain", "stop": "codex-task.sh stop run-1"}])

    def test_reconciled_records_a_run_without_bumping_any_revision(self):
        self.bind()
        result = self.revise("--reconciled", "run-9", "--note", "merged by hand")
        self.assertEqual(result, {"run": "run-9", "reconciled": True})
        self.assertEqual(coordination_log.read(str(self.root))["events"][-1]["type"], "revision.reconciled")


class DispatchFenceTests(RevisionTestCase):
    def test_revision_zero_with_no_brief_revision_dispatches(self):
        self.assertIsNone(task_revisions.check_dispatch(self.root, "TASKS.md", "R1", ""))

    def test_stale_revision_is_refused_with_both_numbers_named(self):
        coordination_log.append(str(self.root), SESSION, "revision.bump", task="TASKS.md", row="R1", revision=1,
                                 request="R1", kind="correction", note="")
        self.assertEqual(task_revisions.check_dispatch(self.root, "TASKS.md", "R1", ""),
                          "STATUS=STALE_REVISION (brief revision none, row revision 1)")
        self.assertEqual(task_revisions.check_dispatch(self.root, "TASKS.md", "R1", "2"),
                          "STATUS=STALE_REVISION (brief revision 2, row revision 1)")

    def test_matching_revision_dispatches(self):
        coordination_log.append(str(self.root), SESSION, "revision.bump", task="TASKS.md", row="R1", revision=1,
                                 request="R1", kind="correction", note="")
        self.assertIsNone(task_revisions.check_dispatch(self.root, "TASKS.md", "R1", "1"))

    def test_cancelled_row_refuses_regardless_of_a_matching_revision_line(self):
        coordination_log.append(str(self.root), SESSION, "revision.bump", task="TASKS.md", row="R1", revision=1,
                                 request="R1", kind="cancel", note="")
        self.assertEqual(task_revisions.check_dispatch(self.root, "TASKS.md", "R1", "1"), "STATUS=ROW_CANCELLED")

    def test_is_stale_finish_compares_against_the_recorded_revision(self):
        self.assertFalse(task_revisions.is_stale_finish(self.root, "TASKS.md", "R1", 0))
        coordination_log.append(str(self.root), SESSION, "revision.bump", task="TASKS.md", row="R1", revision=1,
                                 request="R1", kind="correction", note="")
        self.assertTrue(task_revisions.is_stale_finish(self.root, "TASKS.md", "R1", 0))
        self.assertFalse(task_revisions.is_stale_finish(self.root, "TASKS.md", "R1", 1))


class WorkerBlockerRefusalTests(RevisionTestCase):
    def test_refuse_worker_evidence_for_a_stale_result_state(self):
        result_path = Path(self.scratch.name) / "run1.result.json"
        result_path.write_text(json.dumps({"state": "stale_revision"}))
        reason = task_revisions.refuse_worker_evidence(self.root, result_path, ["R1"])
        self.assertIn("stale_revision", reason)

    def test_refuse_worker_evidence_for_a_row_revised_past_the_recorded_one(self):
        runs = Path(self.scratch.name) / "runs"
        runs.mkdir()
        result_path = runs / "run1.result.json"
        result_path.write_text(json.dumps({"state": "succeeded"}))
        (runs / "run1.meta.json").write_text(json.dumps({"task_file": "TASKS.md", "instruction_revision": 0}))
        coordination_log.append(str(self.root), SESSION, "revision.bump", task="TASKS.md", row="R1", revision=1,
                                 request="R1", kind="correction", note="")
        reason = task_revisions.refuse_worker_evidence(self.root, result_path, ["R1"])
        self.assertIn("revision moved past this run", reason)

    def test_refuse_worker_evidence_accepts_a_result_at_the_current_revision(self):
        runs = Path(self.scratch.name) / "runs"
        runs.mkdir()
        result_path = runs / "run1.result.json"
        result_path.write_text(json.dumps({"state": "succeeded"}))
        (runs / "run1.meta.json").write_text(json.dumps({"task_file": "TASKS.md", "instruction_revision": 1}))
        coordination_log.append(str(self.root), SESSION, "revision.bump", task="TASKS.md", row="R1", revision=1,
                                 request="R1", kind="correction", note="")
        self.assertIsNone(task_revisions.refuse_worker_evidence(self.root, result_path, ["R1"]))

    def test_resolve_refuses_a_stale_result_through_the_blocker_cli(self):
        self.bind()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tasks.main(["block", "--root", str(self.root), "--file", "TASKS.md",
                                          "--session", SESSION, "--rows", "R1", "--kind", "worker",
                                          "--text", "worker dispatched for R1"]), 0)
        result_path = Path(self.scratch.name) / "result.json"
        result_path.write_text(json.dumps({"state": "stale_revision"}))
        error = io.StringIO()
        with contextlib.redirect_stderr(error), self.assertRaises(SystemExit):
            tasks.main(["resolve", "--root", str(self.root), "--file", "TASKS.md", "--session", SESSION,
                        "--id", "B1", "--evidence", str(result_path), "--reason", "worker finished"])
        self.assertIn("stale_revision", error.getvalue())


if __name__ == "__main__":
    unittest.main()
