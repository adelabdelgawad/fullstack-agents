"""The four confirmed defects this unit fixes (see the FSA1 design's amendment 18 and item 17): a later unrelated
prompt erasing a pause/approval, a quoted/pasted negation forging a deploy hold, a notification creating a hold,
and a hold set in one session going unenforced in a new one after a handover."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "plugins/fullstack-agents/scripts/lib"
sys.path.insert(0, str(LIB))
import coordination_log
import deploy_hold
import request_inbox
import stop_guard
import task_controls
import task_lifecycle

SPEC = importlib.util.spec_from_file_location("task_tracking_control_regression_test", LIB / "task_tracking.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)


def git(args, cwd):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


SESSION = "regress-session"


class RegressionTestCase(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-regress-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name) / "repo"
        self.root.mkdir()
        git(["init", "-q"], self.root)
        git(["config", "user.email", "a@example.com"], self.root)
        git(["config", "user.name", "Test"], self.root)
        (self.root / "README.md").write_text("doc\n")
        git(["add", "-A"], self.root)
        git(["commit", "-q", "-m", "initial"], self.root)
        self.env = patch.dict(os.environ, {
            "FSA_TASKS_DIR": str(Path(self.scratch.name) / "tasks"),
            "FSA_STOP_GUARD_DIR": str(Path(self.scratch.name) / "guard"),
            "CLAUDE_CONFIG_DIR": str(Path(self.scratch.name) / "config"),
            "FSA_TEAM_DEPLOY_REGEX": r"deploy\.sh",
            "CODEX_THREAD_ID": SESSION})
        self.env.start()
        self.addCleanup(self.env.stop)

    def hook(self, prompt, session=SESSION):
        return {"session_id": session, "cwd": str(self.root), "prompt": prompt}

    def events(self):
        return coordination_log.read(str(self.root))["events"]

    def ledger(self, session=SESSION, filename="TASKS.md"):
        argv = ["init", "--root", str(self.root), "--file", filename, "--session", session,
                "--task", "T1|in_progress|Task 1|"]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(argv), 0)

    def call(self, command, action, *args, session=SESSION):
        argv = [command, "--root", str(self.root), "--session", session, action, *args]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(argv), 0)
        text = output.getvalue()
        return json.loads(text) if text.strip() else None

    def classify(self, rid, as_class, session=SESSION):
        self.call("request", "classify", "--id", rid, "--as", as_class, session=session)


class DefectATests(RegressionTestCase):
    """(a) a later unrelated prompt used to erase a pause/approval; a durable control no longer can be."""

    def test_a_later_unrelated_prompt_does_not_erase_a_durable_pause_control(self):
        self.ledger()
        hold = self.hook("stop everything, I need to re-plan this work")
        rid = request_inbox.capture(hold)
        stop_guard.record_prompt(hold)
        self.classify(rid, "pause")
        self.call("control", "set", "--kind", "pause", "--scope", "project", "--request", rid,
                  "--quote", "stop everything, I need to re-plan this work")
        unrelated = self.hook("what does the P1 row actually depend on")
        rid2 = request_inbox.capture(unrelated)
        stop_guard.record_prompt(unrelated)
        self.classify(rid2, "status")
        self.assertIsNone(stop_guard.decide(SESSION, str(self.root), "Progress update.", "claude"))


class DefectBTests(RegressionTestCase):
    """(b) a negated "deploy" inside pasted/quoted investigation text used to replace the stored hold quote."""

    def test_quoted_investigation_text_creates_no_deploy_hold_candidate(self):
        prompt = ('Investigation notes: the old runbook said "do not deploy under any circumstances" but that '
                  'guidance is outdated and was superseded last week. Please continue the migration and merge.')
        hook = self.hook(prompt)
        deploy_hold.on_prompt(hook)
        kinds = [event.get("kind") for event in self.events() if event["type"] == "control.candidate"]
        self.assertNotIn("deploy_hold", kinds)
        self.assertIsNone(task_controls.active_deploy_hold(str(self.root), SESSION))

    def test_fenced_deploy_text_creates_no_deploy_hold_candidate_through_on_prompt(self):
        prompt = '```\n# no deploy here either\n```\nPlease continue the migration and merge.'
        deploy_hold.on_prompt(self.hook(prompt))
        kinds = [event.get("kind") for event in self.events() if event["type"] == "control.candidate"]
        self.assertNotIn("deploy_hold", kinds)
        self.assertIsNone(task_controls.active_deploy_hold(str(self.root), SESSION))

    def test_structured_pasted_deploy_text_yields_a_candidate_through_on_prompt(self):
        prompt = '<pasted_content id="x">Please do not deploy until the migration is reviewed.</pasted_content>'
        deploy_hold.on_prompt(self.hook(prompt))
        candidates = [event for event in self.events() if event["type"] == "control.candidate"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["kind"], "deploy_hold")

    def test_an_active_holds_quote_is_never_replaced_by_a_later_prompt(self):
        rid = request_inbox.capture(self.hook("no deploy until further notice"))
        self.call("control", "set", "--kind", "deploy_hold", "--scope", "project", "--request", rid,
                  "--quote", "no deploy until further notice")
        deploy_hold.on_prompt(self.hook('Earlier someone wrote "please deploy right away" in the chat log.'))
        control = task_controls.active_deploy_hold(str(self.root), SESSION)
        self.assertEqual(control["quote"], "no deploy until further notice")


class DefectCTests(RegressionTestCase):
    """(c) a <task-notification> saying "do not deploy" used to create a hold on its own."""

    def test_notification_creates_no_candidate_or_hold(self):
        hook = self.hook("<task-notification>Build finished. Reminder: do not deploy until QA signs off."
                          "</task-notification>")
        deploy_hold.on_prompt(hook)
        self.assertEqual(self.events(), [])
        self.assertIsNone(task_controls.active_deploy_hold(str(self.root), SESSION))
        reason = deploy_hold.on_bash({"session_id": SESSION, "cwd": str(self.root),
                                      "tool_input": {"command": "deploy.sh"}})
        self.assertIsNone(reason)


class DefectDTests(RegressionTestCase):
    """(d) a hold set in session S1 used to go unenforced for session S2 after a handover with no prompt hook."""

    def test_a_hold_set_in_one_session_blocks_a_brand_new_session(self):
        rid = request_inbox.capture(self.hook("no deploy until further notice", session="S1"))
        self.call("control", "set", "--kind", "deploy_hold", "--scope", "project", "--request", rid,
                  "--quote", "no deploy until further notice", session="S1")
        reason = deploy_hold.on_bash({"session_id": "S2", "cwd": str(self.root),
                                      "tool_input": {"command": "deploy.sh"}})
        self.assertIsNotNone(reason)
        self.assertIn("deploy hold", reason.lower())

    def test_an_unbound_session_after_handover_still_enforces_a_task_level_hold(self):
        self.ledger(session="S1")
        rid = request_inbox.capture(self.hook("no deploy until further notice", session="S1"))
        self.call("control", "set", "--kind", "deploy_hold", "--scope", "task", "--request", rid,
                  "--quote", "no deploy until further notice", session="S1")
        self.assertTrue(task_controls.active_controls(str(self.root), "S2", kind="deploy_hold"))


class FailClosedTests(RegressionTestCase):
    """(5) a hook never fails open or loses state when the coordination log is unreadable."""

    def test_on_bash_skips_coordination_entirely_for_a_non_matching_command(self):
        with patch.object(task_controls, "active_deploy_hold", side_effect=AssertionError("should not be called")):
            reason = deploy_hold.on_bash({"session_id": SESSION, "cwd": str(self.root),
                                          "tool_input": {"command": "echo hello"}})
        self.assertIsNone(reason)

    def test_on_bash_fails_closed_when_coordination_log_is_unreadable_for_a_matching_command(self):
        with patch.object(task_controls, "active_deploy_hold", side_effect=OSError("boom")):
            reason = deploy_hold.on_bash({"session_id": SESSION, "cwd": str(self.root),
                                          "tool_input": {"command": "deploy.sh"}})
        self.assertIsNotNone(reason)
        self.assertIn("BLOCKED", reason)

    def test_on_prompt_continues_when_active_deploy_hold_lookup_fails(self):
        with patch.object(task_controls, "active_deploy_hold", side_effect=OSError("boom")):
            out = deploy_hold.on_prompt(self.hook("just checking in"))
        self.assertIsNone(out)

    def test_on_prompt_catches_record_candidate_errors_and_still_checks_the_legacy_hold(self):
        deploy_hold.set_hold(SESSION, "no deploy now please")
        with patch.object(task_controls, "record_candidate", side_effect=OSError("boom")):
            out = deploy_hold.on_prompt(self.hook("no deploy now please, hold off"))
        self.assertIsNotNone(out)
        self.assertIn("Deploy hold", out)

    def test_record_prompt_still_saves_state_when_coordination_log_fails(self):
        self.ledger()
        hook = self.hook("stop everything right now")
        with patch.object(task_controls, "record_candidate", side_effect=OSError("boom")):
            stop_guard.record_prompt(hook)
        path = stop_guard._state_path(SESSION)
        state = json.loads(path.read_text())
        self.assertTrue(state["paused"])

    def test_decide_continues_with_legacy_flags_when_coordination_log_fails(self):
        self.ledger()
        hook = self.hook("stop everything right now")
        rid = request_inbox.capture(hook)
        stop_guard.record_prompt(hook)
        self.classify(rid, "status")
        with patch.object(task_controls, "active_controls", side_effect=OSError("boom")), \
             patch.object(task_controls, "unresolved_session_candidate", side_effect=OSError("boom")):
            result = stop_guard.decide(SESSION, str(self.root), "Progress update.", "claude")
        self.assertIsNone(result)

    def test_session_start_continues_without_a_controls_line_when_coordination_log_fails(self):
        with patch.object(task_controls, "mirror_deploy_hold", side_effect=OSError("boom")):
            output = task_lifecycle._session_start({"session_id": SESSION, "source": "startup", "cwd": str(self.root)})
        self.assertIsNone(output)


class LiftHintTests(RegressionTestCase):
    """(6) on_prompt falls back to the old legacy context line, and a 'lift' verdict only hints, never lifts."""

    def test_on_prompt_reports_a_legacy_only_hold_with_the_old_context_line(self):
        deploy_hold.set_hold(SESSION, "no deploy until further notice")
        out = deploy_hold.on_prompt(self.hook("what's the status"))
        payload = json.loads(out)
        text = payload["hookSpecificOutput"]["additionalContext"]
        self.assertTrue(text.startswith('[fullstack-agents] Deploy hold: the user said "no deploy until further notice"'))

    def test_on_prompt_adds_a_lift_hint_line_without_lifting_the_control(self):
        rid = request_inbox.capture(self.hook("no deploy until further notice"))
        self.call("control", "set", "--kind", "deploy_hold", "--scope", "project", "--request", rid,
                  "--quote", "no deploy until further notice")
        out = deploy_hold.on_prompt(self.hook("go ahead and deploy the backend now"))
        payload = json.loads(out)
        text = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("fsa-task control lift --id", text)
        self.assertIn("--request", text)
        self.assertIn("--quote", text)
        self.assertIsNotNone(task_controls.active_deploy_hold(str(self.root), SESSION))


class RowScopedPauseApprovalTests(RegressionTestCase):
    """(7) rows-level pause/approval controls only affect their own rows; the candidate sentence is the match."""

    def multi_ledger(self):
        argv = ["init", "--root", str(self.root), "--file", "TASKS.md", "--session", SESSION,
                "--task", "T1|in_progress|Task 1|", "--task", "T2|in_progress|Task 2|"]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(argv), 0)

    def test_rows_level_approval_approves_only_those_rows(self):
        self.multi_ledger()
        hook = self.hook("go ahead and ship T1, T2 still needs review")
        rid = request_inbox.capture(hook)
        stop_guard.record_prompt(hook)
        self.classify(rid, "status")
        self.call("control", "set", "--kind", "approval", "--scope", "rows", "--rows", "T1", "--request", rid,
                  "--quote", "go ahead and ship")
        result = stop_guard.decide(SESSION, str(self.root), "Progress update.", "claude")
        self.assertIsNotNone(result)
        self.assertIn("T2", result)
        self.assertNotIn("T1 (", result)

    def test_rows_level_pause_control_does_not_disable_the_legacy_paused_flag(self):
        self.multi_ledger()
        hook1 = self.hook("let's pause on T1 specifically for now")
        rid1 = request_inbox.capture(hook1)
        stop_guard.record_prompt(hook1)
        self.classify(rid1, "status")
        self.call("control", "set", "--kind", "pause", "--scope", "rows", "--rows", "T1", "--request", rid1,
                  "--quote", "pause on T1 specifically")
        hook2 = self.hook("stop everything right now")
        rid2 = request_inbox.capture(hook2)
        stop_guard.record_prompt(hook2)
        self.classify(rid2, "status")
        self.call("control", "dismiss", "--request", rid2, "--kind", "pause", "--reason", "covered by the raw flag")
        result = stop_guard.decide(SESSION, str(self.root), "Progress update.", "claude")
        self.assertIsNone(result)

    def test_pause_candidate_sentence_is_the_matching_sentence_not_the_full_text(self):
        hook = self.hook("Quick status: the build is green. Please stop everything for now, I need to replan.")
        request_inbox.capture(hook)
        stop_guard.record_prompt(hook)
        candidate = task_controls.unresolved_session_candidate(str(self.root), SESSION, "pause")
        self.assertEqual(candidate["sentence"], "Please stop everything for now, I need to replan.")

    def test_approval_candidate_sentence_is_the_matching_sentence_not_the_full_text(self):
        hook = self.hook("Quick status: the build is green. Go ahead and ship it, nothing else pending.")
        request_inbox.capture(hook)
        stop_guard.record_prompt(hook)
        candidate = task_controls.unresolved_session_candidate(str(self.root), SESSION, "approval")
        self.assertEqual(candidate["sentence"], "Go ahead and ship it, nothing else pending.")


class AdditionalCandidateAndRecoveryTests(RegressionTestCase):
    """(9) fenced/quoted/structured prompts through record_prompt; approval replaces the flag; new-session line."""

    def test_fenced_and_quoted_pause_text_is_stripped_before_recording_a_candidate(self):
        hook = self.hook('```\nstop everything\n```\n"please stop everything" was from yesterday. '
                          'Continue the migration.')
        request_inbox.capture(hook)
        stop_guard.record_prompt(hook)
        candidates = [e for e in self.events() if e["type"] == "control.candidate"]
        self.assertEqual(candidates, [])

    def test_structured_pasted_pause_text_still_yields_a_candidate_through_record_prompt(self):
        hook = self.hook('<pasted_content id="x">Please stop everything until further notice.</pasted_content>')
        request_inbox.capture(hook)
        stop_guard.record_prompt(hook)
        kinds = [e["kind"] for e in self.events() if e["type"] == "control.candidate"]
        self.assertIn("pause", kinds)

    def test_unresolved_pause_candidate_holds_the_turn(self):
        self.ledger()
        hook = self.hook("stop everything, let's replan")
        rid = request_inbox.capture(hook)
        stop_guard.record_prompt(hook)
        self.classify(rid, "status")
        result = stop_guard.decide(SESSION, str(self.root), "Progress update.", "claude")
        self.assertIn("classify the possible pause", result)

    def test_approval_control_replaces_the_legacy_flag(self):
        self.ledger()
        hook = self.hook("here is a status update, nothing to approve yet")
        rid = request_inbox.capture(hook)
        stop_guard.record_prompt(hook)
        self.classify(rid, "status")
        self.call("control", "set", "--kind", "approval", "--scope", "project", "--request", rid,
                  "--quote", "status update, nothing to approve yet")
        result = stop_guard.decide(SESSION, str(self.root), "Approve the plan and I'll start?", "claude")
        self.assertIsNotNone(result)
        self.assertIn("T1", result)

    def test_session_start_prints_the_controls_line_for_a_new_session_id(self):
        rid = request_inbox.capture(self.hook("no deploy until further notice", session="S1"))
        self.call("control", "set", "--kind", "deploy_hold", "--scope", "project", "--request", rid,
                  "--quote", "no deploy until further notice", session="S1")
        output = task_lifecycle._session_start({"session_id": "S2", "source": "startup", "cwd": str(self.root)})
        self.assertIn("Active controls:", output)


if __name__ == "__main__":
    unittest.main()
