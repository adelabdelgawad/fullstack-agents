"""Explicit task ledgers are validated, scoped to a session root and reread live."""
import contextlib
from datetime import datetime, timedelta, timezone
import time
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
        self.assertIn("must be the session cwd or a git repository root", tasks.load_tasks("session-1", nested)["error"])
        record = self.state / "session-1.json"
        record.write_text(json.dumps({"session_id": "other", "root": str(self.root), "file": str(self.path)}))
        self.assertIn("session does not match", tasks.load_tasks("session-1", self.root)["error"])

    def test_ledger_may_live_in_another_git_repository_than_the_cwd(self):
        (self.root / ".git").mkdir()
        self.bind()
        project = self.base / "project"
        project.mkdir()
        loaded = tasks.load_tasks("session-1", project)
        self.assertNotIn("error", loaded)
        self.assertEqual(loaded["relative_file"], "TASKS.md")

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
        self.assertEqual(result["items"][0]["status"], "in_progress")
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

    def deadline(self, seconds=120):
        return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")

    def set_task(self, *arguments):
        return self.invoke("set", "--root", str(self.root), "--file", str(self.path), "--id", "T1", *arguments)

    def test_running_compatibility_normalizes_to_canonical_in_progress(self):
        legacy = self.ledger().replace("| T1 | pending |", "| T1 | running |")
        result = self.bind(legacy)
        self.assertEqual(result["items"][0]["status"], "in_progress")
        self.assertEqual(result["counts"]["in_progress"], 1)
        self.assertNotIn("running", result["counts"])
        self.set_task("--status", "running")
        result = tasks.load_tasks("session-1", self.root)
        self.assertEqual(result["items"][0]["status"], "in_progress")
        self.assertIn("| T1 | in_progress |", self.path.read_text())

    def test_extended_columns_roundtrip_escaped_metadata_without_executing_html(self):
        owner = "lead | browser\\worker"
        activity = '<img src=x onerror="alert(1)"> | inspect'
        deadline = self.deadline()
        result = self.bind(self.ledger([tasks._item("T1", "in_progress", "Inspect | UI", "Keep note", owner=owner, activity=activity, active_until=deadline)]))
        self.assertIn("| Owner | Activity | Active until |", self.path.read_text())
        item = result["items"][0]
        self.assertEqual((item["owner"], item["activity"], item["active_until"]), (owner, activity, deadline))
        self.assertTrue(item["is_active"])
        self.assertEqual(result["active"], 1)
        self.assertEqual(result["completed"], 0)
        self.assertEqual(tasks._parse(self.path.read_text())[0][0]["activity"], activity)
        self.set_task("--status", "in_progress", "--note", "Updated | note")
        reread = tasks.load_tasks("session-1", self.root)["items"][0]
        self.assertEqual((reread["owner"], reread["activity"]), (owner, activity))
        self.assertEqual(reread["note"], "Updated | note")

    def test_extended_rows_with_missing_metadata_cells_are_explicit_errors(self):
        self.bind(self.ledger([tasks._item("T1", "in_progress", "Task", "", owner="lead", activity="Checks", active_until=self.deadline())]))
        malformed = self.path.read_text().replace("| lead | Checks |", "| lead |")
        self.path.write_text(malformed)
        result = tasks.load_tasks("session-1", self.root)
        self.assertIn("error", result)
        self.assertNotIn("active", result)
        self.assertNotIn("completed", result)

    def test_four_column_table_remains_valid_and_incomplete_counts_do_not_imply_activity(self):
        result = self.bind(self.ledger([tasks._item("T1", "in_progress", "No heartbeat", ""), tasks._item("T2", "pending", "Queued", ""), tasks._item("T3", "blocked", "Dependency", "")]))
        self.assertNotIn("| Owner |", self.path.read_text())
        self.assertEqual((result["total"], result["completed"], result["active"]), (3, 0, 0))
        self.assertEqual((result["counts"]["in_progress"], result["counts"]["pending"], result["counts"]["blocked"]), (1, 1, 1))
        self.assertTrue(all(item["is_active"] is False for item in result["items"]))

    def test_expired_and_file_mtime_capped_leases_do_not_remain_busy(self):
        expired = self.bind(self.ledger([tasks._item("T1", "in_progress", "Expired", "", owner="lead", activity="Checks", active_until=self.deadline(-60))]))
        self.assertFalse(expired["items"][0]["is_active"])
        self.assertEqual(expired["active"], 0)
        self.path.write_text(self.ledger([tasks._item("T1", "in_progress", "Future claim", "", owner="lead", activity="Checks", active_until=self.deadline(3600))]))
        old = time.time() - 301
        os.utime(self.path, (old, old))
        capped = tasks.load_tasks("session-1", self.root)
        self.assertEqual(capped["counts"]["in_progress"], 1)
        self.assertFalse(capped["items"][0]["is_active"])
        self.assertEqual(capped["active"], 0)

    def test_active_for_requires_in_progress_owner_and_activity_and_is_bounded(self):
        self.bind()
        invalid = [
            ["--status", "pending", "--owner", "lead", "--activity", "Checks", "--active-for", "60"],
            ["--status", "in_progress", "--activity", "Checks", "--active-for", "60"],
            ["--status", "in_progress", "--owner", "lead", "--active-for", "60"],
            ["--status", "in_progress", "--owner", "lead", "--activity", "Checks", "--active-for", "301"],
            ["--status", "in_progress", "--owner", "lead", "--activity", "Checks", "--active-for", "-1"],
        ]
        original = self.path.read_bytes()
        for arguments in invalid:
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.set_task(*arguments)
            self.assertEqual(self.path.read_bytes(), original)
        self.set_task("--status", "in_progress", "--owner", "lead", "--activity", "Checks", "--active-for", "300")
        result = tasks.load_tasks("session-1", self.root)
        self.assertTrue(result["items"][0]["is_active"])
        self.assertEqual(result["active"], 1)
        remaining = datetime.fromisoformat(result["items"][0]["active_until"].replace("Z", "+00:00")).timestamp() - time.time()
        self.assertGreater(remaining, 290)
        self.assertLessEqual(remaining, 300)
        self.set_task("--status", "in_progress", "--active-for", "0")
        cleared = tasks.load_tasks("session-1", self.root)
        self.assertEqual(cleared["items"][0]["active_until"], "")
        self.assertEqual(cleared["active"], 0)

    def test_owner_transfer_clears_previous_activity_and_lease(self):
        self.bind(self.ledger([tasks._item("T1", "in_progress", "Working", "", owner="old owner", activity="Old checks", active_until=self.deadline())]))
        self.set_task("--status", "in_progress", "--owner", "new owner")
        result = tasks.load_tasks("session-1", self.root)
        item = result["items"][0]
        self.assertEqual((item["owner"], item["activity"], item["active_until"]), ("new owner", "", ""))
        self.assertFalse(item["is_active"])
        self.assertEqual(result["active"], 0)

    def test_owner_transfer_cannot_renew_previous_owners_activity_without_a_fresh_description(self):
        self.bind(self.ledger([tasks._item("T1", "in_progress", "Working", "", owner="old owner", activity="Old checks", active_until=self.deadline())]))
        original = self.path.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.set_task("--status", "in_progress", "--owner", "new owner", "--active-for", "60")
        self.assertEqual(self.path.read_bytes(), original)
        self.set_task("--status", "running", "--owner", "new owner", "--activity", "New checks", "--active-for", "60")
        result = tasks.load_tasks("session-1", self.root)
        self.assertEqual((result["items"][0]["owner"], result["items"][0]["activity"]), ("new owner", "New checks"))
        self.assertEqual(result["active"], 1)

    def test_nonprogress_status_clears_active_deadline_without_counting_it_as_done(self):
        self.bind()
        for status in ("pending", "blocked", "done", "skipped", "canceled"):
            self.path.write_text(self.ledger([tasks._item("T1", "in_progress", "Working", "", owner="lead", activity="Checks", active_until=self.deadline())]))
            self.set_task("--status", status)
            result = tasks.load_tasks("session-1", self.root)
            self.assertEqual(result["items"][0]["active_until"], "")
            self.assertFalse(result["items"][0]["is_active"])
            self.assertEqual(result["active"], 0)
            self.assertEqual(result["completed"], int(status == "done"))

    def test_timezone_offsets_are_accepted_and_resolve_to_the_same_instant(self):
        offset = "2026-10-15T12:00:00+02:00"
        item = tasks._item("T1", "in_progress", "Task", "", owner="lead", activity="Checks", active_until=offset)
        self.assertEqual(item["active_until"], offset)
        self.assertEqual(tasks._deadline(offset), tasks._deadline("2026-10-15T10:00:00Z"))

    def test_metadata_control_characters_and_invalid_deadlines_are_rejected(self):
        for key, value in [("owner", "bad\nowner"), ("activity", "bad\tactivity"), ("owner", "bad\x1bowner"), ("activity", tasks.END), ("active_until", "tomorrow"), ("active_until", "2026-10-15T12:00:00")]:
            kwargs = {"owner": "lead", "activity": "Checks", "active_until": self.deadline(), key: value}
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                tasks._item("T1", "in_progress", "Task", "", **kwargs)
        self.bind()
        original = self.path.read_bytes()
        for flag, value in [("--owner", "bad\nowner"), ("--activity", "bad\tactivity")]:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.set_task("--status", "in_progress", flag, value)
            self.assertEqual(self.path.read_bytes(), original)


    def show(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(["show", "--root", str(self.root), "--file", str(self.path), *args]), 0)
        return output.getvalue()

    def test_add_appends_new_rows_and_upserts_existing_ones_keeping_owner_and_activity(self):
        self.bind(self.ledger([tasks._item("T1", "in_progress", "Old title", "Old note", owner="lead", activity="Checks", active_until=self.deadline())]))
        before = self.path.read_text()
        self.invoke("add", "--root", str(self.root), "--file", "TASKS.md", "--task", "T1|in_progress|New title|New note", "--task", "S4a|pending|Brief A|", "--task", "V1|running|Compile check|cargo check")
        after = self.path.read_text()
        self.assertEqual(before.split(tasks.START)[0], after.split(tasks.START)[0])
        self.assertEqual(before.split(tasks.END)[1], after.split(tasks.END)[1])
        items = tasks.load_tasks("session-1", self.root)["items"]
        self.assertEqual([item["id"] for item in items], ["T1", "S4a", "V1"])
        self.assertEqual((items[0]["title"], items[0]["note"], items[0]["owner"], items[0]["activity"]), ("New title", "New note", "lead", "Checks"))
        self.assertTrue(items[0]["is_active"])
        self.assertEqual(items[2]["status"], "in_progress")
        self.invoke("add", "--root", str(self.root), "--file", "TASKS.md", "--task", "T1|done|New title|Verified")
        item = tasks.load_tasks("session-1", self.root)["items"][0]
        self.assertEqual((item["status"], item["owner"], item["active_until"]), ("done", "lead", ""))

    def test_add_rejects_malformed_specs_and_row_overflow_without_writes(self):
        self.bind(self.ledger([tasks._item(str(index), "pending", "Task", "") for index in range(tasks.MAX_ROWS - 1)]))
        original = self.path.read_bytes()
        for specs in (["X|pending|Title"], ["X|complete|Title|"], ["X|pending| |"], ["X|pending|One|", "Y|pending|Two|"]):
            with self.subTest(specs=specs), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                tasks.main(["add", "--root", str(self.root), "--file", "TASKS.md", *[arg for spec in specs for arg in ("--task", spec)]])
            self.assertEqual(self.path.read_bytes(), original)
        self.invoke("add", "--root", str(self.root), "--file", "TASKS.md", "--task", "0|done|Task|Upsert at the limit", "--task", "X|pending|Last|")
        self.assertEqual(tasks.load_tasks("session-1", self.root)["total"], tasks.MAX_ROWS)

    def test_set_applies_one_change_to_several_ids_and_keeps_status_when_omitted(self):
        self.bind(self.ledger([tasks._item("T1", "pending", "First", ""), tasks._item("T2", "blocked", "Second", "Waits on T1"), tasks._item("T3", "pending", "Third", "")]))
        self.invoke("set", "--root", str(self.root), "--file", "TASKS.md", "--id", "T1", "--id", "T2", "--note", "Batch note", "--owner", "lead")
        items = tasks.load_tasks("session-1", self.root)["items"]
        self.assertEqual([(item["status"], item["note"], item["owner"]) for item in items],
                         [("pending", "Batch note", "lead"), ("blocked", "Batch note", "lead"), ("pending", "", "")])
        self.invoke("set", "--root", str(self.root), "--file", "TASKS.md", "--id", "T1", "--id", "T3", "--status", "done")
        self.assertEqual([item["status"] for item in tasks.load_tasks("session-1", self.root)["items"]], ["done", "blocked", "done"])
        original = self.path.read_bytes()
        for arguments in (["--id", "T2", "--id", "missing", "--status", "done"], ["--id", "T2", "--activity", "Checks", "--active-for", "60"]):
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                tasks.main(["set", "--root", str(self.root), "--file", "TASKS.md", *arguments])
            self.assertEqual(self.path.read_bytes(), original)

    def test_show_prints_compact_summary_and_json_on_request(self):
        long_note = "n" * 150
        self.bind(self.ledger([tasks._item("S4a", "done", "Brief A", "Audited"), tasks._item("S4b", "in_progress", "Brief B", long_note, owner="codex", activity="implementing S4b", active_until=self.deadline()),
                               tasks._item("V1", "blocked", "Compile check", ""), tasks._item("V2", "pending", "Focused tests", "")]))
        lines = self.show().splitlines()
        self.assertEqual(lines[0], "done 1/4 · in_progress 1 · blocked 1 · pending 1 · active 1")
        self.assertEqual(lines[1], "S4b  in_progress  [codex: implementing S4b]  Brief B — " + "n" * 99 + "…")
        self.assertEqual(lines[2:], ["V1  blocked  Compile check", "V2  pending  Focused tests"])
        summary = json.loads(self.show("--json"))
        self.assertEqual((summary["total"], summary["completed"], summary["active"], summary["file"]), (4, 1, 1, str(self.path)))

if __name__ == "__main__":
    unittest.main()
