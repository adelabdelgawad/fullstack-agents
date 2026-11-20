"""Result outbox: save-before-send reports, Stop-hook emission evidence, and re-offer after a handover;
see docs/TASK_LIFECYCLE_DESIGN.md §15 (Unit D)."""
import contextlib
import hashlib
import importlib.util
import io
import json
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
GUARD = REPO / "plugins/fullstack-agents/scripts/fsa-stop-guard"
sys.path.insert(0, str(LIB))
import coordination_log
import result_outbox
import stop_guard

SPEC = importlib.util.spec_from_file_location("task_tracking_report_test", LIB / "task_tracking.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)


def git(args, cwd):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


SESSION = "report-session"


class ResultOutboxTestCase(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-reports-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name) / "repo"
        self.root.mkdir()
        git(["init", "-q"], self.root)
        git(["config", "user.email", "a@example.com"], self.root)
        git(["config", "user.name", "Test"], self.root)
        (self.root / "README.md").write_text("doc\n")
        git(["add", "-A"], self.root)
        git(["commit", "-q", "-m", "initial"], self.root)
        self.tasks_dir = Path(self.scratch.name) / "tasks"
        self.guard_dir = Path(self.scratch.name) / "guard"
        self.env = patch.dict(os.environ, {"FSA_TASKS_DIR": str(self.tasks_dir), "FSA_STOP_GUARD_DIR": str(self.guard_dir),
                                            "CODEX_THREAD_ID": SESSION})
        self.env.start()
        self.addCleanup(self.env.stop)

    def events(self):
        return coordination_log.read(str(self.root))["events"]

    def report_file(self, body="Report body: the thing is done.\n", name="report.md"):
        path = Path(self.scratch.name) / name
        path.write_text(body)
        return path

    def call(self, action, *args, session=SESSION):
        argv = ["report", "--root", str(self.root), "--session", session, action, *args]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(argv), 0)
        return output.getvalue()

    def call_json(self, action, *args, session=SESSION):
        text = self.call(action, *args, session=session)
        lines = [line for line in text.splitlines() if line.strip()]
        json_line = next(line for line in lines if line.startswith("{"))
        return json.loads(json_line)

    def call_fail(self, action, *args, session=SESSION):
        argv = ["report", "--root", str(self.root), "--session", session, action, *args]
        error = io.StringIO()
        with contextlib.redirect_stderr(error), self.assertRaises(SystemExit):
            tasks.main(argv)
        return error.getvalue()

    def save(self, body="Report body: the thing is done.\n", request=None, rows=None, session=SESSION, name="report.md"):
        path = self.report_file(body, name=name)
        argv = ["report", "--root", str(self.root), "--session", session, "--file", str(path), "save"]
        if request:
            argv += ["--request", request]
        if rows:
            argv += ["--rows", rows]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(argv), 0)
        text = output.getvalue()
        lines = [line for line in text.splitlines() if line.strip()]
        json_line = next(line for line in lines if line.startswith("{"))
        return json.loads(json_line)

    def save_text(self, body="Report body: the thing is done.\n", name="report.md"):
        path = self.report_file(body, name=name)
        argv = ["report", "--root", str(self.root), "--session", SESSION, "--file", str(path), "save"]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(argv), 0)
        return output.getvalue()


class SaveTests(ResultOutboxTestCase):
    def test_save_copies_file_sets_mode_and_appends_prepared(self):
        result = self.save(request="R1", rows="GEN1,GEN2")
        self.assertEqual(result["id"], "O1")
        events = self.events()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["type"], "report.prepared")
        self.assertEqual(event["id"], "O1")
        self.assertEqual(event["request"], "R1")
        self.assertEqual(event["rows"], ["GEN1", "GEN2"])
        body = "Report body: the thing is done.\n".encode()
        self.assertEqual(event["sha256"], hashlib.sha256(body).hexdigest())
        outbox = coordination_log._coordination_dir() / f"{coordination_log._key(str(self.root))}.outbox" / "O1.md"
        self.assertTrue(outbox.is_file())
        self.assertEqual(stat.S_IMODE(outbox.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(outbox.parent.stat().st_mode), 0o700)
        self.assertEqual(outbox.read_text(), "Report body: the thing is done.\n")

    def test_save_prints_marker_line(self):
        text = self.save_text()
        self.assertIn("[report O1]", text.splitlines())

    def test_saving_same_sha256_twice_returns_existing_id_and_appends_nothing(self):
        first = self.save()
        second = self.save(name="report-copy.md")
        self.assertEqual(first["id"], second["id"])
        prepared = [e for e in self.events() if e["type"] == "report.prepared"]
        self.assertEqual(len(prepared), 1)

    def test_different_content_gets_a_new_id(self):
        first = self.save(body="First report.\n")
        second = self.save(body="Second report.\n", name="other.md")
        self.assertNotEqual(first["id"], second["id"])

    def test_resaving_same_content_prints_marker_and_restores_a_missing_outbox_file(self):
        self.save(body="Reused report.\n")
        outbox = result_outbox._report_path(str(self.root), "O1")
        outbox.unlink()
        before = self.events()
        text = self.save_text(body="Reused report.\n", name="again.md")
        self.assertIn("[report O1]", text.splitlines())
        self.assertTrue(outbox.is_file())
        self.assertEqual(stat.S_IMODE(outbox.stat().st_mode), 0o600)
        self.assertEqual(outbox.read_text(), "Reused report.\n")
        self.assertEqual(self.events(), before)

    def test_outbox_dir_and_file_modes_under_a_permissive_umask(self):
        old_umask = os.umask(0o022)
        try:
            self.save(body="Permissive umask report.\n")
        finally:
            os.umask(old_umask)
        outbox = result_outbox._report_path(str(self.root), "O1")
        self.assertEqual(stat.S_IMODE(outbox.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(outbox.parent.stat().st_mode), 0o700)

    def test_save_corrects_an_existing_outbox_dir_with_the_wrong_mode(self):
        directory = result_outbox._outbox_dir(str(self.root))
        directory.mkdir(parents=True, exist_ok=True)
        os.chmod(directory, 0o755)
        self.save(body="Fixes the directory mode.\n")
        self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)

    def test_read_paths_create_no_outbox_directory(self):
        directory = result_outbox._outbox_dir(str(self.root))
        self.assertFalse(directory.exists())
        self.assertEqual(result_outbox._read_body(str(self.root), "O1"), "")
        self.assertIsNone(result_outbox.session_start_line(str(self.root)))
        self.assertEqual(result_outbox.cmd_list(None, str(self.root)), {"reports": []})
        self.assertFalse(directory.exists())


class StopEmissionTests(ResultOutboxTestCase):
    def test_marker_and_body_in_final_reply_is_emitted(self):
        self.save(body="The feature ships today.\n")
        path = result_outbox._report_path(str(self.root), "O1")
        message = f"Summary.\n\n[report O1]\n{path.read_text()}"
        result_outbox.record_emission(str(self.root), SESSION, message, [])
        events = [e for e in self.events() if e["type"] in ("report.emitted", "report.uncertain")]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "report.emitted")
        self.assertEqual(events[0]["evidence"], "final_reply")

    def test_marker_without_body_is_uncertain_marker_only(self):
        self.save(body="The feature ships today.\n")
        result_outbox.record_emission(str(self.root), SESSION, "Done: [report O1]", [])
        events = [e for e in self.events() if e["type"] in ("report.emitted", "report.uncertain")]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "report.uncertain")
        self.assertEqual(events[0]["evidence"], "marker_only")

    def test_marker_only_in_earlier_turn_text_is_uncertain_mid_turn(self):
        self.save(body="The feature ships today.\n")
        result_outbox.record_emission(str(self.root), SESSION, "No marker here.", ["[report O1] posted earlier"])
        events = [e for e in self.events() if e["type"] in ("report.emitted", "report.uncertain")]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "report.uncertain")
        self.assertEqual(events[0]["evidence"], "mid_turn_text")

    def test_body_only_in_earlier_turn_text_is_uncertain_mid_turn(self):
        self.save(body="The feature ships today.\n")
        result_outbox.record_emission(str(self.root), SESSION, "No marker here.", ["The  feature   ships today."])
        events = [e for e in self.events() if e["type"] in ("report.emitted", "report.uncertain")]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["evidence"], "mid_turn_text")

    def test_no_marker_and_no_body_anywhere_records_nothing(self):
        self.save(body="The feature ships today.\n")
        result_outbox.record_emission(str(self.root), SESSION, "Just a status update.", ["Also unrelated."])
        self.assertEqual([e for e in self.events() if e["type"] in ("report.emitted", "report.uncertain")], [])

    def test_same_id_evidence_and_session_recorded_once(self):
        self.save(body="The feature ships today.\n")
        result_outbox.record_emission(str(self.root), SESSION, "Done: [report O1]", [])
        result_outbox.record_emission(str(self.root), SESSION, "Done: [report O1]", [])
        events = [e for e in self.events() if e["type"] in ("report.emitted", "report.uncertain")]
        self.assertEqual(len(events), 1)

    def test_no_received_read_delivered_or_acknowledged_event_or_field_exists(self):
        self.save(body="The feature ships today.\n")
        path = result_outbox._report_path(str(self.root), "O1")
        result_outbox.record_emission(str(self.root), SESSION, f"[report O1]\n{path.read_text()}", [])
        for event in self.events():
            self.assertNotIn(event["type"], ("report.received", "report.read", "report.delivered", "report.acknowledged"))
            for key in event:
                self.assertNotIn(key, ("received", "read", "delivered", "acknowledged"))

    def test_marker_with_missing_report_file_is_uncertain_body_unavailable(self):
        self.save(body="The feature ships today.\n")
        result_outbox._report_path(str(self.root), "O1").unlink()
        result_outbox.record_emission(str(self.root), SESSION, "Done: [report O1]", [])
        events = [e for e in self.events() if e["type"] in ("report.emitted", "report.uncertain")]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "report.uncertain")
        self.assertEqual(events[0]["evidence"], "body_unavailable")

    def test_record_emission_never_raises_on_storage_failure(self):
        self.save()
        blocked = Path(self.scratch.name) / "blocked-state"
        blocked.write_text("not a directory")
        with patch.dict(os.environ, {"FSA_TASKS_DIR": str(blocked)}):
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                result_outbox.record_emission(str(self.root), SESSION, "[report O1]", [])
            self.assertTrue(buffer.getvalue())


class StopGuardHoldTests(ResultOutboxTestCase):
    def test_decide_holds_while_prepared_report_has_no_evidence(self):
        self.save()
        reason = stop_guard.decide(SESSION, str(self.root), "", "claude")
        self.assertIn("include report O1 in the final reply", reason)
        self.assertIn("fsa-task report show O1", reason)

    def test_decide_falls_through_once_uncertain(self):
        self.save(body="The feature ships today.\n")
        result_outbox.record_emission(str(self.root), SESSION, "Done: [report O1]", [])
        self.assertIsNone(stop_guard.decide(SESSION, str(self.root), "", "claude"))

    def test_decide_falls_through_once_emitted(self):
        self.save(body="The feature ships today.\n")
        path = result_outbox._report_path(str(self.root), "O1")
        result_outbox.record_emission(str(self.root), SESSION, f"[report O1]\n{path.read_text()}", [])
        self.assertIsNone(stop_guard.decide(SESSION, str(self.root), "", "claude"))

    def test_decide_obeys_max_blocks(self):
        self.save()
        for _ in range(stop_guard.MAX_BLOCKS):
            reason = stop_guard.decide(SESSION, str(self.root), "", "claude")
            self.assertIsNotNone(reason)
        self.assertIsNone(stop_guard.decide(SESSION, str(self.root), "", "claude"))


class CliTests(ResultOutboxTestCase):
    def test_list_shows_id_state_request_rows(self):
        self.save(request="R1", rows="GEN1")
        listed = self.call_json("list")
        self.assertEqual(listed["reports"], [{"id": "O1", "state": "prepared", "request": "R1", "rows": ["GEN1"]}])

    def test_show_prints_the_saved_file(self):
        self.save(body="The feature ships today.\n")
        text = self.call("show", "--id", "O1")
        self.assertIn("The feature ships today.", text)

    def test_show_prefixes_repeat_once_an_evidence_event_exists(self):
        self.save(body="The feature ships today.\n")
        result_outbox.record_emission(str(self.root), SESSION, "Done: [report O1]", [])
        text = self.call("show", "--id", "O1")
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith("REPEAT of O1 (first emitted"))
        self.assertIn("delivery unconfirmed", lines[0])

    def test_list_reports_missing_outbox_file_without_crashing(self):
        self.save()
        result_outbox._report_path(str(self.root), "O1").unlink()
        listed = self.call_json("list")
        self.assertEqual(listed["reports"][0]["state"], "missing_file")

    def test_show_and_list_append_nothing(self):
        self.save()
        before = self.events()
        self.call("list")
        self.call("show", "--id", "O1")
        self.assertEqual(self.events(), before)

    def test_unknown_id_exits_nonzero_with_one_line_error(self):
        error = self.call_fail("show", "--id", "O999")
        self.assertIn("Unknown report id: O999", error)


class HandoverTests(ResultOutboxTestCase):
    def test_session_start_lists_prepared_and_uncertain_reports(self):
        self.save(body="The feature ships today.\n", request="R1")
        line = result_outbox.session_start_line(str(self.root))
        self.assertIn("O1", line)
        self.assertIn("prepared", line)
        self.assertIn("The feature ships today.", line)

    def test_save_in_a_new_session_for_the_same_content_returns_the_old_id(self):
        first = self.save(session="session-a")
        second = self.save(session="session-b", name="resaved.md")
        self.assertEqual(first["id"], second["id"])
        prepared = [e for e in self.events() if e["type"] == "report.prepared"]
        self.assertEqual(len(prepared), 1)
        self.assertEqual(prepared[0]["session"], "session-a")


if __name__ == "__main__":
    unittest.main()
