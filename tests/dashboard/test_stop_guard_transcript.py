"""fsa-stop-guard transcript parsing: turn detection, last-reply scan-back and malformed lines."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "plugins/fullstack-agents/scripts/fsa-stop-guard"

_loader = SourceFileLoader("fsa_stop_guard_transcript_test", str(SCRIPT))
guard = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_stop_guard_transcript_test", _loader))
_loader.exec_module(guard)


def assistant_text(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def assistant_tool_use():
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {}}]}}


def user_tool_result():
    return {"type": "user", "message": {"content": [{"type": "tool_result", "content": "result data"}]}}


def user_prompt(text):
    return {"type": "user", "message": {"content": text}}


def write_transcript(entries):
    path = Path(tempfile.mkstemp(prefix="fsa-transcript-")[1])
    path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n")
    return path


class AssistantTextsTests(unittest.TestCase):
    def test_tool_result_does_not_reset_but_genuine_prompt_does(self):
        path = write_transcript([assistant_text("Text A"), assistant_tool_use(), user_tool_result(),
                                  assistant_text("Text B")])
        self.assertEqual(guard._assistant_texts(str(path)), ["Text A", "Text B"])

        path2 = write_transcript([assistant_text("Text A"), assistant_tool_use(), user_tool_result(),
                                   assistant_text("Text B"), user_prompt("new prompt"), assistant_text("Text C")])
        self.assertEqual(guard._assistant_texts(str(path2)), ["Text C"])


class LastReplyTests(unittest.TestCase):
    def test_scans_backward_past_user_entries_to_the_last_assistant_text(self):
        path = write_transcript([assistant_text("Earlier text"), user_tool_result(), assistant_tool_use()])
        self.assertEqual(guard.last_reply(str(path)), "Earlier text")


class MalformedLineTests(unittest.TestCase):
    def test_non_object_json_lines_are_skipped_without_raising(self):
        lines = ["[1, 2, 3]", "42", json.dumps(assistant_text("Text A"))]
        path = Path(tempfile.mkstemp(prefix="fsa-transcript-")[1])
        path.write_text("\n".join(lines) + "\n")
        self.assertEqual(guard._assistant_texts(str(path)), ["Text A"])
        self.assertEqual(guard.last_reply(str(path)), "Text A")


class EarlierTextsEvidenceTests(unittest.TestCase):
    def run_stop(self, transcript, last_assistant_message):
        hook = {"session_id": "s1", "cwd": "/tmp/repo", "transcript_path": str(transcript),
                "last_assistant_message": last_assistant_message}
        with patch.object(guard, "result_outbox") as outbox, patch.object(guard, "stop_guard") as stop_guard_mock:
            stop_guard_mock.decide.return_value = None
            with patch("sys.stdin", io.StringIO(json.dumps(hook))), patch("sys.argv", ["fsa-stop-guard", "stop"]):
                with contextlib.redirect_stdout(io.StringIO()):
                    guard.main()
        return outbox.record_emission.call_args.args[-1]

    def test_final_message_dropped_once_transcript_has_flushed_it(self):
        path = write_transcript([assistant_text("Text A"), assistant_text("Text B")])
        earlier = self.run_stop(path, "Text B")
        self.assertEqual(earlier, ["Text A"])

    def test_nothing_dropped_when_transcript_has_not_flushed_the_final_message(self):
        path = write_transcript([assistant_text("Text A"), assistant_text("Text B")])
        earlier = self.run_stop(path, "Not yet in the transcript")
        self.assertEqual(earlier, ["Text A", "Text B"])


if __name__ == "__main__":
    unittest.main()
