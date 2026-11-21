"""A session inside a long foreground tool call is working, not stalled."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("fsa_dashboard_pending_tool", str(REPO / "plugins/fullstack-agents/scripts/fsa-dashboard"))
dash = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_dashboard_pending_tool", _loader))
_loader.exec_module(dash)


def stamp(minutes_ago):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def state_after(tool, minutes_ago, answered=False):
    rows = [
        {"type": "user", "timestamp": stamp(minutes_ago + 1), "message": {"role": "user", "content": "run clippy"}},
        {"type": "assistant", "timestamp": stamp(minutes_ago), "message": {"role": "assistant", "stop_reason": "tool_use",
         "content": [{"type": "tool_use", "id": "toolu_1", "name": tool, "input": {"description": "Clippy"}}]}},
    ]
    if answered:
        rows.append({"type": "user", "timestamp": stamp(minutes_ago), "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_1", "content": "ok"}]}})
    with tempfile.TemporaryDirectory() as scratch:
        path = Path(scratch) / "session.jsonl"
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        return dash.read_session(path, time.time(), None, {}, {})


class PendingToolTests(unittest.TestCase):
    def test_a_long_foreground_command_keeps_the_session_working(self):
        session = state_after("Bash", 8)
        self.assertEqual((session["state"], session["action_running"]), ("working", True))

    def test_a_tool_call_pending_past_the_limit_is_a_stall(self):
        self.assertEqual(state_after("Bash", dash.PENDING_TOOL_S / 60 + 5)["state"], "quiet")

    def test_a_pending_question_is_not_work(self):
        self.assertEqual(state_after("AskUserQuestion", 8)["state"], "quiet")

    def test_without_a_pending_call_silence_is_still_a_stall(self):
        self.assertEqual(state_after("Bash", 8, answered=True)["state"], "quiet")


if __name__ == "__main__":
    unittest.main()
