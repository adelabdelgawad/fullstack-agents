"""Format-v2 lifecycle and compatibility coverage."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "plugins/fullstack-agents/scripts/lib"
SPEC = importlib.util.spec_from_file_location("task_tracking_v2", LIB / "task_tracking.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)


class TaskFormatV2Tests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-v2-")
        self.root = Path(self.scratch.name) / "repo"
        self.root.mkdir()
        self.path = self.root / "TASKS.md"
        self.env = patch.dict(os.environ, {"FSA_TASKS_DIR": str(Path(self.scratch.name) / "state"),
                                           "CODEX_THREAD_ID": "v2-session"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.scratch.cleanup()

    def call(self, command, *args, fails=False):
        argv = [command, "--root", str(self.root), "--file", "TASKS.md", "--session", "v2-session", *args]
        if fails:
            error = io.StringIO()
            with contextlib.redirect_stderr(error), self.assertRaises(SystemExit):
                tasks.main(argv)
            return error.getvalue()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(argv), 0)
        return json.loads(output.getvalue())

    def init(self, *taskspecs, legacy=False):
        args = (["--format", "legacy"] if legacy else [])
        for spec in taskspecs:
            args += ["--task", spec]
        return self.call("init", *args)

    def test_init_defaults_v2_and_legacy_is_explicit(self):
        result = self.init("D1|pending|Deliverable|")
        self.assertEqual(result["format"], "v2")
        self.assertIn(tasks.V2_HEADERS, [tasks._cells(line) for line in self.path.read_text().splitlines() if line.startswith("|")])
        self.assertIn(" init", self.path.read_text())
        self.path.unlink()
        result = self.init("D1|pending|Deliverable|", legacy=True)
        self.assertEqual(result["format"], "legacy")
        self.assertNotIn(tasks.LOG_START, self.path.read_text())

    def test_strict_headers_and_log_markers(self):
        self.init("D1|pending|Deliverable|")
        valid = self.path.read_text()
        malformed = [valid.replace("| Parent |", "| Unknown |"),
                     valid.replace("| ID | Status |", "| Status | ID |"),
                     valid.replace(tasks.LOG_START, ""), valid.replace(tasks.LOG_START, "prefix " + tasks.LOG_START)]
        for text in malformed:
            self.path.write_text(text)
            result = tasks.load_tasks("v2-session", self.root)
            self.assertIn("error", result)

    def test_hand_written_invalid_parent_graphs_are_refused(self):
        self.init("D1|pending|Deliverable|", "D2|pending|Second|")
        valid = self.path.read_text()
        cases = (("| D1 | pending | Deliverable |  |  |  |  |  |",
                  "| D1 | pending | Deliverable |  |  |  |  | D1 |", "cannot parent itself"),
                 ("| D1 | pending | Deliverable |  |  |  |  |  |",
                  "| D1 | pending | Deliverable |  |  |  |  | missing |", "Unknown parent"),
                 ("| D1 | pending | Deliverable |  |  |  |  |  |\n| D2 | pending | Second |  |  |  |  |  |",
                  "| D1 | pending | Deliverable |  |  |  |  | D2 |\n| D2 | pending | Second |  |  |  |  | D1 |",
                  "cannot be a parent"))
        for old, new, message in cases:
            self.path.write_text(valid.replace(old, new))
            self.assertIn(message, tasks.load_tasks("v2-session", self.root)["error"])

    def test_upgrade_downgrade_roundtrip_and_refusals(self):
        self.init("D1|pending|Deliverable|", legacy=True)
        table = self.path.read_text().split(tasks.START)[1].split(tasks.END)[0]
        self.call("upgrade")
        self.assertEqual(tasks.load_tasks("v2-session", self.root)["format"], "v2")
        self.call("downgrade")
        text = self.path.read_text()
        self.assertEqual(text.split(tasks.START)[1].split(tasks.END)[0], table)
        self.assertIn(" upgrade from=\"4\"", text)
        self.assertIn(" downgrade to=\"4\"", text)
        self.call("upgrade")
        self.call("set", "--id", "D1", "--status", "verifying")
        self.assertIn("D1", self.call("downgrade", fails=True))

    def test_latest_upgrade_width_controls_downgrade(self):
        self.init("D1|pending|Deliverable|", legacy=True)
        self.call("upgrade")
        self.call("downgrade")
        self.call("set", "--id", "D1", "--owner", "lead")
        self.call("upgrade")
        self.call("downgrade")
        header = next(line for line in self.path.read_text().splitlines() if line.startswith("| ID |"))
        self.assertEqual(len(tasks._cells(header)), 7)

    def test_legacy_verifying_and_duplicate_batches_are_refused(self):
        self.init("D1|pending|Deliverable|", legacy=True)
        original = self.path.read_bytes()
        self.assertIn("verifying requires a v2 ledger", self.call("set", "--id", "D1", "--status", "verifying", fails=True))
        for args in (("--task", "D1|done|Duplicate|"),
                     ("--task", "X|pending|X|", "--task", "X|pending|X again|")):
            self.call("add", *args, fails=True)
            self.assertEqual(self.path.read_bytes(), original)

    def test_parent_rules_reopen_reason_and_deliverable_counts(self):
        # D2 starts done pre-L2 (legacy init + upgrade, completion unrecorded) so this stays about parent/step
        # mechanics rather than the completion-evidence gate.
        self.init("D1|pending|Deliverable|", "D2|done|Done parent|", legacy=True)
        self.call("upgrade")
        self.call("add", "--parent", "D1", "--task", "R1|pending|Repair|")
        summary = tasks.load_tasks("v2-session", self.root)
        self.assertEqual((summary["deliverables"]["total"], summary["steps"]["total"]), (2, 1))
        self.assertIn("close the steps first", self.call("set", "--id", "D1", "--status", "done", fails=True))
        self.assertIn("close the steps first", self.call("set", "--id", "D1", "--status", "canceled", fails=True))
        self.assertIn("reopen the parent", self.call("add", "--parent", "D2", "--task", "R2|pending|Repair|", fails=True))
        self.call("add", "--parent", "D2", "--task", "R3|done|Recorded repair|")
        self.assertIn("requires set --reason", self.call("set", "--id", "D2", "--status", "in_progress", fails=True))
        self.call("set", "--id", "D2", "--status", "in_progress", "--reason", "new work")
        # Hand-edit back to done: no evidence spec is recorded for D2, so the gated `set` would refuse it.
        self.path.write_text(self.path.read_text().replace("| D2 | in_progress |", "| D2 | done |"))
        self.assertIn("reopen the parent", self.call("set", "--id", "R3", "--status", "in_progress",
                                                       "--reason", "redo", fails=True))
        self.assertIn('reason="new work"', self.path.read_text())
        for parent in ("missing", "R1"):
            self.assertTrue(self.call("add", "--parent", parent, "--task", f"X{parent}|done|Child|", fails=True))

    def test_log_marker_in_title_is_refused(self):
        self.init("D1|pending|Deliverable|")
        self.assertIn("ledger markers", self.call("set", "--id", "D1", "--title",
                                                   f"Bad {tasks.LOG_START} title", fails=True))

    def test_title_log_is_append_only_and_nonlog_bytes_are_preserved(self):
        self.init("D1|pending|Old title|")
        text = self.path.read_text().replace("# Tasks", "# Tasks\n\nUntouched prose")
        self.path.write_text(text)
        before_log = text.split(tasks.LOG_START)[1].split(tasks.LOG_END)[0]
        self.call("set", "--id", "D1", "--title", "New title")
        after = self.path.read_text()
        self.assertTrue(after.split(tasks.LOG_START)[1].split(tasks.LOG_END)[0].startswith(before_log))
        self.assertIn("Untouched prose", after)
        self.assertIn('title from="Old title" to="New title"', after)

    def test_set_preserves_checkpoint_ownership_log_and_prose_bytes(self):
        self.init("D1|pending|Deliverable|")
        checkpoint = '<!-- fsa:checkpoint:start -->\n```json\n{"kept": "byte exact"}\n```\n<!-- fsa:checkpoint:end -->'
        ownership = '<!-- fsa:ownership:start -->\nowner bytes\n<!-- fsa:ownership:end -->'
        prose = "\nProse bytes: café  \n"
        text = self.path.read_text().replace(tasks.END, tasks.END + "\n\n" + checkpoint + "\n\n" + ownership + prose)
        self.path.write_text(text)
        self.call("set", "--id", "D1", "--note", "changed")
        after = self.path.read_text()
        for unchanged in (checkpoint, ownership, prose):
            self.assertIn(unchanged, after)
        self.assertEqual(tasks.load_tasks("v2-session", self.root)["items"][0]["note"], "changed")

    def test_size_refusal_leaves_bytes_unchanged(self):
        self.init("D1|pending|Deliverable|")
        original_limit = tasks.MAX_BYTES
        original = self.path.read_bytes()
        tasks.MAX_BYTES = len(original) + 5
        try:
            error = self.call("set", "--id", "D1", "--title", "A much longer title", fails=True)
        finally:
            tasks.MAX_BYTES = original_limit
        self.assertIn("ledger too large: close or split it", error)
        self.assertEqual(self.path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
