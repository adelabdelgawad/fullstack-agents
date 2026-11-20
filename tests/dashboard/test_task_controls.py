"""Scoped, append-only controls: `fsa-task control`, scope resolution and candidate folding; see
docs/TASK_LIFECYCLE_DESIGN.md §15."""
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
import task_checkpoint
import task_controls

SPEC = importlib.util.spec_from_file_location("task_tracking_control_test", LIB / "task_tracking.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)


def git(args, cwd):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


SESSION = "ctl-session"


class ControlsTestCase(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-controls-")
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
            "CODEX_THREAD_ID": SESSION})
        self.env.start()
        self.addCleanup(self.env.stop)

    def hook(self, prompt, session=SESSION, host_id=None):
        return {"session_id": session, "cwd": str(self.root), "prompt": prompt, "prompt_id": host_id}

    def capture(self, prompt, session=SESSION, host_id=None):
        return request_inbox.capture(self.hook(prompt, session=session, host_id=host_id))

    def events(self):
        return coordination_log.read(str(self.root))["events"]

    def _run(self, command, args, session):
        argv = [command, "--root", str(self.root), "--session", session, *args]
        return argv

    def call(self, action, *args, session=SESSION):
        argv = self._run("control", [action, *args], session)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(argv), 0)
        text = output.getvalue()
        return json.loads(text) if text.strip() else None

    def call_fail(self, action, *args, session=SESSION):
        argv = self._run("control", [action, *args], session)
        error = io.StringIO()
        with contextlib.redirect_stderr(error), self.assertRaises(SystemExit):
            tasks.main(argv)
        return error.getvalue()

    def bind(self, session, filename="TASKS.md"):
        path = self.root / filename
        if not path.exists():
            argv = ["init", "--root", str(self.root), "--file", filename, "--session", session,
                     "--task", "T1|pending|Task 1|"]
        else:
            argv = ["bind", "--root", str(self.root), "--file", filename, "--session", session]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(argv), 0)


class SetValidationTests(ControlsTestCase):
    def test_set_refused_when_quote_does_not_occur_in_the_request(self):
        rid = self.capture("please hold off, do not deploy until I say so")
        error = self.call_fail("set", "--kind", "deploy_hold", "--scope", "project", "--request", rid,
                                "--quote", "totally unrelated phrase")
        self.assertIn("does not occur", error)

    def test_set_refused_when_quote_is_shorter_than_eight_characters(self):
        rid = self.capture("stop everything right now")
        error = self.call_fail("set", "--kind", "pause", "--scope", "project", "--request", rid, "--quote", "stop")
        self.assertIn("does not occur", error)

    def test_set_requires_exactly_one_of_request_or_evidence(self):
        rid = self.capture("please hold the deploy for now")
        error = self.call_fail("set", "--kind", "deploy_hold", "--scope", "project", "--request", rid,
                                "--evidence", "/nonexistent.json", "--quote", "please hold the deploy for now")
        self.assertIn("exactly one of", error)

    def test_deploy_hold_scope_rows_is_refused(self):
        rid = self.capture("no deploy now please")
        error = self.call_fail("set", "--kind", "deploy_hold", "--scope", "rows", "--rows", "T1",
                                "--request", rid, "--quote", "no deploy now please")
        self.assertIn("cannot be rows", error)

    def test_task_scope_requires_a_bound_ledger(self):
        rid = self.capture("stop everything right now please")
        error = self.call_fail("set", "--kind", "pause", "--scope", "task", "--request", rid,
                                "--quote", "stop everything right now")
        self.assertIn("requires a bound task ledger", error)


class ScopeApplicabilityTests(ControlsTestCase):
    def test_project_scope_applies_to_any_session(self):
        rid = self.capture("please hold off, do not deploy until I say so")
        self.call("set", "--kind", "deploy_hold", "--scope", "project", "--request", rid,
                  "--quote", "do not deploy until I say so")
        self.assertTrue(task_controls.active_controls(str(self.root), "someone-else", kind="deploy_hold"))

    def test_task_scope_applies_to_the_bound_session_and_an_unbound_one_not_a_different_ledger(self):
        self.bind(SESSION)
        rid = self.capture("stop everything right now please", session=SESSION)
        self.call("set", "--kind", "pause", "--scope", "task", "--request", rid,
                  "--quote", "stop everything right now")
        self.assertTrue(task_controls.active_controls(str(self.root), SESSION, kind="pause"))
        self.assertTrue(task_controls.active_controls(str(self.root), "new-session", kind="pause"))
        self.bind("new-session", filename="OTHER.md")
        self.assertFalse(task_controls.active_controls(str(self.root), "new-session", kind="pause"))

    def test_rows_scope_records_full_row_keys_for_the_bound_ledger(self):
        self.bind(SESSION)
        rid = self.capture("please pause T1 only for now", session=SESSION)
        result = self.call("set", "--kind", "pause", "--scope", "rows", "--rows", "T1", "--request", rid,
                           "--quote", "please pause T1 only for now")
        self.assertEqual(result["scope"]["rows"], ["TASKS.md#T1"])


class LiftNarrowDismissTests(ControlsTestCase):
    def test_lift_refused_on_a_request_older_than_the_control(self):
        rid1 = self.capture("no deploy now please")
        cid = self.call("set", "--kind", "deploy_hold", "--scope", "project", "--request", rid1,
                        "--quote", "no deploy now please")["id"]
        error = self.call_fail("lift", "--id", cid, "--request", rid1, "--quote", "no deploy now please")
        self.assertIn("predates the control", error)

    def test_lift_refused_on_a_quote_not_in_the_request(self):
        rid1 = self.capture("no deploy now please")
        cid = self.call("set", "--kind", "deploy_hold", "--scope", "project", "--request", rid1,
                        "--quote", "no deploy now please")["id"]
        rid2 = self.capture("go ahead and deploy the backend now")
        error = self.call_fail("lift", "--id", cid, "--request", rid2, "--quote", "completely unrelated words")
        self.assertIn("does not occur", error)

    def test_lift_with_a_newer_matching_request_ends_the_control(self):
        rid1 = self.capture("no deploy now please")
        cid = self.call("set", "--kind", "deploy_hold", "--scope", "project", "--request", rid1,
                        "--quote", "no deploy now please")["id"]
        rid2 = self.capture("go ahead and deploy the backend now")
        result = self.call("lift", "--id", cid, "--request", rid2, "--quote", "go ahead and deploy the backend")
        self.assertTrue(result["lifted"])
        self.assertFalse(task_controls.active_controls(str(self.root), "x", kind="deploy_hold"))

    def test_lift_has_no_dead_reason_argument(self):
        rid1 = self.capture("no deploy now please")
        cid = self.call("set", "--kind", "deploy_hold", "--scope", "project", "--request", rid1,
                        "--quote", "no deploy now please")["id"]
        rid2 = self.capture("go ahead and deploy the backend now")
        error = self.call_fail("lift", "--id", cid, "--request", rid2, "--quote", "go ahead and deploy the backend",
                               "--reason", "resolved")
        self.assertIn("unrecognized", error.lower())

    def test_narrow_changes_scope_with_its_own_quote_check(self):
        self.bind(SESSION)
        rid1 = self.capture("stop everything for now please", session=SESSION)
        cid = self.call("set", "--kind", "pause", "--scope", "project", "--request", rid1,
                        "--quote", "stop everything for now")["id"]
        rid2 = self.capture("actually just pause row T1 specifically", session=SESSION)
        result = self.call("narrow", "--id", cid, "--scope", "rows", "--rows", "T1", "--request", rid2,
                           "--quote", "actually just pause row T1")
        self.assertEqual(result["scope"], {"level": "rows", "task": "TASKS.md", "rows": ["TASKS.md#T1"]})

    def test_dismiss_requires_a_reason_and_is_listed(self):
        rid = self.capture("please hold off on the deploy for a bit")
        task_controls.record_candidate(str(self.root), SESSION, rid, "deploy_hold", "please hold off on the deploy")
        error = self.call_fail("dismiss", "--request", rid, "--kind", "deploy_hold", "--reason", "")
        self.assertIn("requires --reason", error)
        result = self.call("dismiss", "--request", rid, "--kind", "deploy_hold", "--reason", "false positive")
        self.assertTrue(result["dismissed"])
        dismissed = self.call("list", "--dismissed")["dismissed"]
        self.assertEqual(dismissed[0]["request"], rid)
        self.assertIsNone(task_controls.unresolved_project_candidate(str(self.root), "deploy_hold"))


class MigrateAndRecoveryTests(ControlsTestCase):
    def test_migrate_uses_task_scope_when_the_session_owns_one_ledger_and_is_idempotent(self):
        self.bind("legacy-sid")
        deploy_hold.set_hold("legacy-sid", "no deploy now please")
        result = self.call("migrate")
        self.assertEqual(len(result["migrated"]), 1)
        controls = self.call("list")["controls"]
        self.assertEqual(controls[0]["provenance"]["source"], "legacy_migration")
        self.assertEqual(controls[0]["scope"], {"level": "task", "task": "TASKS.md"})
        self.assertEqual(self.call("migrate")["migrated"], [])

    def test_migrate_flags_scope_ambiguous_without_a_binding(self):
        self.capture("please hold the deploy for now", session="drifter-sid")
        deploy_hold.set_hold("drifter-sid", "please hold the deploy for now")
        self.call("migrate")
        controls = self.call("list")["controls"]
        self.assertEqual(controls[0]["scope"]["level"], "project")
        self.assertTrue(controls[0]["scope"]["scope_ambiguous"])

    def test_migrate_flags_quote_unreliable_for_a_notification(self):
        self.capture("status update", session="notif-sid")
        deploy_hold.set_hold("notif-sid", "<task-notification>deploy finished</task-notification>")
        self.call("migrate")
        controls = self.call("list")["controls"]
        self.assertTrue(controls[0]["provenance"]["quote_unreliable"])

    def test_migrate_flags_quote_unreliable_for_a_multi_sentence_quote(self):
        self.capture("status update", session="multi-sid")
        deploy_hold.set_hold("multi-sid", "Build finished. Also, do not deploy until further notice. Thanks!")
        self.call("migrate")
        controls = self.call("list")["controls"]
        self.assertTrue(controls[0]["provenance"]["quote_unreliable"])

    def test_migrate_skips_a_session_with_no_evidence_of_belonging_to_this_project(self):
        deploy_hold.set_hold("foreign-sid", "please hold the deploy for now")
        result = self.call("migrate")
        self.assertEqual(result["migrated"], [])
        self.assertIn("foreign-sid", result["skipped_other_project"])
        self.assertEqual(self.call("list")["controls"], [])

    def test_migrate_imports_a_binding_rooted_under_a_subdirectory_of_the_project(self):
        subdir = self.root / "pkg"
        subdir.mkdir()
        argv = ["init", "--root", str(subdir), "--file", "TASKS.md", "--session", "subdir-sid",
                "--task", "T1|pending|Task 1|"]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(argv), 0)
        deploy_hold.set_hold("subdir-sid", "no deploy now please")
        result = self.call("migrate")
        self.assertNotIn("subdir-sid", result["skipped_other_project"])
        self.assertEqual(len(result["migrated"]), 1)

    def test_migrate_skips_a_file_that_already_carries_a_control_id(self):
        self.capture("no deploy now please", session="mirrored-sid")
        deploy_hold.set_hold("mirrored-sid", "no deploy now please", control_id="C99")
        result = self.call("migrate")
        self.assertEqual(result["migrated"], [])

    def test_lifted_migrated_control_leaves_legacy_file_enforcing_and_is_listed(self):
        self.bind("legacy-sid")
        deploy_hold.set_hold("legacy-sid", "no deploy now please")
        cid = self.call("migrate")["migrated"][0]
        rid = self.capture("go ahead and deploy now", session="legacy-sid")
        self.call("lift", "--id", cid, "--request", rid, "--quote", "go ahead and deploy now")
        self.assertTrue(deploy_hold.hold_path("legacy-sid").exists())
        held = deploy_hold.read_hold("legacy-sid")
        self.assertNotIn("control_id", held)
        legacy = self.call("list").get("legacy_still_enforcing") or []
        self.assertEqual(legacy[0]["session"], "legacy-sid")
        self.assertEqual(legacy[0]["path"], str(deploy_hold.hold_path("legacy-sid")))

    def test_migrate_never_deletes_the_legacy_file(self):
        self.bind("legacy-sid")
        deploy_hold.set_hold("legacy-sid", "no deploy now please")
        self.call("migrate")
        self.assertTrue(deploy_hold.hold_path("legacy-sid").exists())

    def test_set_from_evidence_recovers_without_a_request(self):
        evidence = Path(self.scratch.name) / "checkpoint.json"
        evidence.write_text(json.dumps({"constraint": "do not deploy until QA signs off"}))
        result = self.call("set", "--kind", "deploy_hold", "--scope", "project", "--evidence", str(evidence),
                           "--quote", "do not deploy until QA signs off", "--scope-ambiguous")
        self.assertEqual(result["scope"], {"level": "project", "scope_ambiguous": True})
        controls = self.call("list")["controls"]
        self.assertEqual(controls[0]["provenance"]["source"], "lead_recovery")
        self.assertEqual(controls[0]["provenance"]["evidence"], str(evidence))

    def test_set_from_evidence_requires_the_quote_in_the_file(self):
        evidence = Path(self.scratch.name) / "checkpoint.json"
        evidence.write_text("nothing relevant here")
        error = self.call_fail("set", "--kind", "deploy_hold", "--scope", "project", "--evidence", str(evidence),
                               "--quote", "do not deploy at all")
        self.assertIn("does not occur", error)


class CandidateDetectionTests(ControlsTestCase):
    def test_notification_yields_no_candidate(self):
        rid = request_inbox.capture(self.hook("<task-notification>do not deploy</task-notification>"))
        self.assertIsNone(rid)
        task_controls.record_candidate(str(self.root), SESSION, rid, "deploy_hold", "x")
        self.assertEqual([e for e in self.events() if e["type"] == "control.candidate"], [])

    def test_quoted_fenced_and_blockquote_text_is_stripped_before_detection(self):
        text = ('Investigation notes: the old script said "no deploy today" but that was removed.\n'
                '```\n# no deploy here either\n```\n> no deploy per the ticket\nPlease continue the migration.')
        cleaned = task_controls.strip_quoted(text)
        self.assertNotIn("no deploy today", cleaned)
        self.assertNotIn("no deploy here either", cleaned)
        self.assertNotIn("no deploy per the ticket", cleaned)

    def test_structured_pasted_prompt_still_yields_a_candidate(self):
        text = '<pasted_content id="abc">Please do not deploy until the migration is reviewed.</pasted_content>'
        cleaned = task_controls.strip_quoted(text)
        self.assertIn("do not deploy", cleaned)

    def test_unresolved_project_candidate_is_visible_to_any_session(self):
        rid = self.capture("please do not deploy this afternoon", session="other-session")
        task_controls.record_candidate(str(self.root), "other-session", rid, "deploy_hold",
                                        "please do not deploy this afternoon")
        candidate = task_controls.unresolved_project_candidate(str(self.root), "deploy_hold")
        self.assertEqual(candidate["request"], rid)
        self.call("dismiss", "--request", rid, "--kind", "deploy_hold", "--reason", "not a real hold")
        self.assertIsNone(task_controls.unresolved_project_candidate(str(self.root), "deploy_hold"))

    def test_unresolved_session_candidate_is_scoped_to_its_own_session(self):
        rid = self.capture("stop everything for a minute", session=SESSION)
        task_controls.record_candidate(str(self.root), SESSION, rid, "pause", "stop everything for a minute")
        self.assertIsNone(task_controls.unresolved_session_candidate(str(self.root), "other-session", "pause"))
        self.assertIsNotNone(task_controls.unresolved_session_candidate(str(self.root), SESSION, "pause"))

    def test_record_candidate_is_idempotent_per_request_and_kind(self):
        rid = self.capture("stop everything for a minute")
        task_controls.record_candidate(str(self.root), SESSION, rid, "pause", "stop everything for a minute")
        task_controls.record_candidate(str(self.root), SESSION, rid, "pause", "stop everything for a minute")
        candidates = [e for e in self.events() if e["type"] == "control.candidate"]
        self.assertEqual(len(candidates), 1)


class MirrorGuardTests(ControlsTestCase):
    def test_mirror_not_written_when_a_legacy_hold_file_already_exists(self):
        deploy_hold.set_hold(SESSION, "an old legacy hold text")
        rid = self.capture("no deploy now please")
        self.call("set", "--kind", "deploy_hold", "--scope", "project", "--request", rid,
                  "--quote", "no deploy now please")
        held = deploy_hold.read_hold(SESSION)
        self.assertEqual(held["quote"], "an old legacy hold text")
        self.assertNotIn("control_id", held)

    def test_mirror_written_when_no_hold_file_exists(self):
        rid = self.capture("no deploy now please")
        cid = self.call("set", "--kind", "deploy_hold", "--scope", "project", "--request", rid,
                        "--quote", "no deploy now please")["id"]
        held = deploy_hold.read_hold(SESSION)
        self.assertEqual(held["control_id"], cid)

    def test_mirror_removed_on_lift_only_when_it_carries_a_control_id(self):
        rid1 = self.capture("no deploy now please")
        cid = self.call("set", "--kind", "deploy_hold", "--scope", "project", "--request", rid1,
                        "--quote", "no deploy now please")["id"]
        rid2 = self.capture("go ahead and deploy now")
        self.call("lift", "--id", cid, "--request", rid2, "--quote", "go ahead and deploy now")
        self.assertIsNone(deploy_hold.read_hold(SESSION))

    def test_legacy_file_untouched_by_lift_of_an_unrelated_mirror(self):
        deploy_hold.set_hold("other-sid", "an unrelated legacy hold")
        rid1 = self.capture("no deploy now please")
        cid = self.call("set", "--kind", "deploy_hold", "--scope", "project", "--request", rid1,
                        "--quote", "no deploy now please")["id"]
        rid2 = self.capture("go ahead and deploy now")
        self.call("lift", "--id", cid, "--request", rid2, "--quote", "go ahead and deploy now")
        held = deploy_hold.read_hold("other-sid")
        self.assertEqual(held["quote"], "an unrelated legacy hold")


class NarrowScopeValidationTests(ControlsTestCase):
    def test_narrow_refused_when_widening_from_task_to_project(self):
        self.bind(SESSION)
        rid1 = self.capture("stop everything for now please", session=SESSION)
        cid = self.call("set", "--kind", "pause", "--scope", "task", "--request", rid1,
                        "--quote", "stop everything for now")["id"]
        rid2 = self.capture("actually let's pause the whole project", session=SESSION)
        error = self.call_fail("narrow", "--id", cid, "--scope", "project", "--request", rid2,
                               "--quote", "pause the whole project")
        self.assertIn("strictly inside", error)

    def test_narrow_refused_when_rows_are_not_a_subset(self):
        self.bind(SESSION)
        rid1 = self.capture("pause row T1 for now please", session=SESSION)
        cid = self.call("set", "--kind", "pause", "--scope", "rows", "--rows", "T1", "--request", rid1,
                        "--quote", "pause row T1 for now")["id"]
        rid2 = self.capture("actually also pause row T2 instead", session=SESSION)
        error = self.call_fail("narrow", "--id", cid, "--scope", "rows", "--rows", "T2", "--request", rid2,
                               "--quote", "also pause row T2 instead")
        self.assertIn("strictly inside", error)

    def test_narrow_refused_on_a_request_older_than_the_control(self):
        self.bind(SESSION)
        rid1 = self.capture("stop everything for now please", session=SESSION)
        cid = self.call("set", "--kind", "pause", "--scope", "task", "--request", rid1,
                        "--quote", "stop everything for now")["id"]
        error = self.call_fail("narrow", "--id", cid, "--scope", "rows", "--rows", "T1", "--request", rid1,
                               "--quote", "stop everything for now")
        self.assertIn("predates the control", error)


class EvidenceKindRestrictionTests(ControlsTestCase):
    def test_evidence_refused_for_pause_kind(self):
        evidence = Path(self.scratch.name) / "checkpoint.json"
        evidence.write_text(json.dumps({"constraint": "pause everything until QA signs off"}))
        error = self.call_fail("set", "--kind", "pause", "--scope", "project", "--evidence", str(evidence),
                               "--quote", "pause everything until QA")
        self.assertIn("deploy_hold", error)

    def test_evidence_refused_for_approval_kind(self):
        evidence = Path(self.scratch.name) / "checkpoint.json"
        evidence.write_text(json.dumps({"constraint": "approved to proceed with everything"}))
        error = self.call_fail("set", "--kind", "approval", "--scope", "project", "--evidence", str(evidence),
                               "--quote", "approved to proceed with everything")
        self.assertIn("deploy_hold", error)


class DismissRequiresCandidateTests(ControlsTestCase):
    def test_dismiss_refused_without_an_existing_unresolved_candidate(self):
        rid = self.capture("please hold off on the deploy for a bit")
        error = self.call_fail("dismiss", "--request", rid, "--kind", "deploy_hold", "--reason", "no candidate here")
        self.assertIn("unresolved", error.lower())

    def test_dismiss_refused_after_the_candidate_is_already_resolved_by_set(self):
        rid = self.capture("please hold off on the deploy for a bit")
        task_controls.record_candidate(str(self.root), SESSION, rid, "deploy_hold", "please hold off on the deploy")
        self.call("set", "--kind", "deploy_hold", "--scope", "project", "--request", rid,
                  "--quote", "please hold off on the deploy")
        error = self.call_fail("dismiss", "--request", rid, "--kind", "deploy_hold", "--reason", "already resolved")
        self.assertIn("unresolved", error.lower())


class RequiredScopeTests(ControlsTestCase):
    def test_set_without_scope_is_refused_by_argparse(self):
        rid = self.capture("please hold the deploy for now")
        error = self.call_fail("set", "--kind", "deploy_hold", "--request", rid,
                               "--quote", "please hold the deploy for now")
        self.assertIn("--scope", error)


class LedgerUntouchedTests(ControlsTestCase):
    def test_ledger_file_is_byte_identical_after_control_operations(self):
        self.bind(SESSION)
        ledger_path = self.root / "TASKS.md"
        before = ledger_path.read_bytes()
        rid1 = self.capture("please pause everything for now", session=SESSION)
        cid = self.call("set", "--kind", "pause", "--scope", "project", "--request", rid1,
                        "--quote", "please pause everything for now")["id"]
        rid2 = self.capture("actually just pause row T1 specifically", session=SESSION)
        self.call("narrow", "--id", cid, "--scope", "rows", "--rows", "T1", "--request", rid2,
                 "--quote", "actually just pause row T1")
        rid3 = self.capture("go ahead and resume everything", session=SESSION)
        self.call("lift", "--id", cid, "--request", rid3, "--quote", "go ahead and resume everything")
        rid4 = self.capture("maybe hold the deploy, not sure", session=SESSION)
        task_controls.record_candidate(str(self.root), SESSION, rid4, "deploy_hold", "maybe hold the deploy")
        self.call("dismiss", "--request", rid4, "--kind", "deploy_hold", "--reason", "false positive")
        self.call("migrate")
        after = ledger_path.read_bytes()
        self.assertEqual(before, after)

    def test_ledger_checkpoint_with_approvals_is_byte_identical_after_control_operations(self):
        self.bind(SESSION)
        ledger_path = self.root / "TASKS.md"
        payload = {
            "goal": "Ship scoped controls", "scope": {"in": ["controls"], "out": []},
            "approvals": [{"quote": "yes do that", "at": "2026-10-19T20:00:00Z", "scope": "controls",
                           "kind": "task", "used": False, "clarity": "explicit"}],
            "decisions": [], "constraints": [], "done": [], "next": {"action": "test", "owner": "claude"},
            "evidence": [], "verification": [], "status": "active"}
        text, changed = task_checkpoint.apply(ledger_path.read_text(), payload, self.root, "T1", SESSION)
        self.assertTrue(changed)
        ledger_path.write_text(text)
        before = ledger_path.read_bytes()
        rid1 = self.capture("please pause everything for now", session=SESSION)
        cid = self.call("set", "--kind", "pause", "--scope", "project", "--request", rid1,
                        "--quote", "please pause everything for now")["id"]
        rid2 = self.capture("actually just pause row T1 specifically", session=SESSION)
        self.call("narrow", "--id", cid, "--scope", "rows", "--rows", "T1", "--request", rid2,
                 "--quote", "actually just pause row T1")
        rid3 = self.capture("go ahead and resume everything", session=SESSION)
        self.call("lift", "--id", cid, "--request", rid3, "--quote", "go ahead and resume everything")
        rid4 = self.capture("maybe hold the deploy, not sure", session=SESSION)
        task_controls.record_candidate(str(self.root), SESSION, rid4, "deploy_hold", "maybe hold the deploy")
        self.call("dismiss", "--request", rid4, "--kind", "deploy_hold", "--reason", "false positive")
        self.call("migrate")
        after = ledger_path.read_bytes()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
