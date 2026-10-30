import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "plugins/fullstack-agents"
sys.path.insert(0, str(PLUGIN / "scripts/lib"))

import deploy_hold

HOOK = PLUGIN / "hooks/deploy-hold"
REGEX = r"deploy-backend\.sh|deploy-frontend\.sh"


class DeployHoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {**os.environ, "CLAUDE_CONFIG_DIR": self.tmp.name, "FSA_TEAM_DEPLOY_REGEX": REGEX}
        self.env.pop("FSA_IMPLEMENTER_RUN", None)

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, mode, payload, env=None):
        payload = {"session_id": "s1", "cwd": self.tmp.name, **payload}
        return subprocess.run(["bash", str(HOOK), mode], input=json.dumps(payload), capture_output=True, text=True,
                              env=env or self.env, timeout=30, check=False)

    def prompt(self, text, sid="s1"):
        return self.run_hook("prompt", {"prompt": text, "session_id": sid})

    def bash(self, command, env=None):
        return self.run_hook("bash", {"tool_input": {"command": command}}, env)

    def test_the_users_own_prompts_set_and_lift_the_hold(self):
        for text in ("no deploy now", "keep it undeployed", "merge and commit but do not do deployment",
                     ("Do not merge application branches, push application commits, restart services, or deploy "
                      "while implementing this skill."), "deploy it later"):
            self.assertEqual(deploy_hold.classify(text), "hold", text)
        for text in ("go ahead and deploy", "push and deploy the backend", "when you finish do deploy",
                     "no, deploy it now", "commit and merge it, then deploy"):
            self.assertEqual(deploy_hold.classify(text), "lift", text)
        for text in ("did you deploy", "why is the deploy slow?", "check the calls of today",
                     "Deploy the frontend. " + "x" * 400):
            self.assertIsNone(deploy_hold.classify(text), text)

    def test_hold_blocks_only_deploy_commands_until_the_user_says_deploy(self):
        self.assertEqual(self.bash("scripts/deploy-backend.sh").returncode, 0)
        out = self.prompt("fix it, merge and commit, no deploy now").stdout
        self.assertIn("Deploy hold", out)
        blocked = self.bash("cd /x && scripts/deploy-backend.sh --yes")
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("Only the user lifts it", blocked.stderr)
        self.assertEqual(self.bash("git push origin main").returncode, 0)
        self.assertIn("Deploy hold", self.prompt("what is the progress").stdout)
        self.assertIn("lifted", self.prompt("push and deploy").stdout)
        self.assertEqual(self.bash("scripts/deploy-backend.sh").returncode, 0)

    def test_gate_off_switch_does_not_bypass_the_hold(self):
        self.prompt("no deploy now")
        self.assertEqual(self.bash("scripts/deploy-frontend.sh", {**self.env, "FSA_TEAM_GATE_OFF": "1"}).returncode, 2)

    def test_hold_belongs_to_the_session_that_was_told(self):
        self.prompt("no deploy now", sid="other")
        self.assertEqual(self.bash("scripts/deploy-frontend.sh").returncode, 0)

    def test_hold_survives_a_clear_context_handover(self):
        self.prompt("no deploy now")
        plans = Path(self.tmp.name) / "plans"
        plans.mkdir()
        plan = plans / "resume.md"
        plan.write_text("# HANDOFF RESUME\nnext: run the tests\n")
        refused = self.run_hook("plan", {"tool_input": {}})
        self.assertEqual(refused.returncode, 2)
        self.assertIn(deploy_hold.MARKER, refused.stderr)
        plan.write_text(f"# HANDOFF RESUME\n{deploy_hold.MARKER}\nnext: run the tests\n")
        os.utime(plan, (time.time(), time.time()))
        self.assertEqual(self.run_hook("plan", {"tool_input": {}}).returncode, 0)
        self.prompt(f"Implement the following plan:\n\n{plan.read_text()}", sid="new")
        self.assertEqual(self.run_hook("bash", {"session_id": "new",
                                                "tool_input": {"command": "scripts/deploy-backend.sh"}}).returncode, 2)

    def test_handover_without_a_hold_is_untouched(self):
        plans = Path(self.tmp.name) / "plans"
        plans.mkdir()
        (plans / "resume.md").write_text("# HANDOFF RESUME\nnext\n")
        self.assertEqual(self.run_hook("plan", {"tool_input": {}}).returncode, 0)


if __name__ == "__main__":
    unittest.main()
