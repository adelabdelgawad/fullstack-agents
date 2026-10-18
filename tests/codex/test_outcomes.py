"""Terminal states, result.json, legacy/strict exit codes and cancellation of codex-task.sh runs."""
import json
import os
import re
import signal
import subprocess
import sys
import tarfile
import io
import tempfile
import time
import unittest
from pathlib import Path

from dispatch_support import REPO, SCRIPTS, DispatchCase

sys.path.insert(0, str(SCRIPTS / "lib"))
import liveness  # noqa: E402

BASELINE = "5e78c14"  # the dispatcher before Phase 1: legacy STATUS lines must match it exactly
SCENARIOS = {
    "ok": {"FSA_FAKE_MODE": "touch", "FSA_FAKE_TOUCH": "app.py"},
    "engine_failed": {"FSA_FAKE_MODE": "fail"},
    "invalid_output": {"FSA_FAKE_MODE": "touch,malformed", "FSA_FAKE_TOUCH": "app.py"},
    "truncated": {"FSA_FAKE_MODE": "touch,truncated", "FSA_FAKE_TOUCH": "app.py"},
    "scope_violation": {"FSA_FAKE_MODE": "touch", "FSA_FAKE_TOUCH": "app.py:other.py"},
    "no_changes": {"FSA_FAKE_MODE": "ok"},
}


def statuses(stdout):
    return [line.split(" ", 1)[0] for line in stdout.splitlines() if line.startswith("STATUS=")]


class OutcomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = tempfile.TemporaryDirectory(prefix="fsa-baseline-")
        archive = subprocess.run(["git", "-C", str(REPO), "archive", BASELINE, "plugins/fullstack-agents"],
                                 capture_output=True, check=True).stdout
        tarfile.open(fileobj=io.BytesIO(archive)).extractall(cls.old.name, filter="data")
        cls.old_script = Path(cls.old.name) / "plugins/fullstack-agents/scripts/codex-task.sh"

    @classmethod
    def tearDownClass(cls):
        cls.old.cleanup()

    def run_case(self, env, script=None, engine="codex"):
        case = DispatchCase(engine)
        self.addCleanup(case.cleanup)
        if script:
            return case, subprocess.run(["bash", str(script), "implement", str(case.brief)], env={**case.env, **env},
                                        capture_output=True, text=True, cwd=case.root, stdin=subprocess.DEVNULL)
        return case, case.dispatch(env=env)

    def result_json(self, case, result):
        m = case.manifest(result)
        return json.loads((Path(m["log"]).parent / f"{m['run']}.result.json").read_text())

    def test_legacy_status_lines_match_the_pre_phase1_dispatcher(self):
        for name, env in SCENARIOS.items():
            for engine in ("codex", "grok", "claude"):
                with self.subTest(scenario=name, engine=engine):
                    _, old = self.run_case(env, self.old_script, engine)
                    _, new = self.run_case(env, engine=engine)
                    self.assertEqual(statuses(new.stdout), statuses(old.stdout))
                    self.assertEqual((new.returncode, old.returncode), (0, 0))

    def test_terminal_state_and_strict_exit_codes(self):
        expected = {"ok": ("succeeded", 0), "engine_failed": ("engine_failed", 10),
                    "invalid_output": ("invalid_output", 11), "truncated": ("invalid_output", 11),
                    "scope_violation": ("scope_violation", 12), "no_changes": ("no_changes", 13)}
        for name, (state, code) in expected.items():
            with self.subTest(scenario=name):
                case, result = self.run_case({**SCENARIOS[name], "FSA_DISPATCH_EXIT": "strict"})
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                self.assertEqual(self.result_json(case, result)["state"], state)

    def test_engine_exit_is_kept_apart_from_result_extraction(self):
        case, result = self.run_case(SCENARIOS["invalid_output"], engine="grok")
        data = self.result_json(case, result)
        self.assertEqual((data["state"], data["engine_exit"]), ("invalid_output", 0))

    def test_sigterm_cancels_the_engine_and_records_touched_paths(self):
        case = DispatchCase("codex")
        self.addCleanup(case.cleanup)
        env = {**case.env, "FSA_FAKE_MODE": "touch,sleep", "FSA_FAKE_TOUCH": "app.py", "FSA_FAKE_SLEEP": "60",
               "FSA_CANCEL_WAIT_S": "3"}
        proc = subprocess.Popen(["bash", str(SCRIPTS / "codex-task.sh"), "implement", str(case.brief)], env=env,
                                cwd=case.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                stdin=subprocess.DEVNULL)
        runs = case.home / ".codex/fsa-runs"
        rid = self.wait_for_runner(runs)
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=30)
        self.assertEqual(proc.returncode, 130, out + err)
        data = json.loads((runs / f"{rid}.result.json").read_text())
        self.assertEqual(data["state"], "cancelled")
        self.assertIn("app.py", data["touched"])
        self.assertEqual(liveness.run_state(runs, rid)["state"] != "running", True)

    def test_sigkill_of_the_dispatcher_keeps_ownership_until_the_engine_stops(self):
        case = DispatchCase("codex")
        self.addCleanup(case.cleanup)
        env = {**case.env, "FSA_FAKE_MODE": "sleep", "FSA_FAKE_SLEEP": "60"}
        proc = subprocess.Popen(["bash", str(SCRIPTS / "codex-task.sh"), "implement", str(case.brief)], env=env,
                                cwd=case.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL)
        runs = case.home / ".codex/fsa-runs"
        rid = self.wait_for_runner(runs)
        proc.kill()
        proc.wait()
        self.assertEqual(liveness.run_state(runs, rid)["state"], "running")
        self.assertEqual(liveness.release(runs, rid, confirm=True)[0], 2)
        pgid = json.loads((runs / f"{rid}.meta.json").read_text())["runner_pgid"]
        os.killpg(pgid, signal.SIGKILL)
        time.sleep(0.3)
        self.assertEqual(liveness.run_state(runs, rid)["state"], "uncertain")
        self.assertEqual(liveness.release(runs, rid, confirm=True)[0], 0)

    def test_a_missing_mapped_skill_does_not_abort_the_dispatch_silently(self):
        plugin = Path(self.old.name) / "plugins/fullstack-agents"
        current = tempfile.TemporaryDirectory(prefix="fsa-current-")
        self.addCleanup(current.cleanup)
        subprocess.run(["cp", "-r", str(SCRIPTS.parent), current.name], check=True)
        copy = Path(current.name) / "fullstack-agents"
        subprocess.run(["rm", "-rf", str(copy / "skills/fastapi")], check=True)
        self.assertTrue(plugin.exists())
        _, result = self.run_case(SCENARIOS["ok"], copy / "scripts/codex-task.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STATUS=OK", result.stdout)

    def wait_for_runner(self, runs):
        for _ in range(100):
            metas = list(runs.glob("*.meta.json")) if runs.exists() else []
            try:
                started = bool(metas) and "runner_pgid" in json.loads(metas[0].read_text())
            except json.JSONDecodeError:
                started = False
            if started:
                time.sleep(0.5)
                return metas[0].name[:-len(".meta.json")]
            time.sleep(0.1)
        self.fail("runner never started")


if __name__ == "__main__":
    unittest.main()
