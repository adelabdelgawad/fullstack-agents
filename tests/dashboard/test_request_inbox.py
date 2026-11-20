"""Durable request inbox: capture, `fsa-task request`, and the stop guard's unclassified hold; see docs/TASK_LIFECYCLE_DESIGN.md §15."""
import contextlib
import hashlib
import importlib.util
import io
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "plugins/fullstack-agents/scripts/lib"
sys.path.insert(0, str(LIB))
import coordination_log
import request_inbox
import stop_guard

SPEC = importlib.util.spec_from_file_location("task_tracking_request_test", LIB / "task_tracking.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)


def git(args, cwd):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


SESSION = "req-session"


def _capture_distinct(tasks_dir, guard_dir, root, worker, count):
    os.environ["FSA_TASKS_DIR"] = tasks_dir
    os.environ["FSA_STOP_GUARD_DIR"] = guard_dir
    for index in range(count):
        request_inbox.capture({"session_id": f"worker-{worker}", "cwd": root,
                                "prompt": f"distinct prompt {worker}-{index}", "prompt_id": f"{worker}-{index}"})


def _capture_same(tasks_dir, guard_dir, root, session, host_id, text, barrier):
    os.environ["FSA_TASKS_DIR"] = tasks_dir
    os.environ["FSA_STOP_GUARD_DIR"] = guard_dir
    barrier.wait()
    request_inbox.capture({"session_id": session, "cwd": root, "prompt": text, "prompt_id": host_id})


class RequestInboxTestCase(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-requests-")
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

    def hook(self, prompt, host_id="h1", session=SESSION):
        return {"session_id": session, "cwd": str(self.root), "prompt": prompt, "prompt_id": host_id}

    def events(self):
        return coordination_log.read(str(self.root))["events"]

    def call(self, action, *args):
        argv = ["request", "--root", str(self.root), "--session", SESSION, action, *args]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(argv), 0)
        text = output.getvalue()
        return json.loads(text) if text.strip() else None

    def call_fail(self, action, *args):
        argv = ["request", "--root", str(self.root), "--session", SESSION, action, *args]
        error = io.StringIO()
        with contextlib.redirect_stderr(error), self.assertRaises(SystemExit):
            tasks.main(argv)
        return error.getvalue()


class CaptureTests(RequestInboxTestCase):
    def test_genuine_prompt_is_captured_with_expected_fields(self):
        rid = request_inbox.capture(self.hook("please fix the login bug", host_id="h1"))
        self.assertEqual(rid, "R1")
        events = self.events()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["type"], "request.received")
        self.assertEqual(event["id"], "R1")
        self.assertEqual(event["text"], "please fix the login bug")
        self.assertEqual(event["text_sha256"], hashlib.sha256(b"please fix the login bug").hexdigest())
        self.assertEqual(event["host_id"], "h1")
        self.assertIsNone(event["origin"])

    def test_notification_is_not_captured(self):
        rid = request_inbox.capture(self.hook("<task-notification>done</task-notification>", host_id=None))
        self.assertIsNone(rid)
        self.assertEqual(self.events(), [])

    def test_same_session_and_host_id_and_text_twice_is_one_request(self):
        first = request_inbox.capture(self.hook("fix the bug", host_id="h1"))
        second = request_inbox.capture(self.hook("fix the bug", host_id="h1"))
        self.assertEqual(first, second)
        types = [e["type"] for e in self.events()]
        self.assertEqual(types, ["request.received", "request.duplicate_delivery"])

    def test_same_host_id_different_text_is_a_new_mid_turn_request(self):
        first = request_inbox.capture(self.hook("fix the bug", host_id="h1"))
        second = request_inbox.capture(self.hook("actually, also check the signup flow", host_id="h1"))
        self.assertNotEqual(first, second)
        received = [e for e in self.events() if e["type"] == "request.received"]
        self.assertEqual(len(received), 2)
        self.assertNotIn("mid_turn", received[0])
        self.assertEqual(received[1]["host_id"], "h1")
        self.assertTrue(received[1]["mid_turn"])

    def test_no_host_id_same_text_within_two_seconds_is_one_request(self):
        first = request_inbox.capture(self.hook("fix the bug", host_id=None))
        second = request_inbox.capture(self.hook("fix the bug", host_id=None))
        self.assertEqual(first, second)
        types = [e["type"] for e in self.events()]
        self.assertEqual(types, ["request.received", "request.duplicate_delivery"])

    def test_no_host_id_same_text_after_window_is_two_requests(self):
        first = request_inbox.capture(self.hook("fix the bug", host_id=None))
        time.sleep(2.1)
        second = request_inbox.capture(self.hook("fix the bug", host_id=None))
        self.assertNotEqual(first, second)
        received = [e for e in self.events() if e["type"] == "request.received"]
        self.assertEqual(len(received), 2)

    def test_different_host_id_same_text_is_two_requests(self):
        first = request_inbox.capture(self.hook("fix the bug", host_id="h1"))
        second = request_inbox.capture(self.hook("fix the bug", host_id="h2"))
        self.assertNotEqual(first, second)
        received = [e for e in self.events() if e["type"] == "request.received"]
        self.assertEqual(len(received), 2)

    def test_capture_failure_never_raises_and_writes_one_stderr_line(self):
        blocked = Path(self.scratch.name) / "blocked-state"
        blocked.write_text("not a directory")
        with patch.dict(os.environ, {"FSA_TASKS_DIR": str(blocked)}):
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                result = request_inbox.capture(self.hook("fix the bug"))
            self.assertIsNone(result)
            self.assertEqual(len(buffer.getvalue().rstrip("\n").splitlines()), 1)


class CaptureRaceTests(RequestInboxTestCase):
    def test_two_processes_capturing_fifty_distinct_prompts_yield_fifty_distinct_ids(self):
        processes = [multiprocessing.Process(target=_capture_distinct,
                     args=(str(self.tasks_dir), str(self.guard_dir), str(self.root), worker, 25))
                     for worker in range(2)]
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=60)
            self.assertEqual(process.exitcode, 0)
        received = [e for e in self.events() if e["type"] == "request.received"]
        self.assertEqual(len(received), 50)
        self.assertEqual(len({e["id"] for e in received}), 50)

    def test_two_processes_delivering_the_same_prompt_id_at_once_yield_one_received(self):
        barrier = multiprocessing.Barrier(2)
        processes = [multiprocessing.Process(target=_capture_same,
                     args=(str(self.tasks_dir), str(self.guard_dir), str(self.root), SESSION, "dup-1",
                           "same text", barrier))
                     for _ in range(2)]
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=60)
            self.assertEqual(process.exitcode, 0)
        received = [e for e in self.events() if e["type"] == "request.received"]
        duplicates = [e for e in self.events() if e["type"] == "request.duplicate_delivery"]
        self.assertEqual(len(received), 1)
        self.assertEqual(len(duplicates), 1)


class RequestCliTests(RequestInboxTestCase):
    def test_list_and_show_reflect_a_captured_request(self):
        rid = request_inbox.capture(self.hook("please fix the login bug"))
        listed = self.call("list")
        self.assertEqual(listed["requests"], [{"id": rid, "class": "unclassified", "execution": "none",
                                                 "open": True, "preview": "please fix the login bug"}])
        shown = self.call("show", "--id", rid)
        self.assertEqual(shown["class"], "unclassified")
        self.assertEqual(shown["text"], "please fix the login bug")
        self.assertTrue(shown["open"])

    def test_classify_sets_class_and_rows(self):
        rid = request_inbox.capture(self.hook("that was wrong, fix GEN1"))
        result = self.call("classify", "--id", rid, "--as", "correction", "--rows", "GEN1", "--note", "typo")
        self.assertEqual(result, {"id": rid, "as": "correction"})
        shown = self.call("show", "--id", rid)
        self.assertEqual(shown["class"], "correction")
        self.assertEqual(shown["rows"], ["GEN1"])
        self.assertEqual(shown["note"], "typo")

    def test_classify_ambiguous_keeps_the_request_open(self):
        rid = request_inbox.capture(self.hook("not sure what this means"))
        self.call("classify", "--id", rid, "--as", "ambiguous", "--note", "unclear ask")
        shown = self.call("show", "--id", rid)
        self.assertEqual(shown["class"], "ambiguous")
        self.assertEqual(shown["note"], "unclear ask")
        self.assertTrue(shown["open"])
        listed = self.call("list")
        self.assertEqual(listed["requests"][0]["class"], "ambiguous")
        self.assertTrue(listed["requests"][0]["open"])

    def test_oldest_unclassified_ignores_ambiguous(self):
        request_inbox.capture(self.hook("not sure what this means", host_id="h1"))
        self.call("classify", "--id", "R1", "--as", "ambiguous", "--note", "unclear")
        self.assertIsNone(request_inbox.oldest_unclassified(str(self.root), SESSION))

    def test_later_classify_replaces_ambiguous(self):
        rid = request_inbox.capture(self.hook("not sure what this means"))
        self.call("classify", "--id", rid, "--as", "ambiguous", "--note", "unclear")
        self.call("classify", "--id", rid, "--as", "correction", "--rows", "GEN1", "--note", "got it")
        shown = self.call("show", "--id", rid)
        self.assertEqual(shown["class"], "correction")
        self.assertEqual(shown["rows"], ["GEN1"])
        self.assertFalse(shown["open"])

    def test_execution_state_queued(self):
        rid = request_inbox.capture(self.hook("also do this new work"))
        self.call("classify", "--id", rid, "--as", "queued")
        self.assertEqual(self.call("show", "--id", rid)["execution"], "queued")

    def test_execution_state_active_when_linked(self):
        rid = request_inbox.capture(self.hook("also do FSA1"))
        self.call("link", "--id", rid, "--rows", "FSA1")
        self.assertEqual(self.call("show", "--id", rid)["execution"], "active")

    def test_done_dropped_requires_reason(self):
        rid = request_inbox.capture(self.hook("do the thing"))
        error = self.call_fail("done", "--id", rid, "--dropped")
        self.assertIn("--dropped requires --reason", error)

    def test_done_dropped_with_reason_sets_execution_dropped(self):
        rid = request_inbox.capture(self.hook("do the thing"))
        result = self.call("done", "--id", rid, "--dropped", "--reason", "superseded by FSA2")
        self.assertEqual(result, {"id": rid, "execution": "dropped"})
        self.assertEqual(self.call("show", "--id", rid)["execution"], "dropped")

    def test_link_records_rows(self):
        rid = request_inbox.capture(self.hook("also do FSA1"))
        self.call("link", "--id", rid, "--rows", "FSA1,FSA2")
        shown = self.call("show", "--id", rid)
        self.assertEqual(shown["linked_rows"], ["FSA1", "FSA2"])

    def test_done_sets_execution_done(self):
        rid = request_inbox.capture(self.hook("do the thing"))
        result = self.call("done", "--id", rid)
        self.assertEqual(result, {"id": rid, "execution": "done"})
        self.assertEqual(self.call("show", "--id", rid)["execution"], "done")

    def test_unknown_id_exits_nonzero_with_one_line_error(self):
        error = self.call_fail("show", "--id", "R999")
        self.assertIn("Unknown request id: R999", error)

    def test_unknown_class_exits_nonzero_with_one_line_error(self):
        rid = request_inbox.capture(self.hook("do the thing"))
        error = self.call_fail("classify", "--id", rid, "--as", "nonsense")
        self.assertIn("Unknown classification: nonsense", error)

    def test_open_requests_lists_unclassified_and_ambiguous_oldest_first(self):
        rid1 = request_inbox.capture(self.hook("investigate the build", host_id="h1"))
        rid2 = request_inbox.capture(self.hook("not sure what this means", host_id="h2"))
        self.call("classify", "--id", rid2, "--as", "ambiguous", "--note", "unclear")
        rid3 = request_inbox.capture(self.hook("also do this new work", host_id="h3"))
        self.call("classify", "--id", rid3, "--as", "queued")
        open_requests = request_inbox.open_requests(str(self.root))
        self.assertEqual([r["id"] for r in open_requests], [rid1, rid2])

    def test_ack_capture_failure_clears_the_marker(self):
        coordination_log.mark_capture_failed(str(self.root))
        self.assertTrue(coordination_log.capture_failed(str(self.root)))
        self.call("list", "--ack-capture-failure")
        self.assertFalse(coordination_log.capture_failed(str(self.root)))


class StopGuardHoldTests(RequestInboxTestCase):
    def test_decide_blocks_on_oldest_unclassified_request_even_when_paused(self):
        stop_guard.record_prompt(self.hook("stop everything", host_id="h1"))  # sets legacy paused=True
        reason = stop_guard.decide(SESSION, str(self.root), "", "claude")
        self.assertIn("classify R1 with `fsa-task request classify`", reason)

    def test_decide_falls_through_once_classified(self):
        rid = request_inbox.capture(self.hook("please fix the bug", host_id="h1"))
        self.call("classify", "--id", rid, "--as", "correction")
        self.assertIsNone(stop_guard.decide(SESSION, str(self.root), "", "claude"))

    def test_decide_obeys_max_blocks(self):
        request_inbox.capture(self.hook("please fix the bug", host_id="h1"))
        for _ in range(stop_guard.MAX_BLOCKS):
            reason = stop_guard.decide(SESSION, str(self.root), "", "claude")
            self.assertIsNotNone(reason)
        self.assertIsNone(stop_guard.decide(SESSION, str(self.root), "", "claude"))

    def test_fsa_stop_guard_off_bypasses_the_hold(self):
        request_inbox.capture(self.hook("please fix the bug", host_id="h1"))
        with patch.dict(os.environ, {"FSA_STOP_GUARD": "off"}):
            self.assertIsNone(stop_guard.decide(SESSION, str(self.root), "", "claude"))


if __name__ == "__main__":
    unittest.main()
