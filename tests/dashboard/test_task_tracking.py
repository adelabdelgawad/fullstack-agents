"""Explicit task ledgers are validated, scoped to a session root and reread live."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "plugins/fullstack-agents/scripts/lib/task_tracking.py"
SPEC = importlib.util.spec_from_file_location("task_tracking", MODULE)
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)
CLI = REPO / "plugins/fullstack-agents/scripts/fsa-task"


class TaskTrackingTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-tasks-")
        self.base = Path(self.scratch.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.state = self.base / "state"
        self.env = patch.dict(os.environ, {"FSA_TASKS_DIR": str(self.state), "CODEX_THREAD_ID": "session-1"})
        self.env.start()
        self.path = self.root / "TASKS.md"

    def tearDown(self):
        self.env.stop()
        self.scratch.cleanup()

    def ledger(self, rows=None):
        items = rows if rows is not None else [tasks._item("T1", "pending", "Implement API", "Awaiting work")]
        return "# Feature tasks\n\nProse before.\n\n" + tasks.START + tasks._render(items) + tasks.END + "\n\nProse after.\n"

    def bind(self, text=None):
        self.path.write_text(text if text is not None else self.ledger())
        return tasks.bind_tasks("session-1", self.root, self.path)

    def invoke(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = tasks.main(list(args))
        self.assertEqual(status, 0)
        return json.loads(output.getvalue())

    def test_unbound_session_has_no_inferred_tasks(self):
        self.assertEqual(tasks.load_tasks("unbound", self.root), {})

    def test_binding_has_exact_keys_and_only_done_counts_as_completed(self):
        rows = [tasks._item(str(index), status, status.title(), "") for index, status in enumerate(tasks.STATUSES)]
        result = self.bind(self.ledger(rows))
        self.assertEqual(result["file"], str(self.path))
        self.assertEqual(result["relative_file"], "TASKS.md")
        self.assertEqual(result["title"], "Feature tasks")
        self.assertEqual(result["total"], 6)
        self.assertEqual(result["completed"], 1)
        self.assertEqual(result["counts"], dict.fromkeys(tasks.STATUSES, 1))
        self.assertIsInstance(result["updated"], float)
        self.assertEqual(json.loads((self.state / "session-1.json").read_text()), {"session_id": "session-1", "root": str(self.root), "file": str(self.path)})

    def test_live_edit_is_reread_and_missing_document_is_not_complete(self):
        self.bind()
        self.path.write_text(self.ledger([tasks._item("T1", "done", "Implement API", "Tested")]))
        self.assertEqual(tasks.load_tasks("session-1", self.root)["completed"], 1)
        self.path.unlink()
        result = tasks.load_tasks("session-1", self.root)
        self.assertIn("error", result)
        self.assertNotIn("completed", result)

    def test_session_and_root_must_match_registration(self):
        self.bind()
        nested = self.root / "nested"
        nested.mkdir()
        self.assertIn("root does not match", tasks.load_tasks("session-1", nested)["error"])
        record = self.state / "session-1.json"
        record.write_text(json.dumps({"session_id": "other", "root": str(self.root), "file": str(self.path)}))
        self.assertIn("session does not match", tasks.load_tasks("session-1", self.root)["error"])

    def test_absent_session_cwd_cannot_match_process_working_directory(self):
        self.bind()
        for cwd in ("", None):
            self.assertIn("error", tasks.load_tasks("session-1", cwd))

    def test_session_identifier_rejects_path_traversal_and_long_values(self):
        for sid in ("../escape", "/tmp/task", ".", "a/b", "x" * 201, "has space", "x\n"):
            with self.subTest(sid=sid):
                self.assertIn("error", tasks.load_tasks(sid, self.root))
        self.assertFalse((self.base / "escape.json").exists())

    def test_path_traversal_nonmarkdown_and_symlink_escape_are_rejected(self):
        outside = self.base / "OUTSIDE.md"
        outside.write_text(self.ledger())
        link = self.root / "link.md"
        link.symlink_to(outside)
        nonmarkdown = self.root / "tasks.py"
        nonmarkdown.write_text(self.ledger())
        for path in ("../OUTSIDE.md", outside, link, nonmarkdown):
            with self.subTest(path=path), self.assertRaises(ValueError):
                tasks.bind_tasks("session-1", self.root, path)
        parent = self.root / "external"
        parent.symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(ValueError):
            tasks._file(self.root, parent / "new.md", existing=False)

    def test_symlink_swapped_after_binding_is_revalidated(self):
        self.bind()
        outside = self.base / "outside.md"
        outside.write_text(self.ledger([tasks._item("T1", "done", "Outside", "")]))
        self.path.unlink()
        self.path.symlink_to(outside)
        result = tasks.load_tasks("session-1", self.root)
        self.assertIn("inside", result["error"])
        self.assertNotIn("completed", result)

    def test_broken_or_symlinked_registration_is_explicitly_invalid(self):
        self.state.mkdir()
        registration = self.state / "session-1.json"
        registration.write_text("not JSON")
        self.assertIn("error", tasks.load_tasks("session-1", self.root))
        registration.unlink()
        registration.symlink_to(self.base / "missing")
        self.assertIn("symlink", tasks.load_tasks("session-1", self.root)["error"])

    def test_fifo_registration_cannot_block_dashboard_read(self):
        self.state.mkdir()
        os.mkfifo(self.state / "session-1.json")
        self.assertIn("regular file", tasks.load_tasks("session-1", self.root)["error"])

    def test_malformed_markdown_never_silently_drops_rows(self):
        valid = self.ledger()
        malformed = [valid.replace(tasks.START, ""), valid + tasks.END,
                     valid.replace("| T1 | pending", "| T1 | complete"),
                     valid.replace("| T1 | pending | Implement API | Awaiting work |", "T1 pending Implement API"),
                     valid.replace("| --- | --- | --- | --- |", "| -- | --- | --- | --- |"),
                     valid.replace("| ID | Status | Task | Note |", "| ID | Status | Title | Note |"),
                     valid.replace(tasks.END, "| T1 | done | Duplicate | |\n" + tasks.END),
                     valid.replace(tasks.START, "prefix " + tasks.START),
                     valid.replace(tasks.START, "SWAP_START").replace(tasks.END, tasks.START).replace("SWAP_START", tasks.END)]
        self.bind()
        for text in malformed:
            with self.subTest(text=text):
                self.path.write_text(text)
                result = tasks.load_tasks("session-1", self.root)
                self.assertIn("error", result)
                self.assertNotIn("completed", result)

    def test_limits_are_checked_before_counting(self):
        self.bind()
        self.path.write_text("x" * (tasks.MAX_BYTES + 1))
        self.assertIn("exceeds", tasks.load_tasks("session-1", self.root)["error"])
        self.path.write_text(self.ledger([tasks._item(str(index), "done", "Done", "") for index in range(201)]))
        self.assertIn("200 rows", tasks.load_tasks("session-1", self.root)["error"])

    def test_init_does_not_overwrite_and_set_preserves_outside_prose_and_note(self):
        result = self.invoke("init", "--root", str(self.root), "--file", "TASKS.md", "--title", "Feature tasks", "--task", "T1|running|Implement API|Keep this note")
        self.assertEqual(result["items"][0]["status"], "running")
        before = self.ledger([tasks._item("T1", "running", "Implement API", "Keep this note")])
        self.path.write_text(before)
        original = self.path.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            tasks.main(["init", "--root", str(self.root), "--file", "TASKS.md"])
        self.assertEqual(self.path.read_bytes(), original)
        self.invoke("set", "--root", str(self.root), "--file", "TASKS.md", "--id", "T1", "--status", "done")
        after = self.path.read_text()
        self.assertEqual(before.split(tasks.START)[0], after.split(tasks.START)[0])
        self.assertEqual(before.split(tasks.END)[1], after.split(tasks.END)[1])
        self.assertEqual(tasks.load_tasks("session-1", self.root)["items"][0]["note"], "Keep this note")
        self.assertEqual(tasks.load_tasks("session-1", self.root)["completed"], 1)
        self.assertEqual(set(self.root.iterdir()), {self.path})

    def test_set_rejects_missing_id_and_injected_note_without_writes(self):
        self.bind()
        original = self.path.read_bytes()
        for identifier, note in (("missing", "No"), ("T1", "bad\nnote"), ("T1", tasks.END)):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                tasks.main(["set", "--root", str(self.root), "--file", str(self.path), "--id", identifier, "--status", "done", "--note", note])
            self.assertEqual(self.path.read_bytes(), original)

    def test_atomic_replace_failure_leaves_old_document_and_cleans_temporary(self):
        self.bind()
        original = self.path.read_bytes()
        with patch.object(tasks.os, "replace", side_effect=OSError("replacement failed")), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            tasks.main(["set", "--root", str(self.root), "--file", str(self.path), "--id", "T1", "--status", "done"])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(set(self.root.iterdir()), {self.path})

    def test_concurrent_set_intents_do_not_lose_each_others_rows(self):
        self.bind(self.ledger([tasks._item("T1", "pending", "First", ""), tasks._item("T2", "pending", "Second", "")]))
        children = [subprocess.Popen([sys.executable, str(CLI), "set", "--root", str(self.root), "--file", "TASKS.md", "--id", identifier, "--status", "done"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for identifier in ("T1", "T2")]
        for child in children:
            _, error = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, error)
        self.assertEqual(tasks.load_tasks("session-1", self.root)["completed"], 2)

    def test_escaped_pipes_backslashes_and_html_are_data_not_executable_metadata(self):
        title = "Render | <script>ignore</script> \\ path"
        self.bind(self.ledger([tasks._item("T1", "pending", title, "A | B")]))
        result = tasks.load_tasks("session-1", self.root)
        self.assertEqual(result["items"][0]["title"], title)
        self.invoke("set", "--root", str(self.root), "--file", str(self.path), "--id", "T1", "--status", "running", "--note", "C | D")
        self.assertEqual(tasks.load_tasks("session-1", self.root)["items"][0]["note"], "C | D")

    def test_cli_environment_default_and_copied_codex_entrypoint(self):
        process = subprocess.run([sys.executable, str(CLI), "init", "--root", str(self.root), "--file", "TASKS.md", "--task", "T1|pending|Task|"], text=True, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(tasks.load_tasks("session-1", self.root)["total"], 1)
        bundle = self.base / "bundle"
        bundle.mkdir()
        (bundle / "tasks.py").write_bytes((REPO / "integrations/codex/scripts/tasks.py").read_bytes())
        (bundle / "task_tracking.py").write_bytes(MODULE.read_bytes())
        process = subprocess.run([sys.executable, str(bundle / "tasks.py"), "set", "--root", str(self.root), "--file", "TASKS.md", "--id", "T1", "--status", "blocked", "--note", "Dependency"], text=True, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(tasks.load_tasks("session-1", self.root)["counts"]["blocked"], 1)


if __name__ == "__main__":
    unittest.main()
