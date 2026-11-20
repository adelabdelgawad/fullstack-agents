"""Isolated multi-request scenario across a handover: requests, a revision bump against a fake worker run, scoped
controls and a saved report must all still be readable, unlifted and unrerun from a brand new session after a
SessionStart(clear) with no prompt hook. See docs/TASK_LIFECYCLE_DESIGN.md §15 (FSA1 unit E, item 4)."""
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
import task_controls
import task_lifecycle
import task_revisions

SPEC = importlib.util.spec_from_file_location("task_tracking_coordination_scenario_test", LIB / "task_tracking.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)

S1, S2 = "scenario-s1", "scenario-s2"


def git(args, cwd):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


class CoordinationScenarioTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-scenario-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name) / "repo"
        self.root.mkdir()
        git(["init", "-q"], self.root)
        git(["config", "user.email", "a@example.com"], self.root)
        git(["config", "user.name", "Test"], self.root)
        (self.root / "README.md").write_text("doc\n")
        git(["add", "-A"], self.root)
        git(["commit", "-q", "-m", "initial"], self.root)
        self.runs = Path(self.scratch.name) / "runs"
        self.runs.mkdir()
        self.env = patch.dict(os.environ, {
            "FSA_TASKS_DIR": str(Path(self.scratch.name) / "tasks"),
            "FSA_STOP_GUARD_DIR": str(Path(self.scratch.name) / "guard"),
            "CLAUDE_CONFIG_DIR": str(Path(self.scratch.name) / "config"),
            "FSA_TEAM_DEPLOY_REGEX": r"deploy\.sh",
            "FSA_CODEX_RUNS_DIR": str(self.runs)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def hook(self, prompt, session=S1, host_id=None):
        return {"session_id": session, "cwd": str(self.root), "prompt": prompt, "prompt_id": host_id}

    def capture(self, prompt, session=S1, host_id=None):
        return request_inbox.capture(self.hook(prompt, session=session, host_id=host_id))

    def invoke(self, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(argv), 0)
        text = output.getvalue()
        lines = [line for line in text.splitlines() if line.strip()]
        json_line = next((line for line in lines if line.startswith("{")), None)
        return json.loads(json_line) if json_line else None

    def run_command(self, command, *args, session=S1):
        return self.invoke([command, "--root", str(self.root), "--session", session, *args])

    def save_report(self, path, request, rows, session=S1):
        return self.invoke(["report", "--root", str(self.root), "--session", session, "--file", str(path), "save",
                             "--request", request, "--rows", rows])

    def classify(self, rid, as_class, rows=None, session=S1):
        args = ["--id", rid, "--as", as_class]
        if rows:
            args += ["--rows", rows]
        self.run_command("request", "classify", *args, session=session)

    def ledger(self):
        argv = ["init", "--root", str(self.root), "--file", "TASKS.md", "--session", S1,
                "--task", "X|in_progress|Row X|", "--task", "Y|in_progress|Row Y|"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tasks.main(argv), 0)

    def write_run(self, run_id, instruction_revision):
        meta = {"schema": 2, "cwd": str(self.root), "engine": "claude", "task_file": "TASKS.md", "task_row": "X",
                "instruction_revision": instruction_revision}
        (self.runs / f"{run_id}.meta.json").write_text(json.dumps(meta))

    def stale_dispatcher_result(self, touched):
        """Same shape codex-task.sh writes for a stale-revision finish: state stale_revision, touched kept."""
        return {"state": "stale_revision", "engine_exit": 0, "details": ["stale_revision"], "touched": touched,
                "outside": [], "review": [], "liveness_after": {"state": "uncertain"}, "ownership": "free",
                "started": "2026-11-20T00:00:00Z", "ended": "2026-11-20T00:05:00Z"}

    def control_snapshot(self, controls):
        return sorted(({"id": c["id"], "kind": c["kind"], "scope": c["scope"], "quote": c["quote"],
                         "lifted": c["lifted"]} for c in controls), key=lambda c: c["id"])

    def capture_and_classify_requests(self):
        r1 = self.capture("Please investigate why the row X build is failing.", host_id="turn-1")
        r2 = self.capture("Also pause the whole project for now while we investigate, and queue the cleanup task.",
                           host_id="h2")
        self.classify(r2, "queued")
        r3 = self.capture("Please also pause row Y specifically until further notice, that one can wait.",
                           host_id="h3")
        self.classify(r3, "queued")
        # Same prompt_id as the still-running turn (r1), different text: a mid-turn message (item 1), not a dup.
        r4 = self.capture("Also, no deploy until QA signs off on this fix.", host_id="turn-1")
        self.classify(r4, "other")
        self.assertNotEqual(r1, r4)
        return r1, r2, r3, r4

    def apply_revisions_and_controls(self, r1, r2, r3, r4):
        self.write_run("run-x1", instruction_revision=0)
        self.run_command("revise", "--rows", "X", "--request", r1, "--kind", "correction")
        self.run_command("control", "set", "--kind", "pause", "--scope", "project", "--request", r2,
                          "--quote", "pause the whole project for now")
        self.run_command("control", "set", "--kind", "pause", "--scope", "rows", "--rows", "Y", "--request", r3,
                          "--quote", "pause row Y specifically")
        self.run_command("revise", "--rows", "Y", "--request", r3, "--kind", "cancel")
        self.run_command("control", "set", "--kind", "deploy_hold", "--scope", "project", "--request", r4,
                          "--quote", "no deploy until QA signs off")
        return self.control_snapshot(self.run_command("control", "list")["controls"])

    def dispatch_and_refuse_stale_worker(self):
        # The fake worker finishes only after the revision bump above: its evidence must be refused, not applied.
        (self.root / "app.py").write_text("changed by worker\n")
        result_path = self.runs / "run-x1.result.json"
        result = self.stale_dispatcher_result(touched=["app.py"])
        result_path.write_text(json.dumps(result))
        reason = task_revisions.refuse_worker_evidence(str(self.root), result_path, ["X"])
        self.assertIsNotNone(reason)
        self.assertIn("stale_revision", reason)
        self.assertEqual((self.root / "app.py").read_text(), "changed by worker\n")  # changes kept, not reverted
        on_disk = json.loads(result_path.read_text())
        self.assertEqual(on_disk["touched"], ["app.py"])  # kept, not cleared by the refusal

    def save_investigation_report(self, r1):
        report_file = Path(self.scratch.name) / "report.md"
        report_file.write_text("Investigation summary: CI failure root-caused to a flaky test.\n")
        saved = self.save_report(report_file, r1, "X")
        self.assertTrue(saved["created"])
        # Never emitted: result_outbox.record_emission is never called with a final reply carrying its marker.
        return report_file, saved["id"]

    def assert_requests_after_handover(self, r1, r2, r3, r4):
        listed = self.run_command("request", "list", session=S2)["requests"]
        states = {entry["id"]: entry["class"] for entry in listed}
        self.assertEqual(states, {r1: "unclassified", r2: "queued", r3: "queued", r4: "other"})
        self.assertFalse(self.run_command("request", "show", "--id", r1, session=S2).get("mid_turn"))
        self.assertTrue(self.run_command("request", "show", "--id", r4, session=S2)["mid_turn"])

    def assert_controls_after_handover(self, controls_before):
        controls = self.run_command("control", "list", session=S2)["controls"]
        self.assertEqual(len(controls), 3)
        by_kind_scope = {(c["kind"], c["scope"]["level"]) for c in controls}
        self.assertEqual(by_kind_scope, {("pause", "project"), ("pause", "rows"), ("deploy_hold", "project")})
        self.assertFalse(any(c["kind"] == "approval" for c in controls))
        self.assertEqual(self.control_snapshot(controls), controls_before)
        self.assertIsNotNone(task_controls.active_deploy_hold(str(self.root), S2))
        block = deploy_hold.on_bash({"session_id": S2, "cwd": str(self.root), "tool_input": {"command": "deploy.sh"}})
        self.assertIsNotNone(block)

    def assert_runs_and_reports_after_handover(self, report_file, report_id, r1, output):
        runs = task_revisions.runs_for_row(str(self.root), "TASKS.md", "X")
        self.assertIn("run-x1", [r["run"] for r in runs])  # still unreconciled: no --reconciled was ever recorded

        reports = self.run_command("report", "list", session=S2)["reports"]
        self.assertEqual([r["state"] for r in reports if r["id"] == report_id], ["prepared"])
        shown = io.StringIO()
        with contextlib.redirect_stdout(shown):
            self.assertEqual(tasks.main(["report", "--root", str(self.root), "--session", S2, "show",
                                          "--id", report_id]), 0)
        self.assertIn("Investigation summary", shown.getvalue())
        resaved = self.save_report(report_file, r1, "X", session=S2)
        self.assertEqual(resaved, {"id": report_id, "created": False})

        self.assertIn("Coordination:", output)
        self.assertIn(f'{r1} unclassified "Please investigate why the row X build is failing."', output)
        self.assertIn(f"{report_id} prepared", output)
        self.assertNotIn("capture failed", output)

    def test_scenario_survives_a_clear_handover_to_a_new_session(self):
        self.ledger()
        r1, r2, r3, r4 = self.capture_and_classify_requests()
        controls_before = self.apply_revisions_and_controls(r1, r2, r3, r4)
        self.dispatch_and_refuse_stale_worker()
        report_file, report_id = self.save_investigation_report(r1)

        # Handover: a brand new session id, SessionStart(clear) only, no UserPromptSubmit hook at all.
        output = task_lifecycle._session_start({"session_id": S2, "source": "clear", "cwd": str(self.root)})

        self.assert_requests_after_handover(r1, r2, r3, r4)
        self.assert_controls_after_handover(controls_before)
        self.assert_runs_and_reports_after_handover(report_file, report_id, r1, output)


if __name__ == "__main__":
    unittest.main()
