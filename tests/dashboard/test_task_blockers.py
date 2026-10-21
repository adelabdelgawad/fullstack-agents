"""Typed blockers and derived session state for v2 ledgers (docs/TASK_LIFECYCLE_DESIGN.md §13, §14.6)."""
import contextlib
from datetime import datetime, timedelta, timezone
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
SPEC = importlib.util.spec_from_file_location("task_tracking_blockers", LIB / "task_tracking.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)
import task_blockers
import task_checkpoint
import prompt_history
import plan_usage


def git(args, cwd):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


SESSION = "bk-session"


class TaskBlockersTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-blockers-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name) / "repo"
        self.root.mkdir()
        git(["init", "-q"], self.root)
        git(["config", "user.email", "a@example.com"], self.root)
        git(["config", "user.name", "Test"], self.root)
        (self.root / "README.md").write_text("doc\n")
        git(["add", "-A"], self.root)
        git(["commit", "-q", "-m", "initial"], self.root)
        self.state_dir = Path(self.scratch.name) / "state"
        self.env = patch.dict(os.environ, {"FSA_TASKS_DIR": str(self.state_dir), "CODEX_THREAD_ID": SESSION})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.path = self.root / "TASKS.md"

    def init(self, *specs, format="v2"):
        args = ["--format", format]
        for spec in specs:
            args += ["--task", spec]
        self.call("init", *args)

    def call(self, command, *args):
        argv = [command, "--root", str(self.root), "--file", "TASKS.md", "--session", SESSION, *args]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(argv), 0)
        text = output.getvalue()
        return json.loads(text) if text.strip() else None

    def call_fail(self, command, *args):
        argv = [command, "--root", str(self.root), "--file", "TASKS.md", "--session", SESSION, *args]
        error = io.StringIO()
        with contextlib.redirect_stderr(error), self.assertRaises(SystemExit):
            tasks.main(argv)
        return error.getvalue()

    def session_state(self):
        return self.call("show", "--json")["session_state"]

    def write(self, name, text):
        path = Path(self.scratch.name) / name
        path.write_text(text)
        return str(path)

    def make_done(self, task_id):
        spec = {"kind": "other", "scope": {"paths": ["README.md"], "rationale": "trivial"},
                "criteria": [{"id": "AC1", "text": "trivial", "checks": ["C1"]}],
                "checks": {"C1": {"method": "command", "command": "true", "cwd": ".", "expect": {"none": "ok"}}}}
        self.call("accept", "--id", task_id, "--input", self.write(f"{task_id}-spec.json", json.dumps(spec)))
        self.call("check", "run", "--id", task_id, "--check", "C1")
        self.call("set", "--id", task_id, "--status", "done")

    # -- session state ------------------------------------------------

    def test_two_user_questions_leave_third_row_executable_then_waiting_user(self):
        self.init("S3|pending|Row 3|", "S4|pending|Row 4|", "S5|pending|Row 5|")
        self.call("block", "--id", "Q1", "--rows", "S3", "--kind", "user", "--text", "Use the dev DB copy?", "--why", "S3 seeds from it")
        self.call("block", "--id", "Q2", "--rows", "S4", "--kind", "user", "--text", "Which node count?", "--why", "S4 asserts it")
        state = self.session_state()
        self.assertEqual(state["state"], "executable")
        self.assertEqual(state["executable"], ["S5"])
        self.assertEqual({q["id"] for q in state["questions"]}, {"Q1", "Q2"})
        self.make_done("S5")
        state = self.session_state()
        self.assertEqual(state["state"], "waiting_user")
        self.assertEqual({q["id"] for q in state["questions"]}, {"Q1", "Q2"})

    def test_worker_lease_only_is_waiting_worker(self):
        self.init("S1|pending|Row|")
        self.call("set", "--id", "S1", "--status", "in_progress", "--owner", "claude", "--activity", "implementing", "--active-for", "60")
        state = self.session_state()
        self.assertEqual(state["state"], "waiting_worker")
        self.assertEqual([w["row"] for w in state["workers"]], ["S1"])

    def test_stale_ledger_mtime_caps_active_lease_despite_future_active_until(self):
        self.init("S1|pending|Row|")
        self.call("set", "--id", "S1", "--status", "in_progress", "--owner", "claude", "--activity", "implementing", "--active-for", "280")
        old = time.time() - 600
        os.utime(self.path, (old, old))
        state = self.session_state()
        self.assertNotEqual(state["state"], "waiting_worker")
        self.assertEqual(state["executable"], ["S1"])

    def test_external_only_is_waiting_external(self):
        self.init("S1|pending|Row|")
        self.call("block", "--id", "E1", "--rows", "S1", "--kind", "external", "--class", "infrastructure", "--text", "CI is down")
        state = self.session_state()
        self.assertEqual(state["state"], "waiting_external")
        self.assertEqual([e["id"] for e in state["external"]], ["E1"])

    # -- user resolution ------------------------------------------------

    def test_resolve_with_recorded_quote_resumes_only_its_row(self):
        self.init("S3|pending|Row 3|", "S4|pending|Row 4|")
        self.call("block", "--id", "Q1", "--rows", "S3", "--kind", "user", "--text", "Use the dev DB copy?", "--why", "seeds S3")
        self.call("block", "--id", "Q2", "--rows", "S4", "--kind", "user", "--text", "Which node count?", "--why", "asserts S4")
        prompt_history.record(SESSION, "Yes, use the dev DB copy for this run")
        result = self.call("resolve", "--id", "Q1", "--quote", "use the dev DB copy")
        self.assertEqual(result["resumed"], ["S3"])
        self.assertEqual(result["note"], "quote matched a recorded prompt; resolving records the lead's "
                         "interpretation of the user's answer and authorizes nothing else")
        items = {item["id"]: item for item in self.call("show", "--json")["items"]}
        self.assertEqual(items["S3"]["status"], "pending")
        self.assertEqual(items["S4"]["status"], "blocked")

    def test_resolve_user_rejects_missing_short_or_wrong_kind_evidence(self):
        self.init("S3|pending|Row|")
        self.call("block", "--id", "Q1", "--rows", "S3", "--kind", "user", "--text", "Proceed?", "--why", "gates S3")
        self.assertIn("--quote", self.call_fail("resolve", "--id", "Q1"))
        prompt_history.record(SESSION, "short")
        self.assertIn("not found", self.call_fail("resolve", "--id", "Q1", "--quote", "short"))
        self.assertIn("--evidence", self.call_fail("resolve", "--id", "Q1", "--evidence", "free text, not a quote"))

    def test_prompt_history_is_hashed_and_matches_only_one_complete_prompt(self):
        prompt_history.record(SESSION, "Alpha beta gamma delta secretword")
        history_path = self.state_dir / "prompts" / f"{SESSION}.json"
        stored = history_path.read_text()
        for word in ("alpha", "beta", "gamma", "delta", "secretword"):
            self.assertNotIn(word, stored.lower())
        self.assertEqual(history_path.stat().st_mode & 0o777, 0o600)
        self.assertTrue(prompt_history.contains(SESSION, "BETA gamma DELTA"))
        self.assertFalse(prompt_history.contains(SESSION, "gamma delta"))
        prompt_history.record(SESSION, "epsilon zeta eta")
        self.assertFalse(prompt_history.contains(SESSION, "delta epsilon zeta"))

    def test_prompt_history_keeps_the_last_thirty_and_replaces_legacy_plaintext(self):
        history_path = self.state_dir / "prompts" / f"{SESSION}.json"
        history_path.parent.mkdir(parents=True)
        history_path.write_text(json.dumps(["legacy plaintext prompt"]))
        for number in range(31):
            prompt_history.record(SESSION, f"prompt number {number} unique")
        stored = json.loads(history_path.read_text())
        self.assertEqual(len(stored), 30)
        self.assertFalse(prompt_history.contains(SESSION, "prompt number 0"))
        self.assertTrue(prompt_history.contains(SESSION, "prompt number 30"))
        self.assertNotIn("legacy", history_path.read_text())

    def test_row_blocked_by_user_and_external_stays_blocked_until_both_resolve(self):
        self.init("S3|pending|Row|")
        self.call("block", "--id", "Q1", "--rows", "S3", "--kind", "user", "--text", "Proceed?", "--why", "gates S3")
        self.call("block", "--id", "E1", "--rows", "S3", "--kind", "external", "--class", "other", "--text", "waiting on vendor")
        prompt_history.record(SESSION, "Yes please proceed now")
        self.call("resolve", "--id", "Q1", "--quote", "please proceed now")
        self.assertEqual(self.call("show", "--json")["items"][0]["status"], "blocked")
        evidence = self.write("vendor.txt", "vendor confirmed availability")
        result = self.call("resolve", "--id", "E1", "--evidence", evidence, "--reason", "vendor confirmed")
        self.assertEqual(result["resumed"], ["S3"])
        self.assertEqual(self.call("show", "--json")["items"][0]["status"], "pending")

    # -- capacity ---------------------------------------------------------

    def test_capacity_resolution_rules(self):
        self.init("S1|pending|Row|")
        self.call("block", "--id", "E1", "--rows", "S1", "--kind", "external", "--class", "capacity",
                   "--engine", "claude", "--text", "Claude window full")
        with patch.object(plan_usage, "claude_plan", return_value={"windows": [{"name": "5 h", "pct": 100.0, "resets_at": ""}]}):
            self.assertIn("refused", self.call_fail("resolve", "--id", "E1", "--reason", "observed"))
        with patch.object(plan_usage, "claude_plan", return_value={"windows": [{"name": "5 h", "pct": 42.0, "resets_at": ""}]}):
            result = self.call("resolve", "--id", "E1")
        self.assertEqual(result["resumed"], ["S1"])
        self.call("block", "--id", "E2", "--rows", "S1", "--kind", "external", "--class", "capacity",
                   "--engine", "claude", "--text", "Claude window unknown")
        with patch.object(plan_usage, "claude_plan", return_value={"error": "no login"}):
            self.assertIn("unknown", self.call_fail("resolve", "--id", "E2"))
            evidence = self.write("usage.txt", "observed manually at the terminal")
            result = self.call("resolve", "--id", "E2", "--evidence", evidence, "--reason", "manual observation")
        self.assertEqual(result["resumed"], ["S1"])

    def test_capacity_block_without_text_defaults_to_engine_capacity_exhausted(self):
        self.init("S1|pending|Row|")
        self.call("block", "--id", "E1", "--rows", "S1", "--kind", "external", "--class", "capacity",
                   "--engine", "claude")
        state = self.session_state()
        self.assertEqual([e["id"] for e in state["external"]], ["E1"])
        block = task_blockers.load_block(self.path.read_text())
        self.assertEqual(block["blockers"]["E1"]["text"], "claude capacity exhausted")

    def test_capacity_until_in_the_past_alone_does_not_resolve(self):
        self.init("S1|pending|Row|")
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        self.call("block", "--id", "E1", "--rows", "S1", "--kind", "external", "--class", "capacity",
                   "--engine", "claude", "--until", past, "--text", "Claude window full")
        with patch.object(plan_usage, "claude_plan", return_value={"windows": [{"name": "5 h", "pct": 100.0, "resets_at": ""}]}):
            self.assertIn("refused", self.call_fail("resolve", "--id", "E1"))

    def test_stale_capacity_data_is_unknown_and_resolve_refused_without_evidence(self):
        self.init("S1|pending|Row|")
        self.call("block", "--id", "E1", "--rows", "S1", "--kind", "external", "--class", "capacity",
                   "--engine", "claude", "--text", "Claude window full")
        stale = {"windows": [{"name": "5 h", "pct": 10.0, "resets_at": ""}], "stale": "as of 9 min ago"}
        with patch.object(plan_usage, "claude_plan", return_value=stale):
            message = self.call_fail("resolve", "--id", "E1")
            self.assertIn("unknown", message)
            self.assertIn("--evidence", message)
            evidence = self.write("usage.txt", "observed manually at the terminal")
            result = self.call("resolve", "--id", "E1", "--evidence", evidence, "--reason", "manual observation")
        self.assertEqual(result["resumed"], ["S1"])

    def test_codex_window_with_past_resets_at_is_unknown_even_at_full_pct(self):
        self.init("S1|pending|Row|")
        self.call("block", "--id", "E1", "--rows", "S1", "--kind", "external", "--class", "capacity",
                   "--engine", "codex", "--text", "Codex window full")
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        with patch.object(plan_usage, "codex_plan", return_value={"windows": [{"name": "5 h", "pct": 100.0, "resets_at": past}]}):
            self.assertIn("unknown", self.call_fail("resolve", "--id", "E1", "--reason", "observed"))

    # -- row dependency -----------------------------------------------------

    def test_row_dependency_auto_resolves_when_target_done(self):
        self.init("S4|pending|Prerequisite|", "S5|pending|Dependent|")
        self.call("block", "--id", "R1", "--rows", "S5", "--kind", "row", "--text", "S4")
        self.assertEqual(self.call("show", "--json")["session_state"]["state"], "executable")
        self.make_done("S4")
        state = self.call("show", "--json")
        items = {item["id"]: item for item in state["items"]}
        self.assertEqual(items["S5"]["status"], "pending")
        self.assertEqual(state["session_state"]["state"], "executable")

    # -- set consistency ------------------------------------------------

    def test_set_blocked_and_unblock_consistency_refusals(self):
        self.init("S1|pending|Row|")
        self.assertIn("fsa-task block", self.call_fail("set", "--id", "S1", "--status", "blocked"))
        self.call("block", "--id", "B1", "--rows", "S1", "--kind", "external", "--class", "other", "--text", "waiting")
        self.assertIn("open blocker", self.call_fail("set", "--id", "S1", "--status", "pending"))

    def test_legacy_ledger_refuses_blocker_commands(self):
        self.init("S1|pending|Row|", format="legacy")
        self.assertIn("v2 ledger", self.call_fail("block", "--rows", "S1", "--kind", "external", "--class", "other", "--text", "x"))
        self.assertIn("v2 ledger", self.call_fail("resolve", "--id", "B1"))
        self.assertIn("v2 ledger", self.call_fail("withdraw", "--id", "B1", "--reason", "x"))

    # -- checkpoint integration -------------------------------------------

    def checkpoint_payload(self):
        return {"goal": "g", "scope": {"in": [], "out": []}, "approvals": [], "decisions": [],
                "constraints": [], "done": [], "next": {"action": "a", "owner": "o"}, "evidence": [],
                "verification": [], "status": "active"}

    def test_checkpoint_refreshed_on_block_and_left_untouched_when_invalid(self):
        self.init("S1|pending|Row|")
        self.call("checkpoint", "--input", self.write("cp.json", json.dumps(self.checkpoint_payload())))
        self.call("block", "--id", "B1", "--rows", "S1", "--kind", "external", "--class", "other", "--text", "waiting on vendor")
        checkpoint, error = task_checkpoint.load_checkpoint(self.path.read_text())
        self.assertIsNone(error)
        self.assertEqual(len(checkpoint["blockers"]), 1)
        self.assertIn("B1", checkpoint["blockers"][0])
        broken = self.path.read_text().replace('"goal": "g"', '"goal": 5')
        self.path.write_text(broken)
        before = self.path.read_text()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            self.assertEqual(tasks.main(["block", "--root", str(self.root), "--file", "TASKS.md", "--session", SESSION,
                                          "--id", "B2", "--rows", "S1", "--kind", "external", "--class", "other", "--text", "second"]), 0)
        self.assertIn("checkpoint not refreshed", stderr.getvalue())
        after = self.path.read_text()
        def checkpoint_section(text):
            return text[text.index(task_checkpoint.CP_START):text.index(task_checkpoint.CP_END)]
        self.assertEqual(checkpoint_section(before), checkpoint_section(after))
        self.assertIn("B2", task_blockers.load_block(after)["blockers"])

    # -- concurrency ------------------------------------------------------

    def test_concurrent_block_calls_keep_both_blockers(self):
        self.init("S1|pending|Row 1|", "S2|pending|Row 2|")
        children = [subprocess.Popen([sys.executable, str(CLI), "block", "--root", str(self.root), "--file", "TASKS.md",
                                       "--session", SESSION, "--rows", row, "--kind", "external", "--class", "other", "--text", f"waiting on {row}"],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for row in ("S1", "S2")]
        for child in children:
            _out, error = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, error)
        blockers = self.call("show", "--json")["blockers"]
        self.assertEqual(len(blockers), 2)
        self.assertEqual({entry["rows"][0] for entry in blockers.values()}, {"S1", "S2"})


if __name__ == "__main__":
    unittest.main()
