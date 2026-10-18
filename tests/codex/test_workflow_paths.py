"""P6: the light and full paths are defined once, escalate on stated criteria, and every always-loaded source agrees."""
import re
import unittest

from dispatch_support import SCRIPTS

PLUGIN = SCRIPTS.parent
SKILL = (PLUGIN / "skills/task-flow/SKILL.md").read_text()
LEAD = (PLUGIN / "agents/lead/fullstack-agent.md").read_text()
DOCTRINE = (PLUGIN / "hooks/session-doctrine.md").read_text()


def flat(text):
    return " ".join(text.split())


class WorkflowPathTests(unittest.TestCase):
    def section(self):
        m = re.search(r"## Light path and full path\n(.*?)\n## ", SKILL, re.S)
        self.assertIsNotNone(m)
        return flat(m.group(1))

    def test_light_path_drops_the_orchestration_overhead(self):
        light = self.section()
        for dropped in ("no task ledger", "no `fsa-usage` calls", "no detailed-guide read", "no test-runner",
                        "no manual `team-board` calls"):
            self.assertIn(dropped, light)
        self.assertIn("audit of your own diff still apply", light)

    def test_escalation_criteria_cover_risk_and_coordination(self):
        light = self.section()
        for trigger in ("delegated implementer", "carve-out", "more files than the budget", "migration",
                        "another session working on the same paths", "the user asks for tracking"):
            self.assertIn(trigger, light)

    def test_ledger_usage_and_team_board_rules_apply_to_the_full_path_only(self):
        lead = flat(LEAD)
        self.assertIn("On a full-path task, run the plugin's `scripts/fsa-usage`", lead)
        self.assertIn("On a full-path task, before a reply that ends with the user's turn", lead)
        self.assertIn("when a full-path task ends without a push", lead)
        self.assertIn("For full-path multi-step implementation, create and register", flat(SKILL))
        self.assertIn("on a full-path task", flat(DOCTRINE).lower())

    def test_questions_and_research_skip_task_flow(self):
        self.assertIn("A question or web research that ends in an answer needs no task-flow load", flat(LEAD))


if __name__ == "__main__":
    unittest.main()
