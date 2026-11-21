"""The Office chat console reads a session's conversation: prompts and replies only, with line breaks kept."""
import importlib.util
import json
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("fsa_dashboard_conversation", str(REPO / "plugins/fullstack-agents/scripts/fsa-dashboard"))
dash = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_dashboard_conversation", _loader))
_loader.exec_module(dash)


def user(content, **extra):
    return {"type": "user", "timestamp": "2026-11-21T10:00:00Z", "message": {"role": "user", "content": content}, **extra}


def assistant(*blocks):
    return {"type": "assistant", "timestamp": "2026-11-21T10:00:05Z", "message": {"role": "assistant", "content": list(blocks)}}


class ConversationTests(unittest.TestCase):
    def read(self, rows):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as handle:
            handle.write("\n".join(json.dumps(row) for row in rows) + "\n")
        try:
            return dash.conversation(handle.name)
        finally:
            Path(handle.name).unlink()

    def test_prompts_and_replies_keep_line_breaks_and_skip_tools_and_meta(self):
        messages = self.read([
            user("Fix the login page\n\n- keep the layout"),
            user("Base directory for this skill: /x\n# Debug", isMeta=True),
            assistant({"type": "text", "text": "Looking at it."}, {"type": "tool_use", "name": "Read", "input": {}}),
            user([{"type": "tool_result", "tool_use_id": "t", "content": "file text"}]),
            assistant({"type": "text", "text": "Fixed.\n\n- tests pass"}),
            user("<system-reminder>noise</system-reminder>"),
        ])
        self.assertEqual([m["role"] for m in messages], ["user", "assistant", "tool", "assistant"])
        self.assertEqual(messages[0]["text"], "Fix the login page\n\n- keep the layout")
        self.assertEqual(messages[1]["text"], "Looking at it.")
        self.assertEqual(messages[2]["text"], "Read")
        self.assertEqual(messages[3]["text"], "Fixed.\n\n- tests pass")

    def test_consecutive_tool_steps_are_grouped_and_capped(self):
        steps = [assistant({"type": "tool_use", "name": "Bash", "input": {"description": f"step {i}"}})
                 for i in range(dash.CONVERSATION_TOOLS + 3)]
        [group] = self.read(steps)
        self.assertEqual(group["role"], "tool")
        lines = group["text"].split("\n")
        self.assertEqual(len(lines), dash.CONVERSATION_TOOLS)
        self.assertEqual(lines[-1], f"Bash: step {dash.CONVERSATION_TOOLS + 2}")

    def test_only_the_latest_messages_are_kept(self):
        rows = []
        for index in range(dash.CONVERSATION_MAX + 5):
            rows += [user(f"question {index}"), assistant({"type": "text", "text": f"answer {index}"})]
        messages = self.read(rows)
        self.assertEqual(len(messages), dash.CONVERSATION_MAX)
        self.assertEqual(messages[-1]["text"], f"answer {dash.CONVERSATION_MAX + 4}")


if __name__ == "__main__":
    unittest.main()
