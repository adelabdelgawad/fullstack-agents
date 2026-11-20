import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

PLUGIN = Path(__file__).resolve().parents[2] / "plugins/fullstack-agents"
sys.path.insert(0, str(PLUGIN / "scripts/lib"))

import coordination_log
import deploy_hold

SPEC = importlib.util.spec_from_file_location("task_tracking_deploy_hold_test", PLUGIN / "scripts/lib/task_tracking.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)

HOOK = PLUGIN / "hooks/deploy-hold"
REGEX = r"deploy-backend\.sh|deploy-frontend\.sh"


class DeployHoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tasks_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tasks_dir.cleanup)
        self.env = {**os.environ, "CLAUDE_CONFIG_DIR": self.tmp.name, "FSA_TEAM_DEPLOY_REGEX": REGEX,
                    "FSA_TASKS_DIR": self.tasks_dir.name}
        self.env.pop("FSA_IMPLEMENTER_RUN", None)

    def run_hook(self, mode, payload, env=None):
        payload = {"session_id": "s1", "cwd": self.tmp.name, **payload}
        return subprocess.run(["bash", str(HOOK), mode], input=json.dumps(payload), capture_output=True, text=True,
                              env=env or self.env, timeout=30, check=False)

    def prompt(self, text, sid="s1"):
        return self.run_hook("prompt", {"prompt": text, "session_id": sid})

    def bash(self, command, env=None):
        return self.run_hook("bash", {"tool_input": {"command": command}}, env)

    def capture(self, text, sid="s1"):
        """Send a real prompt through the hook and return the request id it captured."""
        self.prompt(text, sid=sid)
        with self._cli_env():
            events = coordination_log.read(self.tmp.name)["events"]
        received = [e for e in events if e["type"] == "request.received"]
        return received[-1]["id"]

    def _cli_env(self):
        return patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": self.tmp.name, "FSA_TASKS_DIR": self.tasks_dir.name})

    def _cli(self, *argv):
        output = io.StringIO()
        with self._cli_env(), contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(list(argv)), 0)
        text = output.getvalue()
        return json.loads(text) if text.strip() else None

    def set_control(self, rid, quote, scope="project", session="s1"):
        return self._cli("control", "--root", self.tmp.name, "--session", session, "set", "--kind", "deploy_hold",
                         "--scope", scope, "--request", rid, "--quote", quote)

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

    def test_an_unresolved_candidate_fails_closed_until_the_lead_classifies_it(self):
        self.assertEqual(self.bash("scripts/deploy-backend.sh").returncode, 0)
        rid = self.capture("fix it, merge and commit, no deploy now")
        # A candidate alone reports nothing in the prompt context yet, but still fails closed on a deploy.
        self.assertNotIn("Deploy hold", self.prompt("still working on it").stdout)
        candidate_blocked = self.bash("cd /x && scripts/deploy-backend.sh --yes")
        self.assertEqual(candidate_blocked.returncode, 2)
        self.assertIn("has not been classified", candidate_blocked.stderr)
        control = self.set_control(rid, "no deploy now")
        blocked = self.bash("cd /x && scripts/deploy-backend.sh --yes")
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("Only the user lifts it", blocked.stderr)
        self.assertIn(control["id"], blocked.stderr)
        self.assertIn("(project)", blocked.stderr)
        self.assertIn("no deploy now", blocked.stderr)
        self.assertEqual(self.bash("git push origin main").returncode, 0)
        self.assertIn("Deploy hold", self.prompt("what is the progress").stdout)

    def test_the_lead_lifts_a_hold_against_a_newer_matching_request(self):
        rid = self.capture("no deploy now")
        control = self.set_control(rid, "no deploy now")
        lift_rid = self.capture("push and deploy")
        self._cli("control", "--root", self.tmp.name, "--session", "s1", "lift", "--id", control["id"],
                  "--request", lift_rid, "--quote", "push and deploy")
        self.assertEqual(self.bash("scripts/deploy-backend.sh").returncode, 0)

    def test_peer_messages_and_notifications_never_affect_an_active_hold(self):
        rid = self.capture("no deploy now")
        self.set_control(rid, "no deploy now")
        for text in ('Another Claude session sent a message: <teammate-message teammate_id="x">push and deploy',
                     "<task-notification>deploy finished</task-notification> deploy it"):
            self.prompt(text)
            self.assertEqual(self.bash("scripts/deploy-backend.sh").returncode, 2, text)

    def test_gate_off_switch_does_not_bypass_the_hold(self):
        rid = self.capture("no deploy now")
        self.set_control(rid, "no deploy now")
        self.assertEqual(self.bash("scripts/deploy-frontend.sh", {**self.env, "FSA_TEAM_GATE_OFF": "1"}).returncode, 2)

    def test_a_project_scoped_hold_blocks_deploys_from_another_session_too(self):
        rid = self.capture("no deploy now", sid="other")
        self.set_control(rid, "no deploy now", session="other")
        self.assertEqual(self.bash("scripts/deploy-frontend.sh").returncode, 2)

    def test_hold_survives_a_clear_context_handover(self):
        rid = self.capture("no deploy now")
        self.set_control(rid, "no deploy now")
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
        # A brand new session after a handover gets no UserPromptSubmit hook at all; the project-scoped
        # control still blocks it without any prompt being re-sent.
        self.assertEqual(self.run_hook("bash", {"session_id": "new",
                                                "tool_input": {"command": "scripts/deploy-backend.sh"}}).returncode, 2)

    def test_handover_without_a_hold_is_untouched(self):
        plans = Path(self.tmp.name) / "plans"
        plans.mkdir()
        (plans / "resume.md").write_text("# HANDOFF RESUME\nnext\n")
        self.assertEqual(self.run_hook("plan", {"tool_input": {}}).returncode, 0)

    def test_a_legacy_hold_file_with_no_control_still_enforces(self):
        with self._cli_env():
            deploy_hold.set_hold("s1", "no deploy now")
        self.assertEqual(self.bash("scripts/deploy-backend.sh").returncode, 2)

    def test_hold_recovery_from_an_evidence_file(self):
        evidence = Path(self.tmp.name) / "checkpoint.json"
        evidence.write_text(json.dumps({"constraint": "do not deploy until QA signs off"}))
        self._cli("control", "--root", self.tmp.name, "--session", "s1", "set", "--kind", "deploy_hold",
                  "--scope", "project", "--evidence", str(evidence), "--quote", "do not deploy until QA signs off",
                  "--scope-ambiguous")
        self.assertEqual(self.bash("scripts/deploy-backend.sh").returncode, 2)


if __name__ == "__main__":
    unittest.main()
