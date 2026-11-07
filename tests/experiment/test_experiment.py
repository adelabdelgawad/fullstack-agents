"""Deterministic checks of the workflow-comparison runner against the fake claude CLI; no model is ever called."""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import evaluate
import fsa_experiment
import measure
import preflight
import session
import workflow
from common import marked_pids, read_json, sha256_text

FAKE = HERE / "fake_claude.py"
CHECKS = HERE / "fixture/checks"
TASK = HERE / "fixture/TASK.md"


class Case(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = Path(tempfile.mkdtemp(prefix="fsa-exp-shared-"))
        cls.plugin = workflow.extract_head(cls.shared / "head")

    @classmethod
    def tearDownClass(cls):
        for p in [cls.shared, *cls.shared.rglob("*")]:
            if not p.is_symlink():
                p.chmod(p.stat().st_mode | 0o700)
        shutil.rmtree(cls.shared, ignore_errors=True)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fsa-exp-"))
        self.src = self.tmp / "src"
        shutil.copytree(HERE / "fixture/repo", self.src)
        git = ["git", "-C", str(self.src), "-c", "user.email=t@example.invalid", "-c", "user.name=T"]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-qm", "fixture"], check=True)
        self.scenario = self.tmp / "scenario.json"
        self.env = mock.patch.dict(os.environ, {"FSA_EXPERIMENTS_DIR": str(self.tmp / "exps"),
                                                "FSA_FAKE_SCENARIO": str(self.scenario)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        for p in [self.tmp, *self.tmp.rglob("*")]:
            if not p.is_symlink():
                p.chmod(p.stat().st_mode | 0o700)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def init(self, scenario, *extra):
        self.scenario.write_text(json.dumps(scenario))
        with mock.patch("sys.stdout"):
            fsa_experiment.main(["init", "--source", str(self.src), "--commit", "HEAD", "--task", str(TASK),
                                 "--workflow", str(self.plugin), "--model", "claude-sonnet-5", "--id", "t",
                                 "--real-claude", str(FAKE), "--env-allow", "FSA_FAKE_SCENARIO",
                                 "--token-file", str(self.tmp / "no-token"), *extra])
        self.exp = self.tmp / "exps/t"
        return self.exp

    def run_arms(self, *extra):
        with mock.patch("sys.stdout"):
            return fsa_experiment.main(["run", "t", "--poll", "0.1", *extra])

    def evaluate(self, checks=CHECKS):
        with mock.patch("sys.stdout"):
            fsa_experiment.main(["evaluate", "t", "--checks", str(checks)])
        return read_json(self.exp / "eval/evaluation.json")

    def arm(self, name):
        return read_json(self.exp / f"arms/{name}/arm.json")

    def results(self):
        return read_json(self.exp / "results.json")


class StartAndIsolation(Case):
    def test_both_arms_start_from_identical_content_and_task(self):
        self.init({"default": ["fix"], "b-propose-1": ["improve_ok"], "b-compose-1": ["improve_ok"]})
        self.run_arms()
        commit_tree = subprocess.run(["git", "-C", str(self.src), "rev-parse", "HEAD^{tree}"], capture_output=True,
                                     text=True, check=True).stdout.strip()
        stages = [s for a in "AB" for s in self.arm(a)["stages"].values() if s["kind"] == "implementation"]
        self.assertEqual(len(stages), 4)
        task_sha = sha256_text(TASK.read_text())
        for s in stages:
            self.assertEqual(s["start_tree"], commit_tree)
            self.assertTrue(s["start_clean"])
            self.assertEqual(s["prompt_sha256"], task_sha)

    def test_mutable_state_is_per_session(self):
        self.init({"default": ["fix", "sentinel"], "b-propose-1": ["keep_base"]})
        self.run_arms()
        recs = [s for a in "AB" for s in self.arm(a)["stages"].values()]
        keys = ("HOME", "CLAUDE_CONFIG_DIR", "TMPDIR", "FSA_STATE_HOME", "FSA_TEAM_BOARD", "FSA_CODEX_RUNS_DIR",
                "FSA_TASKS_DIR", "XDG_DATA_HOME", "FSA_EXP_SESSION")
        for key in keys:
            values = [r["env"][key] for r in recs]
            self.assertEqual(len(values), len(set(values)), key)
        for r in recs:
            for sentinel in Path(self.exp).rglob("SENTINEL"):
                inside = str(sentinel).startswith(r["sandbox"] + "/")
                self.assertEqual(inside, r["env"]["CLAUDE_CONFIG_DIR"] in str(sentinel)
                                 or r["env"]["FSA_STATE_HOME"] in str(sentinel))
        remotes = subprocess.run(["git", "-C", recs[0]["sandbox"] + "/repo", "remote"], capture_output=True,
                                 text=True, check=True).stdout
        self.assertEqual(remotes.strip(), "")

    def test_recorded_workflow_and_instructions_match_execution(self):
        self.init({"default": ["fix"]})
        self.run_arms("--arm", "A")
        rec = self.arm("A")["stages"]["a-final"]
        base = read_json(self.exp / "workflows/base/manifest.json")
        self.assertEqual(rec["workflow_sha256"], base["sha256"])
        self.assertEqual(rec["workflow_mismatch_after"], [])
        self.assertTrue(rec["instruction_sources"]["plugin_dir_loaded"])
        self.assertTrue(any(f.endswith("/repo/AGENTS.md") for f in rec["instruction_sources"]
                            ["instruction_files_in_debug_log"]))
        self.assertFalse((Path(rec["env"]["CLAUDE_CONFIG_DIR"]) / "CLAUDE.md").exists())
        self.assertTrue(rec["env"]["HOME"].startswith(str(self.exp)))

    def test_snapshot_records_delta_from_head(self):
        tree = self.tmp / "plugin"
        shutil.copytree(self.plugin, tree)
        (tree / "scripts/lib/claude_cli.py").write_text("changed\n")
        rec = workflow.snapshot(tree, self.tmp / "snap")
        self.assertEqual([c["path"] for c in rec["delta_from_head"]["changed"]], ["scripts/lib/claude_cli.py"])
        self.assertIn("+changed", (self.tmp / "snap/delta-from-head.diff").read_text())
        self.assertEqual(workflow.verify(self.tmp / "snap/tree", rec), [])

    def test_other_sessions_are_locked_during_a_session(self):
        self.init({"default": ["fix"], "b-propose-1": ["keep_base"], "b-final": ["fix", "peek"]})
        self.run_arms()
        peek = json.loads((self.exp / "arms/B/stages/b-final/peek.json").read_text())
        self.assertEqual(set(peek.values()), {"denied"}, peek)
        self.assertTrue(self.arm("B")["stages"]["b-final"]["locked_during_session"])
        self.assertTrue((self.exp / "arms/B/stages/b-base/repo/pricing.py").read_text())
        self.assertEqual(workflow.verify(self.exp / "workflows/base/tree",
                                         read_json(self.exp / "workflows/base/manifest.json")), [])

    def test_token_leaked_by_the_cli_is_redacted(self):
        token = self.tmp / "token"
        token.write_text("sk-ant-oat01-leakedvalue")
        self.init({"default": ["fix", "leak_token"]}, "--token-file", str(token))
        self.run_arms("--arm", "A")
        rec = self.arm("A")["stages"]["a-final"]
        self.assertTrue(any(f.endswith("debug.log") for f in rec["token_redacted_in"]))
        self.assertEqual(rec["env"]["DISABLE_AUTOUPDATER"], "1")
        for path in self.exp.rglob("*"):
            if path.is_file() and ".git" not in path.parts:
                self.assertNotIn("leakedvalue", path.read_text(errors="replace"), path)

    def test_token_is_never_recorded(self):
        token = self.tmp / "token"
        token.write_text("sk-ant-oat01-secretvalue")
        self.init({"default": ["fix"]}, "--token-file", str(token))
        self.run_arms("--arm", "A")
        rec = self.arm("A")["stages"]["a-final"]
        self.assertEqual(rec["env"]["CLAUDE_CODE_OAUTH_TOKEN"], "[set]")
        for path in self.exp.rglob("*"):
            if path.is_file() and path.stat().st_size < 5_000_000:
                self.assertNotIn("secretvalue", path.read_text(errors="replace"), path)


class ArmB(Case):
    def test_overhead_is_in_totals_and_changes_are_recorded(self):
        self.init({"default": ["fix"], "b-propose-1": ["improve_ok"], "b-compose-1": ["improve_ok"]})
        self.run_arms()
        b = self.results()["arms"]["B"]
        names = [s["stage"] for s in b["stages"]]
        self.assertEqual(names, ["b-base", "b-propose-1", "b-probe-1", "b-compose-1", "b-final"])
        for key in ("seconds", "estimated_usd", "cli_reported_usd"):
            self.assertAlmostEqual(b["totals"][key], sum(s[key] for s in b["stages"]), places=5)
        final = next(s for s in b["stages"] if s["stage"] == "b-final")
        self.assertAlmostEqual(b["overhead_before_final"]["estimated_usd"],
                               b["totals"]["estimated_usd"] - final["estimated_usd"], places=5)
        self.assertGreater(b["totals"]["estimated_usd"], self.results()["arms"]["A"]["totals"]["estimated_usd"])
        change = b["workflow_changes"][-1]
        self.assertIn("verification check", Path(change["diff"]).read_text())
        self.assertFalse(b["final_workflow"]["identical_to_base"])
        self.assertNotEqual(final["workflow_sha256"], b["stages"][0]["workflow_sha256"])
        lessons = read_json(self.exp / "arms/B/lessons.json")
        self.assertIn("separate reviewed decision", lessons["scope"])

    def test_keep_base_is_labelled_a_repeat_attempt(self):
        self.init({"default": ["fix"], "b-propose-1": ["keep_base"]})
        self.run_arms()
        self.evaluate()
        r = self.results()
        self.assertTrue(r["arms"]["B"]["final_workflow"]["identical_to_base"])
        self.assertTrue(any("repeat attempt" in c for c in r["comparison"]["caveats"]))
        self.assertNotIn("b-probe-1", [s["stage"] for s in r["arms"]["B"]["stages"]])

    def test_invalid_candidate_retries_once_then_falls_back(self):
        self.init({"default": ["fix"], "b-propose-1": ["improve_bad"], "b-propose-1-retry": ["improve_bad"]})
        self.run_arms()
        b = self.results()["arms"]["B"]
        change = b["workflow_changes"][0]
        self.assertTrue(change["fell_back"])
        self.assertEqual(len(change["attempts"]), 2)
        self.assertIn("outside allowlist: hooks/hooks.json", change["attempts"][0]["problems"])
        self.assertTrue(b["final_workflow"]["identical_to_base"])
        self.assertEqual(b["totals"]["improver_retries"], 1)

    def test_task_identifier_in_candidate_is_flagged(self):
        self.init({"default": ["fix"], "b-propose-1": ["improve_leak"], "b-propose-1-retry": ["improve_leak"]})
        self.run_arms()
        change = self.arm("B")["workflow_changes"][0]
        self.assertTrue(change["fell_back"])
        self.assertIn("apply_discount", change["attempts"][0]["identifier_hits"])


class Failures(Case):
    def test_timeout_kills_detached_children(self):
        self.init({"default": ["sleep", "detach"]}, "--session-s", "2")
        self.run_arms("--arm", "A")
        rec = self.arm("A")["stages"]["a-final"]
        self.assertEqual(rec["state"], "timed_out")
        self.assertEqual(marked_pids(rec["env"]["FSA_EXP_SESSION"]), [])
        self.assertEqual(self.results()["arms"]["A"]["state"], "timed_out")

    def test_nonzero_exit_is_failed(self):
        self.init({"default": ["fail"]})
        self.run_arms("--arm", "A")
        a = self.results()["arms"]["A"]
        self.assertEqual(a["state"], "failed")
        self.assertEqual(a["totals"]["failed_processes"], 1)
        self.assertTrue(a["totals"]["usage_is_lower_bound"])

    def test_missing_usage_is_a_reported_gap(self):
        self.init({"default": ["fix", "no_usage"]})
        self.run_arms("--arm", "A")
        a = self.results()["arms"]["A"]
        self.assertTrue(a["totals"]["usage_is_lower_bound"])
        self.assertTrue(any("not reported" in g["gap"] for g in a["stages"][0]["gaps"]))
        self.assertIsNone(a["totals"]["billed_usd"])

    def test_budget_watcher_stops_the_session(self):
        self.init({"default": ["fix", "expensive"]}, "--usd-a", "1")
        self.run_arms("--arm", "A")
        rec = self.arm("A")["stages"]["a-final"]
        self.assertEqual(rec["state"], "budget_exhausted")
        self.assertGreater(rec["accounting"]["estimated_usd"], 1)

    def test_interrupt_records_interrupted(self):
        self.init({"default": ["sleep"]})
        proc = subprocess.Popen([sys.executable, str(HERE / "fsa_experiment.py"), "run", "t", "--arm", "A",
                                 "--poll", "0.1"], env=os.environ.copy(), stdout=subprocess.DEVNULL)
        ledger = self.exp / "arms/A/stages/a-final/processes.jsonl"
        deadline = time.time() + 20
        while time.time() < deadline and not (ledger.is_file() and ledger.read_text()):
            time.sleep(0.1)
        time.sleep(0.5)
        proc.send_signal(signal.SIGINT)
        self.assertEqual(proc.wait(timeout=30), 130)
        self.assertEqual(self.arm("A")["state"], "interrupted")
        self.assertEqual(self.results()["arms"]["A"]["state"], "interrupted")

    def test_failed_verification_is_not_success(self):
        self.init({"default": ["wrong"]})
        self.run_arms("--arm", "A")
        ev = self.evaluate()
        self.assertEqual(ev["arms"]["A"]["verdict"], "rejected")
        self.assertEqual(self.results()["comparison"]["outcome"], "inconclusive")


class Replies(Case):
    def test_plan_approval_gets_the_canned_reply(self):
        self.init({"default": ["ask_plan", "fix"]})
        self.run_arms("--arm", "A")
        rec = self.arm("A")["stages"]["a-final"]
        self.assertEqual(rec["state"], "succeeded")
        self.assertEqual(len(rec["session"]["auto_replies"]), 1)
        self.assertEqual(rec["session"]["auto_replies"][0]["reply"], session.CANNED_REPLY)
        self.assertIn("--resume", rec["session"]["steps"][1]["args"])
        totals = self.results()["arms"]["A"]["totals"]
        self.assertEqual((totals["auto_replies"], totals["human_interventions"]), (1, 0))

    def test_permission_request_needs_a_human(self):
        self.init({"default": ["ask_permission"]})
        self.run_arms("--arm", "A")
        rec = self.arm("A")["stages"]["a-final"]
        self.assertEqual(rec["state"], "needs_human")
        self.assertEqual(rec["session"]["auto_replies"], [])

    def test_reply_caps_hold(self):
        self.init({"default": ["ask_plan_twice"]}, "--replies-a", "5")
        self.run_arms("--arm", "A")
        rec = self.arm("A")["stages"]["a-final"]
        self.assertEqual(len(rec["session"]["auto_replies"]), session.MAX_REPLIES_PER_SESSION)
        self.assertEqual(rec["state"], "needs_human")
        self.assertIn("cap reached", rec["reason"])

    def test_arm_reply_cap_holds(self):
        self.init({"default": ["ask_plan_twice"]}, "--replies-a", "1")
        self.run_arms("--arm", "A")
        self.assertEqual(len(self.arm("A")["stages"]["a-final"]["session"]["auto_replies"]), 1)

    def test_human_reply_is_recorded_apart_from_automatic_ones(self):
        self.init({"default": ["ask_permission"]})
        self.run_arms("--arm", "A")
        self.scenario.write_text(json.dumps({"default": ["fix"]}))
        with mock.patch("sys.stdout"):
            fsa_experiment.main(["resume", "t", "--arm", "A", "--stage", "a-final", "--message", "Denied; fix only.",
                                 "--poll", "0.1"])
        a = self.results()["arms"]["A"]
        self.assertEqual(a["state"], "succeeded")
        self.assertEqual(a["totals"]["human_interventions"], 1)
        self.assertEqual(a["totals"]["auto_replies"], 0)

    def test_canned_reply_never_authorizes_expanded_actions(self):
        approve = ["approve the plan", "Approve the implementation plan", "go ahead with the plan"]
        refuse = ["approve the plan and grant access to the database", "approve the plan; it needs $5 more budget",
                  "approve the plan to push to main", "approve the plan and the credential setup",
                  "approve the plan or choose option B", "approve the plan to upload the source to another provider",
                  "approve the plan, which widens the scope to two services", "approve the deploy",
                  "grant permission to run migrations", "send the report to the team"]
        for text in approve:
            self.assertTrue(session.plan_approval(text), text)
        for text in refuse:
            self.assertFalse(session.plan_approval(text), text)
        state, _reason, reply = session.classify_stop("Plan.\nCan I use the prod key?\nWaiting on: you - approve the plan")
        self.assertEqual((state, reply), ("needs_human", False))
        self.assertFalse(session.classify_stop("Waiting on: background test run")[2])


class Accounting(Case):
    def test_subagents_classifiers_and_implementers_counted_once(self):
        self.init({"default": ["fix", "subagent", "classifier", "implementer"]})
        self.run_arms("--arm", "A")
        acct = self.arm("A")["stages"]["a-final"]["accounting"]
        self.assertEqual(acct["transcripts"]["duplicate_lines"], 1)
        self.assertEqual(acct["transcripts"]["messages"], 2 + 1 + 2)
        roles = sorted(p["role"] for p in acct["processes"])
        self.assertEqual(roles, ["classifier", "implementer", "lead"])
        one = measure.usage.cost_of("claude-sonnet-5", {"input": 10, "output": 1000, "write_5m": 0, "write_1h": 2000,
                                                        "cache_read": 5000})
        self.assertAlmostEqual(acct["estimated_usd"], one * 5 + one, places=6)
        self.assertAlmostEqual(acct["estimated_unpersisted_usd"], one, places=6)
        self.assertAlmostEqual(acct["cli_reported_usd"], one * 2 * 2 + one, places=6)


class Evaluation(Case):
    def test_acceptance_failure_is_never_excused_by_the_baseline(self):
        self.init({"default": ["wrong"], "b-propose-1": ["keep_base"], "b-final": ["fix"]})
        self.run_arms()
        ev = self.evaluate()
        a, b = ev["arms"]["A"], ev["arms"]["B"]
        self.assertEqual(a["acceptance"][0], {"id": "AC1", "status": "fail", "baseline": "fail"})
        self.assertEqual(a["verdict"], "rejected")
        self.assertEqual(b["verdict"], "accepted")
        self.assertEqual({r["id"]: r["outcome"] for r in b["regression"]}, {"R1": "ok", "R2": "existing_failure"})
        self.assertEqual(self.results()["comparison"]["outcome"], "B better on acceptance for this task")

    def test_new_regression_rejects(self):
        self.init({"default": ["fix", "break"]})
        self.run_arms("--arm", "A")
        a = self.evaluate()["arms"]["A"]
        self.assertEqual(a["new_regressions"], ["R1"])
        self.assertEqual(a["verdict"], "rejected")

    def test_agent_edited_eval_paths_are_overwritten_and_flagged(self):
        self.init({"default": ["wrong", "touch_eval"]})
        self.run_arms("--arm", "A")
        a = self.evaluate()["arms"]["A"]
        self.assertEqual(a["eval_path_conflicts"], ["tests_eval/__init__.py", "tests_eval/test_acceptance.py"])
        self.assertEqual(a["acceptance"][0]["status"], "fail")

    def test_check_statuses_stay_distinct(self):
        checks = self.tmp / "checks"
        shutil.copytree(CHECKS, checks)
        spec = json.loads((checks / "checks.json").read_text())
        spec["regression"] += [{"id": "T1", "command": "sleep 5", "timeout": 1},
                               {"id": "S1", "command": "true", "skip": "needs a database"}]
        (checks / "checks.json").write_text(json.dumps(spec))
        self.init({"default": ["fix"]})
        self.run_arms("--arm", "A")
        ev = self.evaluate(checks)
        statuses = {c["id"]: c["status"] for c in ev["targets"]["A"]["checks"]}
        self.assertEqual(statuses, {"AC1": "pass", "R1": "pass", "R2": "fail", "T1": "timeout", "S1": "skipped"})
        self.assertEqual(ev["arms"]["A"]["verdict"], "inconclusive")

    def test_unexecuted_when_patch_cannot_apply(self):
        self.init({"default": ["fix"]})
        self.run_arms("--arm", "A")
        patch = Path(self.arm("A")["stages"]["a-final"]["capture"]["deliverable"])
        patch.write_text("diff --git a/x b/x\ngarbage\n")
        ev = self.evaluate()
        self.assertEqual({c["status"] for c in ev["targets"]["A"]["checks"]}, {"unexecuted"})
        self.assertEqual(ev["arms"]["A"]["verdict"], "rejected")

    def test_commitment_mismatch_and_leak_hits_are_reported(self):
        self.init({"default": ["fix"]}, "--checks-sha256", "0" * 64)
        self.run_arms("--arm", "A")
        prompt = self.exp / "arms/A/stages/a-final/prompt.md"
        prompt.write_text(prompt.read_text() + "\nsee tests_eval/test_acceptance.py\n")
        ev = self.evaluate()
        self.assertEqual(ev["commitment"], "MISMATCH")
        self.assertTrue(ev["leak_hits"])
        caveats = self.results()["comparison"]["caveats"]
        self.assertTrue(any("committed at init" in c for c in caveats))

    def test_report_traces_to_saved_artifacts(self):
        self.init({"default": ["fix"], "b-propose-1": ["keep_base"]})
        self.run_arms()
        self.evaluate()
        r = self.results()
        for arm in r["arms"].values():
            self.assertTrue(Path(arm["artifact"]).is_file())
            for s in arm["stages"]:
                self.assertTrue(Path(s["sandbox"], "processes.jsonl").is_file())
        for target in read_json(self.exp / "eval/evaluation.json")["targets"].values():
            for c in target["checks"]:
                self.assertTrue(Path(c["log"]).is_file())
        report = (self.exp / "REPORT.md").read_text()
        self.assertIn("Billed", report)
        self.assertIn(str(self.exp / "results.json"), report)


class Preflight(Case):
    def test_preflight_records_loading_and_semantics(self):
        self.init({"default": ["subagent"]})
        with mock.patch("sys.stdout"):
            fsa_experiment.main(["preflight", "t", "--model", "claude-haiku-5-5"])
        rec = read_json(self.exp / "preflight/preflight.json")
        self.assertTrue(rec["loading"]["auth_ok"])
        self.assertTrue(rec["loading"]["single_pinned_plugin"])
        self.assertEqual(rec["loading"]["personal_claude_md_in_debug_log"], [])
        self.assertEqual(rec["loading"]["personal_instructions_check"], "none loaded")
        self.assertFalse(rec["loading"]["hooks_from_snapshot"])
        self.assertIn(rec["accounting"]["resume_cost_semantics"], ("cumulative", "incremental", "unverified"))
        self.assertEqual(read_json(self.exp / "experiment.json")["resume_cost_semantics"],
                         rec["accounting"]["resume_cost_semantics"])


class Units(unittest.TestCase):
    def test_semantics_need_a_clear_margin(self):
        self.assertEqual(preflight._closer(1.0, 1.0, 1.02), "unknown")
        self.assertEqual(preflight._closer(1.0, 1.0, 2.0), "a")
        self.assertEqual(preflight._closer(1.5, 1.0, 2.0), "unknown")
        self.assertEqual(preflight._closer(None, 1.0, 2.0), "unknown")

    def test_environment_suspect_when_no_regression_passes(self):
        base = {"checks": [{"id": "R1", "kind": "regression", "status": "fail"},
                           {"id": "AC1", "kind": "acceptance", "status": "fail"}]}
        self.assertTrue(evaluate.environment_suspect(base))
        base["checks"][0]["status"] = "pass"
        self.assertFalse(evaluate.environment_suspect(base))

    def test_resumed_session_cost_follows_measured_semantics(self):
        procs = [{"pid": i, "role": "lead", "exit": 0, "argv": [], "result": {"session_id": "s", "total_cost_usd": c}}
                 for i, c in ((1, 0.1), (2, 0.3))]
        self.assertAlmostEqual(measure._cli_cost(procs, "incremental")[0], 0.4)
        self.assertAlmostEqual(measure._cli_cost(procs, "cumulative")[0], 0.3)
        reported, gaps, _ = measure._cli_cost(procs, "unverified")
        self.assertAlmostEqual(reported, 0.4)
        self.assertTrue(any("double-count" in g["gap"] for g in gaps))

    def test_classify_unknown_when_baseline_unexecuted(self):
        base = {"checks": [{"id": "R1", "kind": "regression", "status": "unexecuted"}]}
        arm = {"checks": [{"id": "AC1", "kind": "acceptance", "status": "pass"},
                          {"id": "R1", "kind": "regression", "status": "pass"}], "eval_path_conflicts": []}
        self.assertEqual(evaluate.classify(base, arm)["verdict"], "inconclusive")


if __name__ == "__main__":
    unittest.main()
