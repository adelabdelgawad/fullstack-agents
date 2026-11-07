import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/fullstack-agents/scripts/lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import auto_handoff
import context_handoff
import usage
from test_usage import assistant, write_lines

FAKE_HERDR = """#!/usr/bin/env bash
d="$(dirname "$0")"
echo "$*" >> "$d/calls"
case "$2" in
  wait-output) [ -f "$d/card" ] ;;
  read) if [ -f "$d/card" ] && [ ! -f "$d/pressed" ]; then cat "$d/card"; else echo "idle"; fi ;;
  send-text) touch "$d/pressed" ;;
esac
"""


class AutoHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.path = self.dir / "s.jsonl"
        self.hook = {"session_id": "s1", "transcript_path": str(self.path), "tool_use_id": "t1",
                     "tool_input": {"plan": "# HANDOFF RESUME\n\nNext step.\n"}}
        self.env = {"HERDR_PANE_ID": "w1:p1"}
        usage._CACHE.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def warn(self, read=210_000):
        write_lines(self.path, [assistant("m1", read=read)])
        return context_handoff.notice(self.hook, self.dir)

    def test_arms_once_per_handover_call_after_the_notice(self):
        self.assertIsNone(auto_handoff.armed(self.hook, self.dir, self.env))
        self.assertIsNotNone(self.warn())
        self.assertEqual(auto_handoff.armed(self.hook, self.dir, self.env), "w1:p1")
        self.assertIsNone(auto_handoff.armed(self.hook, self.dir, self.env))
        write_lines(self.path, [assistant("m2", read=220_000)])
        self.assertIsNone(context_handoff.notice(self.hook, self.dir))
        self.assertEqual(auto_handoff.armed({**self.hook, "tool_use_id": "t2"}, self.dir, self.env), "w1:p1")

    def test_other_plans_do_not_arm(self):
        self.warn()
        other = {**self.hook, "tool_input": {"plan": "# Refactor the parser\n\n# HANDOFF RESUME\n"}}
        self.assertIsNone(auto_handoff.armed(other, self.dir, self.env))
        self.assertEqual(auto_handoff.armed(self.hook, self.dir, self.env), "w1:p1")

    def test_an_empty_plan_input_reads_this_sessions_plan_file(self):
        plans = self.dir / "plans"
        plans.mkdir()
        (plans / "mine.md").write_text("\n# HANDOFF RESUME\n")
        (plans / "other.md").write_text("# Refactor the parser\n")
        hook = {**self.hook, "tool_input": {}}
        env = {**self.env, "CLAUDE_CONFIG_DIR": str(self.dir)}
        self.warn()
        with open(self.path, "a") as stream:
            stream.write('{"type":"user","slug":"other"}\n{"type":"user","slug":"mine"}\n')
        self.assertEqual(auto_handoff.armed(hook, self.dir, env), "w1:p1")
        with open(self.path, "a") as stream:
            stream.write('{"type":"user","slug":"other"}\n')
        self.assertIsNone(auto_handoff.armed({**hook, "tool_use_id": "t2"}, self.dir, env))

    def test_arms_after_the_notice_when_the_context_shrank_without_compaction(self):
        self.assertIsNotNone(self.warn(read=266_000))
        write_lines(self.path, [assistant("m1", read=266_000), assistant("m2", read=136_000)])
        self.assertIsNone(context_handoff.notice(self.hook, self.dir))
        self.assertEqual(auto_handoff.armed(self.hook, self.dir, self.env), "w1:p1")

    def test_stays_manual_outside_herdr_when_disabled_or_for_subagents(self):
        self.warn()
        self.assertIsNone(auto_handoff.armed(self.hook, self.dir, {}))
        self.assertIsNone(auto_handoff.armed(self.hook, self.dir, {**self.env, "FSA_AUTO_HANDOFF": "off"}))
        self.assertIsNone(auto_handoff.armed({**self.hook, "agent_id": "a1"}, self.dir, self.env))

    def test_stays_manual_below_the_loop_guard_threshold(self):
        os.environ["FSA_HANDOFF_TOKENS"] = "50000"
        self.addCleanup(os.environ.pop, "FSA_HANDOFF_TOKENS")
        self.assertIsNotNone(self.warn(read=60_000))
        self.assertIsNone(auto_handoff.armed(self.hook, self.dir, self.env))

    def plan_edit(self, read=120_000, tool="Edit", mid="m1"):
        write_lines(self.path, [assistant(mid, read=read)])
        with mock.patch.object(context_handoff, "_adopt", lambda sid: "fsa-task adopt X" if sid else None):
            return context_handoff.notice({**self.hook, "tool_name": tool}, self.dir)

    def test_first_edit_on_a_large_context_gives_one_plan_handoff_that_arms(self):
        self.assertIsNone(self.plan_edit(tool="Bash"))
        line = self.plan_edit(mid="m2")
        self.assertTrue(line.startswith("PLAN-HANDOFF:"))
        self.assertIn("fsa-task adopt X", line)
        self.assertIsNone(self.plan_edit(mid="m3"))
        self.assertEqual(auto_handoff.armed(self.hook, self.dir, self.env), "w1:p1")

    def test_no_plan_handoff_without_a_ledger_on_a_small_context_or_when_disabled(self):
        self.assertIsNone(self.plan_edit(read=60_000))
        with mock.patch.object(context_handoff, "_adopt", lambda sid: None):
            write_lines(self.path, [assistant("m2", read=120_000)])
            self.assertIsNone(context_handoff.notice({**self.hook, "tool_name": "Edit"}, self.dir))
        os.environ["FSA_PLAN_HANDOFF_TOKENS"] = "0"
        self.addCleanup(os.environ.pop, "FSA_PLAN_HANDOFF_TOKENS")
        self.assertIsNone(self.plan_edit(mid="m3"))
        self.assertIsNone(auto_handoff.armed(self.hook, self.dir, self.env))

    def watch(self, card=True):
        fake = self.dir / "herdr"
        fake.write_text(FAKE_HERDR)
        fake.chmod(0o755)
        if card:
            (self.dir / "card").write_text("❯ 1. Yes, clear context (9% used) and bypass permissions\n")
        with mock.patch.object(auto_handoff.time, "sleep"):
            result = auto_handoff.watch("w1:p1", self.dir / "log", {"HERDR_BIN_PATH": str(fake)}, "s1", wait_ms=10)
        calls = (self.dir / "calls").read_bytes().decode()
        return result, calls

    def test_presses_enter_on_the_card(self):
        result, calls = self.watch()
        self.assertEqual(result, "approved")
        self.assertIn("pane send-text w1:p1 \r", calls)

    def test_a_missing_card_is_left_alone_and_logged_with_the_screen(self):
        result, calls = self.watch(card=False)
        self.assertEqual(result, "no-card")
        self.assertNotIn("send-text", calls)
        entry = json.loads((self.dir / "log").read_text().splitlines()[-1])
        self.assertEqual((entry["session"], entry["screen"]), ("s1", ["idle"]))


if __name__ == "__main__":
    unittest.main()
