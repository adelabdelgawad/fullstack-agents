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
        self.hook = {"session_id": "s1", "transcript_path": str(self.path)}
        self.env = {"HERDR_PANE_ID": "w1:p1"}
        usage._CACHE.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def warn(self, read=210_000):
        write_lines(self.path, [assistant("m1", read=read)])
        return context_handoff.notice(self.hook, self.dir)

    def test_arms_once_per_cycle_after_the_notice(self):
        self.assertIsNone(auto_handoff.armed(self.hook, self.dir, self.env))
        self.assertIsNotNone(self.warn())
        self.assertEqual(auto_handoff.armed(self.hook, self.dir, self.env), "w1:p1")
        write_lines(self.path, [assistant("m2", read=220_000)])
        self.assertIsNone(context_handoff.notice(self.hook, self.dir))
        self.assertIsNone(auto_handoff.armed(self.hook, self.dir, self.env))

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

    def watch(self, plan_first_line, card=True):
        fake = self.dir / "herdr"
        fake.write_text(FAKE_HERDR)
        fake.chmod(0o755)
        plan = self.dir / "plan.md"
        plan.write_text(f"{plan_first_line}\n\nNext step.\n")
        if card:
            (self.dir / "card").write_text(f"❯ 1. Yes, clear context (9% used) and bypass permissions\n"
                                           f" ctrl+g to edit in Vim · {plan}\n")
        with mock.patch.object(auto_handoff.time, "sleep"):
            result = auto_handoff.watch("w1:p1", self.dir / "log", {"HERDR_BIN_PATH": str(fake)}, wait_ms=10)
        calls = (self.dir / "calls").read_bytes().decode()
        return result, calls

    def test_presses_enter_only_on_a_handover_plan(self):
        result, calls = self.watch("# HANDOFF RESUME")
        self.assertEqual(result, "approved")
        self.assertIn("pane send-text w1:p1 \r", calls)

    def test_other_plans_and_missing_cards_are_left_alone(self):
        result, calls = self.watch("# Refactor the parser")
        self.assertEqual(result, "not-a-handover-plan")
        self.assertNotIn("send-text", calls)
        (self.dir / "card").unlink()
        (self.dir / "calls").unlink()
        result, calls = self.watch("# HANDOFF RESUME", card=False)
        self.assertEqual(result, "no-card")
        self.assertNotIn("send-text", calls)


if __name__ == "__main__":
    unittest.main()
