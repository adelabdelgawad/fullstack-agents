"""Completion evidence for v2 deliverables: fsa-task accept/check/baseline/verify (docs/TASK_LIFECYCLE_DESIGN.md §12)."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "plugins/fullstack-agents/scripts/lib"
CLI = REPO / "plugins/fullstack-agents/scripts/fsa-task"
sys.path.insert(0, str(LIB))
SPEC = importlib.util.spec_from_file_location("task_tracking_evidence", LIB / "task_tracking.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)
import task_evidence


def git(args, cwd):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


class TaskEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-evidence-")
        self.root = Path(self.scratch.name) / "repo"
        self.root.mkdir()
        git(["init", "-q"], self.root)
        git(["config", "user.email", "a@example.com"], self.root)
        git(["config", "user.name", "Test"], self.root)
        (self.root / "src").mkdir()
        (self.root / "src/app.py").write_text("print('hi')\n")
        (self.root / "lib").mkdir()
        (self.root / "lib/helper.py").write_text("def helper(): pass\n")
        (self.root / "README.md").write_text("doc\n")
        (self.root / ".gitignore").write_text("config.local\n")
        (self.root / "config.local").write_text("secret=1\n")
        git(["add", "-A"], self.root)
        git(["commit", "-q", "-m", "initial"], self.root)
        self.base_commit = git(["rev-parse", "HEAD"], self.root)
        self.state = Path(self.scratch.name) / "state"
        self.env = patch.dict(os.environ, {"FSA_TASKS_DIR": str(self.state), "CODEX_THREAD_ID": "ev-session"})
        self.env.start()
        self.path = self.root / "TASKS.md"
        self.call("init", "--task", "D1|pending|Deliverable|")

    def tearDown(self):
        self.env.stop()
        self.scratch.cleanup()

    def call(self, command, *args, fails=False):
        argv = [command, "--root", str(self.root), "--file", "TASKS.md", "--session", "ev-session", *args]
        if fails:
            error = io.StringIO()
            with contextlib.redirect_stderr(error), self.assertRaises(SystemExit):
                tasks.main(argv)
            return error.getvalue()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(argv), 0)
        text = output.getvalue()
        return json.loads(text) if text.strip() else None

    def write_json(self, payload):
        path = Path(tempfile.mkstemp(dir=self.scratch.name, suffix=".json")[1])
        path.write_text(json.dumps(payload))
        return str(path)

    def basic_spec(self, **overrides):
        spec = {"kind": "code",
                "scope": {"paths": ["src/"], "dependencies_none": "self-contained script",
                          "rationale": "only src/app.py is exercised"},
                "criteria": [{"id": "AC1", "text": "script runs", "checks": ["C1"]}],
                "checks": {"C1": {"method": "command", "command": "true", "cwd": ".",
                                  "expect": {"none": "silent success"}}}}
        for key, value in overrides.items():
            if isinstance(value, dict) and key in spec:
                spec[key] = {**spec[key], **value}
            else:
                spec[key] = value
        return spec

    def accept(self, deliverable_id, spec, reason=None, fails=False):
        args = ["--id", deliverable_id, "--input", self.write_json(spec)]
        if reason:
            args += ["--reason", reason]
        return self.call("accept", *args, fails=fails)

    def run_check(self, deliverable_id, check_id, timeout=None, fails=False):
        args = ["run", "--id", deliverable_id, "--check", check_id]
        if timeout is not None:
            args += ["--timeout", str(timeout)]
        return self.call("check", *args, fails=fails)

    def start(self, deliverable_id, check_id, fails=False):
        return self.call("check", "start", "--id", deliverable_id, "--check", check_id, fails=fails)

    def finish(self, deliverable_id, check_id, run_id, result, evidence=(), reason=None, fails=False):
        args = ["finish", "--id", deliverable_id, "--check", check_id, "--run", run_id, "--result", result]
        for path in evidence:
            args += ["--evidence", path]
        if reason:
            args += ["--reason", reason]
        return self.call("check", *args, fails=fails)

    def verify(self, deliverable_id):
        return self.call("verify", "--id", deliverable_id, "--json")

    def done(self, deliverable_id, fails=False):
        return self.call("set", "--id", deliverable_id, "--status", "done", fails=fails)

    # -- spec validation -------------------------------------------------

    def test_accept_requires_at_least_one_criterion_check_and_command_for_code(self):
        self.assertIn("must reference known checks",
                       self.accept("D1", self.basic_spec(criteria=[{"id": "AC1", "text": "x", "checks": []}]),
                                   fails=True))
        bad = self.basic_spec()
        bad["checks"]["C2"] = {"method": "review"}
        bad["criteria"] = [{"id": "AC1", "text": "x", "checks": ["C1"]}]
        self.assertIn("not used by any criterion", self.accept("D1", bad, fails=True))
        self.assertIn("code deliverables need a command check",
                       self.accept("D1", self.basic_spec(
                           checks={"C1": {"method": "review"}},
                           criteria=[{"id": "AC1", "text": "x", "checks": ["C1"]}]), fails=True))

    def test_done_refused_without_spec_names_the_deliverable(self):
        self.assertIn("no evidence spec recorded", self.done("D1", fails=True))

    # -- the gate: missing / fail / unavailable / pass ------------------

    def test_missing_fail_and_unavailable_results_block_done(self):
        self.accept("D1", self.basic_spec())
        self.assertIn("no result recorded", self.done("D1", fails=True))
        self.run_check("D1", "C1")
        # Re-accept with the failing command so the result and the spec agree, then run it.
        self.accept("D1", self.basic_spec(checks={"C1": {"method": "command", "command": "false", "cwd": ".",
                                                          "expect": {"none": "silent"}}}), reason="swap command")
        self.run_check("D1", "C1")
        self.assertIn("fail", self.done("D1", fails=True))
        run = self.start("D1", "C1")
        fresh = self.root.parent / "unavailable.log"
        fresh.write_text("ci runner missing\n")
        self.assertIn("needs --reason", self.finish("D1", "C1", run["run"], "unavailable",
                                                      evidence=[str(fresh)], fails=True))
        self.finish("D1", "C1", run["run"], "unavailable", evidence=[str(fresh)], reason="ci runner missing")
        self.assertIn("unavailable", self.done("D1", fails=True))

    def test_pass_with_current_state_is_accepted_and_logged(self):
        self.accept("D1", self.basic_spec())
        self.run_check("D1", "C1")
        self.done("D1")
        self.assertIn("done_gate", self.path.read_text())
        self.assertEqual(tasks.load_tasks("ev-session", self.root)["items"][0]["status"], "done")

    # -- state fingerprint / staleness -----------------------------------

    def test_scoped_file_edit_after_finish_is_stale(self):
        self.accept("D1", self.basic_spec())
        self.run_check("D1", "C1")
        self.done("D1")
        (self.root / "src/app.py").write_text("print('changed')\n")
        report = self.verify("D1")
        self.assertFalse(report["ok"])
        self.assertTrue(any("stale" in reason for reason in report["blocking"]))

    def test_dependency_file_edit_is_stale(self):
        self.accept("D1", self.basic_spec(scope={"paths": ["src/"], "dependencies": ["lib/helper.py"],
                                                   "rationale": "src depends on lib/helper.py"}))
        self.run_check("D1", "C1")
        self.done("D1")
        (self.root / "lib/helper.py").write_text("def helper(): return 1\n")
        report = self.verify("D1")
        self.assertFalse(report["ok"])
        self.assertTrue(any("stale" in reason for reason in report["blocking"]))

    def test_gitignored_input_edit_is_stale(self):
        self.accept("D1", self.basic_spec(scope={"paths": ["src/"], "inputs": ["config.local"],
                                                   "dependencies_none": "none", "rationale": "reads config.local"}))
        self.run_check("D1", "C1")
        self.done("D1")
        (self.root / "config.local").write_text("secret=2\n")
        report = self.verify("D1")
        self.assertFalse(report["ok"])

    def test_env_value_change_is_stale(self):
        with patch.dict(os.environ, {"FSA_TEST_VAR": "a"}):
            self.accept("D1", self.basic_spec(scope={"paths": ["src/"], "env": ["FSA_TEST_VAR"],
                                                       "dependencies_none": "none", "rationale": "reads env"}))
            self.run_check("D1", "C1")
            self.done("D1")
        with patch.dict(os.environ, {"FSA_TEST_VAR": "b"}):
            report = self.verify("D1")
        self.assertFalse(report["ok"])

    def test_unscoped_file_edit_is_still_accepted(self):
        self.accept("D1", self.basic_spec())
        self.run_check("D1", "C1")
        (self.root / "README.md").write_text("changed\n")
        self.done("D1")
        self.assertEqual(tasks.load_tasks("ev-session", self.root)["items"][0]["status"], "done")

    def test_commit_of_unchanged_content_after_pass_stays_accepted(self):
        self.accept("D1", self.basic_spec())
        self.run_check("D1", "C1")
        git(["commit", "--allow-empty", "-q", "-m", "noop"], self.root)
        self.done("D1")
        self.assertEqual(tasks.load_tasks("ev-session", self.root)["items"][0]["status"], "done")

    def test_command_writing_a_scoped_file_is_refused_as_changed_during_verification(self):
        self.accept("D1", self.basic_spec(checks={"C1": {"method": "command", "cwd": ".",
                                                           "command": "echo x >> src/app.py",
                                                           "expect": {"none": "silent"}}}))
        self.run_check("D1", "C1")
        self.assertIn("changed during verification", self.done("D1", fails=True))

    # -- evidence integrity -----------------------------------------------

    def test_evidence_deleted_or_altered_is_refused(self):
        self.accept("D1", self.basic_spec())
        result = self.run_check("D1", "C1")
        Path(result["log"]).write_text("tampered\n")
        self.assertIn("evidence missing or altered", self.done("D1", fails=True))

    def test_log_not_written_during_the_run_refuses_finish(self):
        self.accept("D1", self.basic_spec())
        run = self.start("D1", "C1")
        stale_log = self.root / "stale.log"
        stale_log.write_text("old\n")
        os.utime(stale_log, (time.time() - 3600, time.time() - 3600))
        self.assertIn("not modified during the run",
                       self.finish("D1", "C1", run["run"], "pass", evidence=[str(stale_log)], fails=True))

    def test_evidence_for_command_check_inside_scope_is_refused(self):
        self.accept("D1", self.basic_spec())
        run = self.start("D1", "C1")
        self.assertIn("must lie outside the declared scope",
                       self.finish("D1", "C1", run["run"], "pass",
                                   evidence=[str(self.root / "src/app.py")], fails=True))

    # -- check run exit mapping -------------------------------------------

    def test_check_run_exit_mapping(self):
        self.accept("D1", self.basic_spec())
        self.assertEqual(self.run_check("D1", "C1")["result"], "pass")
        self.accept("D1", self.basic_spec(checks={"C1": {"method": "command", "command": "false", "cwd": ".",
                                                          "expect": {"none": "silent"}}}), reason="swap")
        self.assertEqual(self.run_check("D1", "C1")["result"], "fail")
        self.accept("D1", self.basic_spec(checks={"C1": {"method": "command", "command": "definitely-not-a-cmd-xyz",
                                                          "cwd": ".", "expect": {"none": "silent"}}}), reason="swap")
        self.assertEqual(self.run_check("D1", "C1")["result"], "unavailable")
        self.accept("D1", self.basic_spec(checks={"C1": {"method": "command", "command": "sleep 5", "cwd": ".",
                                                          "expect": {"none": "silent"}}}), reason="swap")
        result = self.run_check("D1", "C1", timeout=1)
        self.assertEqual(result["result"], "timeout")
        self.assertIn("latest result to be a fail",
                       self.call("check", "attribute", "--id", "D1", "--check", "C1", "--baseline", "B1",
                                 "--reason", "flaky", fails=True))

    def test_exit_zero_with_unmet_expectations_is_inconclusive(self):
        self.accept("D1", self.basic_spec(checks={"C1": {"method": "command", "command": "true", "cwd": ".",
                                                          "expect": {"patterns": ["NEVER_PRESENT"]}}}))
        self.assertEqual(self.run_check("D1", "C1")["result"], "inconclusive")

    # -- spec changes and reasons ------------------------------------------

    def test_check_command_change_after_pass_invalidates_old_result(self):
        self.accept("D1", self.basic_spec())
        self.run_check("D1", "C1")
        self.done("D1")
        self.accept("D1", self.basic_spec(checks={"C1": {"method": "command", "command": "true -x", "cwd": ".",
                                                          "expect": {"none": "silent"}}}), reason="tighten command")
        report = self.verify("D1")
        self.assertFalse(report["ok"])
        self.assertIn("stale (definition changed)", report["checks"]["C1"]["status"])

    def test_removing_a_check_with_a_result_needs_reason(self):
        spec = self.basic_spec()
        spec["checks"]["C2"] = {"method": "review"}
        spec["criteria"].append({"id": "AC2", "text": "reviewed", "checks": ["C2"]})
        self.accept("D1", spec)
        self.run_check("D1", "C1")
        outside = self.root.parent / "review.txt"
        outside.write_text("looked fine\n")
        run = self.start("D1", "C2")
        self.finish("D1", "C2", run["run"], "pass", evidence=[str(outside)])
        narrowed = self.basic_spec()
        self.assertIn("requires --reason", self.accept("D1", narrowed, fails=True))
        self.accept("D1", narrowed, reason="C2 no longer needed")
        self.assertIn("C2 no longer needed", self.path.read_text())

    def test_scope_change_invalidates_affected_results_and_needs_reason(self):
        self.accept("D1", self.basic_spec())
        self.run_check("D1", "C1")
        self.done("D1")
        narrower = self.basic_spec(scope={"paths": ["src/app.py"], "dependencies_none": "self-contained script",
                                           "rationale": "only the entry point matters now"})
        self.assertIn("requires --reason", self.accept("D1", narrower, fails=True))
        self.accept("D1", narrower, reason="narrow scope to the entry point")
        report = self.verify("D1")
        self.assertFalse(report["ok"])

    # -- baseline attribution ----------------------------------------------

    def failing_check_with_signature(self, signature, reason=None):
        self.accept("D1", self.basic_spec(checks={"C1": {"method": "command", "cwd": ".",
                                                           "command": f"echo {signature}; false",
                                                           "expect": {"none": "silent"}}}), reason=reason)
        self.run_check("D1", "C1")

    def test_baseline_attribution_matching_command_is_accepted(self):
        self.failing_check_with_signature("KNOWN_FLAKE")
        log = self.root.parent / "baseline.log"
        log.write_text("prior run\nKNOWN_FLAKE\n")
        self.call("baseline", "--id", "B1", "--command", "echo KNOWN_FLAKE; false", "--ref", self.base_commit,
                  "--log", str(log), "--signature", "KNOWN_FLAKE", "--reason", "known infra flake")
        self.call("check", "attribute", "--id", "D1", "--check", "C1", "--baseline", "B1", "--reason", "same flake")
        self.done("D1")
        summary = tasks.load_tasks("ev-session", self.root)
        self.assertEqual(summary["items"][0]["completion"], "evidence_with_baseline")
        block = task_evidence.load_block(self.path.read_text())
        result = block["deliverables"]["D1"]["results"]["C1"]
        self.assertEqual(result["result"], "baseline")
        self.assertEqual(result["attributed"]["result"]["result"], "fail")
        self.assertEqual(result["attributed"]["baseline"], "B1")
        self.assertEqual(block["baselines"]["B1"]["log"], str(log.resolve()))

    def test_attribution_refuses_when_log_lacks_baseline_signature(self):
        self.failing_check_with_signature("NEW_FAILURE")
        log = self.root.parent / "baseline.log"
        log.write_text("prior run\nKNOWN_FLAKE\n")
        self.call("baseline", "--id", "B1", "--command", "echo NEW_FAILURE; false", "--ref", self.base_commit,
                  "--log", str(log), "--signature", "KNOWN_FLAKE", "--reason", "known infra flake")
        self.assertIn("missing baseline signatures",
                       self.call("check", "attribute", "--id", "D1", "--check", "C1", "--baseline", "B1",
                                 "--reason", "same flake", fails=True))
        block = task_evidence.load_block(self.path.read_text())
        self.assertEqual(block["deliverables"]["D1"]["results"]["C1"]["result"], "fail")

    def test_attribution_refuses_mismatched_command_missing_baseline_and_pass(self):
        self.accept("D1", self.basic_spec())
        self.run_check("D1", "C1")
        self.assertIn("latest result to be a fail",
                       self.call("check", "attribute", "--id", "D1", "--check", "C1", "--baseline", "none",
                                 "--reason", "x", fails=True))
        self.failing_check_with_signature("OTHER_SIG", reason="swap to a failing command")
        self.assertIn("Unknown baseline",
                       self.call("check", "attribute", "--id", "D1", "--check", "C1", "--baseline", "missing",
                                 "--reason", "x", fails=True))
        log = self.root.parent / "mismatch.log"
        log.write_text("OTHER_SIG\n")
        self.call("baseline", "--id", "B1", "--command", "some other command", "--ref", self.base_commit,
                  "--log", str(log), "--signature", "OTHER_SIG", "--reason", "mismatch")
        self.assertIn("does not match",
                       self.call("check", "attribute", "--id", "D1", "--check", "C1", "--baseline", "B1",
                                 "--reason", "x", fails=True))

    def test_baseline_requires_signature_in_log_and_ancestor_ref(self):
        log = self.root.parent / "missing-sig.log"
        log.write_text("nothing relevant\n")
        self.assertIn("missing signatures",
                       self.call("baseline", "--id", "B1", "--command", "false", "--ref", self.base_commit,
                                  "--log", str(log), "--signature", "ABSENT", "--reason", "x", fails=True))
        (self.root / "future.txt").write_text("x\n")
        git(["add", "future.txt"], self.root)
        git(["commit", "-q", "-m", "future"], self.root)
        future = git(["rev-parse", "HEAD"], self.root)
        git(["reset", "-q", "--hard", self.base_commit], self.root)
        log.write_text("PRESENT\n")
        self.assertIn("ancestor",
                       self.call("baseline", "--id", "B1", "--command", "false", "--ref", future,
                                  "--log", str(log), "--signature", "PRESENT", "--reason", "x", fails=True))

    def test_attribution_refused_for_timeout_and_unavailable(self):
        self.accept("D1", self.basic_spec(checks={"C1": {"method": "command", "command": "sleep 5", "cwd": ".",
                                                          "expect": {"none": "silent"}}}))
        self.run_check("D1", "C1", timeout=1)
        self.assertIn("latest result to be a fail",
                       self.call("check", "attribute", "--id", "D1", "--check", "C1", "--baseline", "B1",
                                 "--reason", "x", fails=True))

    # -- reopening and repair -----------------------------------------------

    def test_fail_on_done_deliverable_reopens_it_with_a_logged_reason(self):
        self.accept("D1", self.basic_spec())
        self.run_check("D1", "C1")
        self.done("D1")
        self.accept("D1", self.basic_spec(checks={"C1": {"method": "command", "command": "false", "cwd": ".",
                                                          "expect": {"none": "silent"}}}), reason="swap")
        self.run_check("D1", "C1")
        summary = tasks.load_tasks("ev-session", self.root)
        self.assertEqual(summary["items"][0]["status"], "in_progress")
        self.assertEqual(summary["deliverables"]["total"], 1)
        self.assertIn("check C1 fail", self.path.read_text())

    def test_repair_fail_then_fix_then_pass_keeps_the_same_row(self):
        self.accept("D1", self.basic_spec(checks={"C1": {"method": "command", "command": "false", "cwd": ".",
                                                          "expect": {"none": "silent"}}}))
        self.run_check("D1", "C1")
        self.assertIn("fail", self.done("D1", fails=True))
        self.accept("D1", self.basic_spec(), reason="fixed the command")
        self.run_check("D1", "C1")
        self.done("D1")
        summary = tasks.load_tasks("ev-session", self.root)
        self.assertEqual(summary["deliverables"]["total"], 1)
        self.assertEqual(summary["items"][0]["status"], "done")

    def test_old_result_state_fields_are_never_restamped(self):
        self.accept("D1", self.basic_spec())
        self.run_check("D1", "C1")
        self.done("D1")
        block = task_evidence.load_block(self.path.read_text())
        before = dict(block["deliverables"]["D1"]["results"]["C1"])
        (self.root / "README.md").write_text("more changes\n")
        self.verify("D1")
        after = task_evidence.load_block(self.path.read_text())["deliverables"]["D1"]["results"]["C1"]
        self.assertEqual(before["state_before"], after["state_before"])
        self.assertEqual(before["state_after"], after["state_after"])
        self.assertEqual(before["finished_at"], after["finished_at"])

    # -- non-command kinds ---------------------------------------------------

    def test_docs_deliverable_needs_no_command_check(self):
        (self.root / "docs").mkdir()
        doc = self.root / "docs/design.md"
        doc.write_text("# Design\n")
        git(["add", "-A"], self.root)
        git(["commit", "-q", "-m", "docs"], self.root)
        spec = {"kind": "docs",
                "scope": {"paths": ["docs/design.md"], "rationale": "the design document itself"},
                "criteria": [{"id": "AC1", "text": "design is current", "checks": ["C1"]}],
                "checks": {"C1": {"method": "document"}}}
        self.accept("D1", spec)
        run = self.start("D1", "C1")
        self.finish("D1", "C1", run["run"], "pass", evidence=[str(doc)])
        self.done("D1")
        summary = tasks.load_tasks("ev-session", self.root)
        self.assertEqual(summary["items"][0]["status"], "done")
        self.assertEqual(summary["items"][0]["completion"], "evidence")
        # The ledger's own write must not stale a document result scoped outside it.
        report = self.verify("D1")
        self.assertTrue(report["ok"])

    def test_investigation_deliverable_accepts_analysis_evidence(self):
        (self.root / "notes.md").write_text("findings\n")
        git(["add", "-A"], self.root)
        git(["commit", "-q", "-m", "notes"], self.root)
        spec = {"kind": "investigation",
                "scope": {"paths": ["notes.md"], "rationale": "the report itself"},
                "criteria": [{"id": "AC1", "text": "conclusion drawn", "checks": ["C1"]}],
                "checks": {"C1": {"method": "analysis"}}}
        self.accept("D1", spec)
        run = self.start("D1", "C1")
        self.finish("D1", "C1", run["run"], "pass", evidence=[str(self.root / "notes.md")])
        self.done("D1")
        self.assertEqual(tasks.load_tasks("ev-session", self.root)["items"][0]["status"], "done")

    # -- external runs -------------------------------------------------------

    def test_external_finish_without_start_unknown_duplicate_and_definition_change(self):
        self.accept("D1", self.basic_spec())
        self.assertIn("already finished or unknown", self.finish("D1", "C1", "not-a-real-run", "pass", fails=True))
        run = self.start("D1", "C1")
        log = self.root.parent / "external.log"
        log.write_text("ran fine\n")
        self.finish("D1", "C1", run["run"], "pass", evidence=[str(log)])
        self.assertIn("already finished or unknown", self.finish("D1", "C1", run["run"], "pass",
                                                        evidence=[str(log)], fails=True))
        block = task_evidence.load_block(self.path.read_text())
        self.assertNotIn(run["run"], block["runs"])
        run2 = self.start("D1", "C1")
        self.accept("D1", self.basic_spec(checks={"C1": {"method": "command", "command": "true -z", "cwd": ".",
                                                          "expect": {"none": "silent"}}}), reason="definition change")
        self.assertIn("check definition changed", self.finish("D1", "C1", run2["run"], "pass",
                                                                evidence=[str(log)], fails=True))

    def test_attested_result_is_labelled_in_verify(self):
        self.accept("D1", self.basic_spec())
        run = self.start("D1", "C1")
        log = self.root.parent / "attested.log"
        log.write_text("ok\n")
        self.finish("D1", "C1", run["run"], "pass", evidence=[str(log)])
        report = self.verify("D1")
        self.assertIn("attested", report["checks"]["C1"]["status"])

    def test_ordering_rule_latest_started_at_wins_regardless_of_finish_order(self):
        self.accept("D1", self.basic_spec())
        run_a = self.start("D1", "C1")
        time.sleep(0.01)
        run_b = self.start("D1", "C1")
        log_a, log_b = self.root.parent / "a.log", self.root.parent / "b.log"
        log_a.write_text("a\n")
        log_b.write_text("b\n")
        self.finish("D1", "C1", run_b["run"], "pass", evidence=[str(log_b)])
        self.finish("D1", "C1", run_a["run"], "fail", evidence=[str(log_a)])
        block = task_evidence.load_block(self.path.read_text())
        self.assertEqual(block["deliverables"]["D1"]["results"]["C1"]["result"], "pass")
        text = self.path.read_text()
        self.assertEqual(text.count("check_finish"), 2)

    def test_concurrent_finishes_both_keep_a_log_line(self):
        self.accept("D1", self.basic_spec())
        run_a = self.start("D1", "C1")
        run_b = self.start("D1", "C1")
        log_a, log_b = self.root.parent / "ca.log", self.root.parent / "cb.log"
        log_a.write_text("a\n")
        log_b.write_text("b\n")
        children = [subprocess.Popen([sys.executable, str(CLI), "check", "--root", str(self.root), "--file",
                                       "TASKS.md", "--session", "ev-session", "finish", "--id", "D1", "--check", "C1",
                                       "--run", run_id, "--result", result, "--evidence", str(log)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    for run_id, result, log in ((run_a["run"], "pass", log_a), (run_b["run"], "fail", log_b))]
        for child in children:
            _, error = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, error)
        self.assertEqual(self.path.read_text().count("check_finish"), 2)

    # -- legacy / step compatibility -----------------------------------------

    def test_legacy_ledger_and_step_rows_refuse_evidence_commands(self):
        legacy_root = Path(self.scratch.name) / "legacy"
        legacy_root.mkdir()
        git(["init", "-q"], legacy_root)
        git(["config", "user.email", "a@example.com"], legacy_root)
        git(["config", "user.name", "Test"], legacy_root)
        (legacy_root / "f").write_text("x\n")
        git(["add", "-A"], legacy_root)
        git(["commit", "-q", "-m", "x"], legacy_root)
        argv = ["init", "--root", str(legacy_root), "--file", "TASKS.md", "--session", "ev-session",
                "--format", "legacy", "--task", "L1|pending|Legacy|"]
        tasks.main(argv)
        error = io.StringIO()
        with contextlib.redirect_stderr(error), self.assertRaises(SystemExit):
            tasks.main(["accept", "--root", str(legacy_root), "--file", "TASKS.md", "--session", "ev-session",
                        "--id", "L1", "--input", self.write_json(self.basic_spec())])
        self.assertIn("v2 ledger", error.getvalue())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            tasks.main(["set", "--root", str(legacy_root), "--file", "TASKS.md", "--session", "ev-session",
                        "--id", "L1", "--status", "verifying"])
        process = tasks.main(["set", "--root", str(legacy_root), "--file", "TASKS.md", "--session", "ev-session",
                               "--id", "L1", "--status", "done"])
        self.assertEqual(process, 0)

    def test_step_row_refuses_evidence_commands(self):
        self.call("add", "--parent", "D1", "--task", "R1|pending|Step|")
        self.assertIn("deliverables only", self.accept("R1", self.basic_spec(), fails=True))
        self.assertIn("deliverables only", self.call("verify", "--id", "R1", fails=True))

    # -- downgrade and malformed block ---------------------------------------

    def test_downgrade_refuses_while_an_evidence_block_exists(self):
        self.accept("D1", self.basic_spec())
        self.assertIn("evidence block exists", self.call("downgrade", fails=True))

    def test_malformed_evidence_block_is_a_clear_error_but_show_still_works(self):
        self.accept("D1", self.basic_spec())
        text = self.path.read_text()
        corrupted = text.replace('"schema": 1', '"schema": 1, "deliverables": "not an object"')
        self.path.write_text(corrupted)
        summary = tasks.load_tasks("ev-session", self.root)
        self.assertIn("evidence_error", summary)
        self.assertIn("evidence_error", self.call("show", "--json"))
        self.assertIn("Evidence block", self.accept("D1", self.basic_spec(), fails=True))
        self.call("set", "--id", "D1", "--note", "still works")
        self.assertEqual(tasks.load_tasks("ev-session", self.root)["items"][0]["note"], "still works")

    def test_reasoned_reopen_works_with_a_malformed_evidence_block(self):
        self.accept("D1", self.basic_spec())
        self.run_check("D1", "C1")
        self.done("D1")
        text = self.path.read_text()
        corrupted = text.replace('"schema": 1', '"schema": 1, "deliverables": "not an object"')
        self.path.write_text(corrupted)
        self.assertIn("requires set --reason", self.call("set", "--id", "D1", "--status", "in_progress", fails=True))
        self.call("set", "--id", "D1", "--status", "in_progress", "--reason", "repair despite corruption")
        after = self.path.read_text()
        self.assertEqual(tasks.load_tasks("ev-session", self.root)["items"][0]["status"], "in_progress")
        def block_bytes(text):
            start = text.index(task_evidence.EVID_START)
            end = text.index(task_evidence.EVID_END) + len(task_evidence.EVID_END)
            return text[start:end]
        self.assertEqual(block_bytes(after), block_bytes(corrupted))
        self.assertIn('D1 evidence_malformed action="reopen"', after)
        self.assertIn("Evidence block", self.done("D1", fails=True))
        self.assertIn("Evidence block", self.call("check", "start", "--id", "D1", "--check", "C1", fails=True))
        self.assertIn("Evidence block", self.accept("D1", self.basic_spec(), fails=True))
        summary = tasks.load_tasks("ev-session", self.root)
        self.assertIn("evidence_error", summary)
        self.assertIn("evidence_error", self.call("show", "--json"))

    def test_completion_kind_unrecorded_for_pre_l2_done_rows(self):
        other_session = "ev-session-2"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(["init", "--root", str(self.root), "--file", "docs/tasks/pre-l2.md",
                                          "--session", other_session, "--format", "legacy",
                                          "--task", "D9|done|Pre-existing|"]), 0)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tasks.main(["upgrade", "--root", str(self.root), "--file", "docs/tasks/pre-l2.md",
                                          "--session", other_session]), 0)
        summary = tasks.load_tasks(other_session, self.root)
        self.assertEqual(summary["items"][0]["completion"], "unrecorded")
        self.assertEqual(summary["deliverables"]["completion"], {"evidence": 0, "evidence_with_baseline": 0,
                                                                   "unrecorded": 1})

    # -- L2 E1 repair r1 (lead audit findings) --------------------------------

    def test_finish_rejects_external_baseline_and_report_never_crashes_on_missing_attribution(self):
        self.accept("D1", self.basic_spec())
        run = self.start("D1", "C1")
        error = self.finish("D1", "C1", run["run"], "baseline", fails=True)
        self.assertIn("invalid choice", error)
        log = self.root.parent / "f1.log"
        log.write_text("ok\n")
        self.finish("D1", "C1", run["run"], "pass", evidence=[str(log)])
        text = self.path.read_text()
        block = task_evidence.load_block(text)
        block["deliverables"]["D1"]["results"]["C1"]["result"] = "baseline"
        self.path.write_text(task_evidence.splice_block(text, task_evidence.render_block(block)))
        blocked = self.done("D1", fails=True)
        self.assertNotIn("Traceback", blocked)
        self.assertIn("baseline result without attribution", blocked)

    def test_weakened_expect_or_edited_criterion_text_needs_reason(self):
        self.accept("D1", self.basic_spec())
        self.run_check("D1", "C1")
        self.done("D1")
        reworded_expect = self.basic_spec(checks={"C1": {"method": "command", "command": "true", "cwd": ".",
                                                           "expect": {"none": "different justification"}}})
        self.assertIn("requires --reason", self.accept("D1", reworded_expect, fails=True))
        self.accept("D1", reworded_expect, reason="reworded expectation")
        self.run_check("D1", "C1")
        self.done("D1")
        reworded_criterion = self.basic_spec(criteria=[{"id": "AC1", "text": "different wording", "checks": ["C1"]}])
        self.assertIn("requires --reason", self.accept("D1", reworded_criterion, fails=True))

    def test_completion_stays_unrecorded_until_the_done_gate_actually_passes(self):
        self.accept("D1", self.basic_spec())
        self.run_check("D1", "C1")
        text = self.path.read_text()
        items, start, end = tasks._parse(text)
        version, _width = tasks._format(text)
        for item in items:
            if item["id"] == "D1":
                item["status"] = "done"
        self.path.write_text(tasks._mutated(text, items, start, end, version))
        summary = tasks.load_tasks("ev-session", self.root)
        self.assertEqual(summary["items"][0]["status"], "done")
        self.assertEqual(summary["items"][0]["completion"], "unrecorded")
        self.assertTrue(self.verify("D1")["ok"])
        self.done("D1")
        self.assertEqual(tasks.load_tasks("ev-session", self.root)["items"][0]["completion"], "evidence")

    def test_changing_one_checks_command_does_not_stale_other_checks(self):
        spec = self.basic_spec()
        spec["checks"]["C2"] = {"method": "command", "command": "true", "cwd": ".", "expect": {"none": "silent"}}
        spec["criteria"].append({"id": "AC2", "text": "second check runs", "checks": ["C2"]})
        self.accept("D1", spec)
        self.run_check("D1", "C1")
        self.run_check("D1", "C2")
        self.done("D1")
        changed = self.basic_spec()
        changed["checks"]["C1"]["command"] = "true -x"
        changed["checks"]["C2"] = {"method": "command", "command": "true", "cwd": ".", "expect": {"none": "silent"}}
        changed["criteria"].append({"id": "AC2", "text": "second check runs", "checks": ["C2"]})
        self.accept("D1", changed, reason="tighten C1 only")
        report = self.verify("D1")
        self.assertIn("stale (definition changed)", report["checks"]["C1"]["status"])
        self.assertEqual(report["checks"]["C2"]["status"], "accepted")

    def test_timeout_kills_the_whole_process_group_including_background_children(self):
        marker = self.root.parent / "child.pid"
        spec = self.basic_spec(checks={"C1": {"method": "command", "cwd": ".",
                                               "command": f"(sleep 30 & echo $! > {marker}); sleep 30",
                                               "expect": {"none": "silent"}}})
        self.accept("D1", spec)
        result = self.run_check("D1", "C1", timeout=1)
        self.assertEqual(result["result"], "timeout")
        child_pid = int(marker.read_text().strip())
        with self.assertRaises(ProcessLookupError):
            os.kill(child_pid, 0)

    def test_refused_log_location_leaves_no_open_run(self):
        self.accept("D1", self.basic_spec())
        bad_log = self.root / "src" / "evil.log"
        error = self.call("check", "run", "--id", "D1", "--check", "C1", "--log", str(bad_log), fails=True)
        self.assertIn("outside the declared scope", error)
        self.assertEqual(task_evidence.load_block(self.path.read_text())["runs"], {})

    def test_finish_prunes_the_run_from_the_block(self):
        self.accept("D1", self.basic_spec())
        run = self.start("D1", "C1")
        log = self.root.parent / "prune.log"
        log.write_text("ok\n")
        self.finish("D1", "C1", run["run"], "pass", evidence=[str(log)])
        self.assertNotIn(run["run"], task_evidence.load_block(self.path.read_text())["runs"])
        self.assertIn("already finished or unknown",
                       self.finish("D1", "C1", run["run"], "pass", evidence=[str(log)], fails=True))

    def test_baseline_log_hash_is_raw_bytes_and_altered_log_blocks(self):
        self.failing_check_with_signature("KNOWN_FLAKE")
        log = self.root.parent / "baseline8.log"
        log.write_bytes("prior run\nKNOWN_FLAKE\n".encode() + b"\xff")
        self.call("baseline", "--id", "B1", "--command", "echo KNOWN_FLAKE; false", "--ref", self.base_commit,
                  "--log", str(log), "--signature", "KNOWN_FLAKE", "--reason", "known infra flake")
        block = task_evidence.load_block(self.path.read_text())
        self.assertEqual(block["baselines"]["B1"]["log_sha256"], hashlib.sha256(log.read_bytes()).hexdigest())
        self.call("check", "attribute", "--id", "D1", "--check", "C1", "--baseline", "B1", "--reason", "same flake")
        log.write_text("tampered\n")
        report = self.verify("D1")
        self.assertFalse(report["ok"])
        self.assertTrue(any("baseline log missing or altered" in reason for reason in report["blocking"]))

    def test_non_winning_fail_finish_still_reopens_a_done_deliverable(self):
        self.accept("D1", self.basic_spec())
        run_a = self.start("D1", "C1")
        time.sleep(0.01)
        run_b = self.start("D1", "C1")
        log_a, log_b = self.root.parent / "na.log", self.root.parent / "nb.log"
        log_a.write_text("a\n")
        log_b.write_text("b\n")
        self.finish("D1", "C1", run_b["run"], "pass", evidence=[str(log_b)])
        self.done("D1")
        self.finish("D1", "C1", run_a["run"], "fail", evidence=[str(log_a)])
        block = task_evidence.load_block(self.path.read_text())
        self.assertEqual(block["deliverables"]["D1"]["results"]["C1"]["result"], "pass")
        self.assertEqual(tasks.load_tasks("ev-session", self.root)["items"][0]["status"], "in_progress")
        self.assertIn("check C1 fail", self.path.read_text())

    def test_parser_always_registers_evidence_commands(self):
        parser = tasks._parser()
        command_action = next(a for a in parser._subparsers._group_actions if a.dest == "command")
        self.assertTrue(set(task_evidence.COMMANDS).issubset(command_action.choices))

    def test_check_run_default_timeout_is_540(self):
        self.assertEqual(task_evidence.DEFAULT_TIMEOUT, 540)

    def test_check_run_accepts_root_file_session_before_or_after_the_action(self):
        self.accept("D1", self.basic_spec())
        shared = ["--root", str(self.root), "--file", "TASKS.md", "--session", "ev-session"]
        before = ["check", *shared, "run", "--id", "D1", "--check", "C1"]
        after = ["check", "run", "--id", "D1", "--check", "C1", *shared]
        for argv in (before, after):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(tasks.main(argv), 0)
            self.assertEqual(json.loads(output.getvalue())["result"], "pass")


if __name__ == "__main__":
    unittest.main()
