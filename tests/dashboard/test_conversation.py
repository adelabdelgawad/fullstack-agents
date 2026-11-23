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

    def test_an_agent_team_members_prompt_is_the_text_inside_the_teammate_tag(self):
        messages = self.read([
            user('<teammate-message teammate_id="team-lead" summary="s">Draw the phone screens\n\nDesign only</teammate-message>'),
            assistant({"type": "text", "text": "Done."}),
        ])
        self.assertEqual(messages[0], {"role": "user", "text": "Draw the phone screens\n\nDesign only",
                                       "at": messages[0]["at"]})

    def test_a_long_message_keeps_its_start_and_its_end(self):
        brief = "GOAL: fix it\n" + "x" * 9000 + "\nEND"
        report = "Summary first. " + "y" * 9000 + " last line"
        messages = self.read([user(brief), assistant({"type": "text", "text": report})])
        self.assertTrue(messages[0]["text"].startswith("GOAL: fix it"))
        self.assertTrue(messages[0]["text"].endswith("END"))
        self.assertTrue(messages[1]["text"].startswith("Summary first."))
        self.assertTrue(messages[1]["text"].endswith("last line"))

    def test_an_implementer_run_reads_as_brief_then_its_work_then_its_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs, rid = Path(tmp), "implement-20261123-084530-1"
            brief = runs / "brief.md"
            brief.write_text("GOAL: repair the swipe track")
            (runs / f"{rid}.meta.json").write_text(json.dumps({"engine": "claude", "brief": str(brief),
                                                                "started": "2026-11-23T08:45:31Z"}))
            (runs / f"{rid}.log").write_text("\n".join(json.dumps(row) for row in [
                user("ROLE: you are the implementer ... the whole prompt"),
                assistant({"type": "text", "text": "Reading the track."}, {"type": "tool_use", "name": "Read", "input": {}}),
            ]) + "\n")
            working = dash.run_conversation(runs, rid)
            self.assertEqual([m["role"] for m in working], ["user", "assistant", "tool"])
            self.assertEqual(working[0]["text"], "GOAL: repair the swipe track")
            (runs / f"{rid}.last.txt").write_text(json.dumps({"summary": "Repaired.", "files": ["a.tsx"], "tests": ["PASS: tsc"]}))
            done = dash.run_conversation(runs, rid)
            self.assertTrue(done[-1]["report"])
            self.assertEqual(done[-1]["text"], "Repaired.\n\n**Files**\n- a.tsx\n\n**Checks**\n- PASS: tsc")


class SessionNameTests(unittest.TestCase):
    def test_claude_session_name_wins_in_rename_then_shown_then_generated_order(self):
        self.assertEqual(list(dash.TITLE_KEYS), ["custom-title", "agent-name", "ai-title"])


if __name__ == "__main__":
    unittest.main()
