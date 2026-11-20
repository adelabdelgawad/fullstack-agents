"""codex-task.sh's revision fence: stale/cancelled dispatch refusal, a stale finish, and `stop <run-id>`.
See docs/TASK_LIFECYCLE_DESIGN.md §15 (Unit C)."""
import json
import os
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from dispatch_support import SCRIPTS, DispatchCase

sys.path.insert(0, str(SCRIPTS / "lib"))
import coordination_log  # noqa: E402


def bump(root, row, revision, kind="correction", task="ledger.md"):
    coordination_log.append(str(root), "test-session", "revision.bump", task=task, row=row, revision=revision,
                             request="R1", kind=kind, note="")


class RevisionFenceCase(unittest.TestCase):
    def setUp(self):
        self.case = DispatchCase("codex")
        self.addCleanup(self.case.cleanup)
        tasks_dir = str(self.case.base / "tasks")
        self.case.env["FSA_TASKS_DIR"] = tasks_dir
        patcher = patch.dict(os.environ, {"FSA_TASKS_DIR": tasks_dir})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.runs = self.case.home / ".codex/fsa-runs"

    def write_brief(self, task_line, revision_line=None):
        text = "IMPLEMENTER: codex\nPLAN: none: test\nALLOWED_PATHS:\napp.py\n\nGOAL: x\n" + task_line + "\n"
        if revision_line:
            text += revision_line + "\n"
        self.case.brief.write_text(text)

    def run_count(self):
        return len(list(self.runs.glob("*.meta.json"))) if self.runs.exists() else 0


class DispatchFenceTests(RevisionFenceCase):
    def test_stale_revision_is_refused_before_any_run_file_exists(self):
        bump(self.case.root, "R1", 1)
        self.write_brief("TASK: ledger.md#R1")
        before = self.run_count()
        result = self.case.dispatch(env={"FSA_FAKE_MODE": "touch", "FSA_FAKE_TOUCH": "app.py"})
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("STATUS=STALE_REVISION (brief revision none, row revision 1)", result.stdout + result.stderr)
        self.assertEqual(self.run_count(), before)

    def test_cancelled_row_is_refused_even_with_a_matching_revision_line(self):
        bump(self.case.root, "R1", 1, kind="cancel")
        self.write_brief("TASK: ledger.md#R1", "REVISION: 1")
        before = self.run_count()
        result = self.case.dispatch(env={"FSA_FAKE_MODE": "touch", "FSA_FAKE_TOUCH": "app.py"})
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("STATUS=ROW_CANCELLED", result.stdout + result.stderr)
        self.assertEqual(self.run_count(), before)

    def test_revision_zero_with_no_revision_line_dispatches_as_today(self):
        self.write_brief("TASK: ledger.md#R1")
        result = self.case.dispatch(env={"FSA_FAKE_MODE": "touch", "FSA_FAKE_TOUCH": "app.py"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("STATUS=OK", result.stdout)

    def test_matching_revision_line_dispatches(self):
        bump(self.case.root, "R1", 1)
        self.write_brief("TASK: ledger.md#R1", "REVISION: 1")
        result = self.case.dispatch(env={"FSA_FAKE_MODE": "touch", "FSA_FAKE_TOUCH": "app.py"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("STATUS=OK", result.stdout)

    def test_a_brief_without_a_task_line_is_never_fenced(self):
        bump(self.case.root, "R1", 1, kind="cancel")
        result = self.case.dispatch(env={"FSA_FAKE_MODE": "touch", "FSA_FAKE_TOUCH": "app.py"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class StaleFinishTests(RevisionFenceCase):
    def init_ledger(self):
        self.case.env["CODEX_THREAD_ID"] = "setup"
        tracker = [sys.executable, str(SCRIPTS / "fsa-task")]
        subprocess.run([*tracker, "init", "--format", "legacy", "--root", str(self.case.root), "--file", "ledger.md",
                        "--session", "setup", "--task", "R1|pending|Row one|"],
                       env=self.case.env, check=True, capture_output=True)

    def test_a_correction_landing_mid_run_ends_it_stale_without_touching_the_row(self):
        self.init_ledger()
        self.write_brief("TASK: ledger.md#R1")
        holder = {}

        def run():
            holder["result"] = self.case.dispatch(env={"FSA_FAKE_MODE": "touch,sleep", "FSA_FAKE_TOUCH": "app.py",
                                                        "FSA_FAKE_SLEEP": "2"}, timeout=30)

        thread = threading.Thread(target=run)
        thread.start()
        time.sleep(0.8)
        bump(self.case.root, "R1", 1)
        thread.join()
        result = holder["result"]
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("STATUS=STALE_REVISION (must reconcile: changes kept)", result.stdout)
        rid = self.case.manifest(result)["run"]
        runs = Path(self.case.manifest(result)["log"]).parent
        data = json.loads((runs / f"{rid}.result.json").read_text())
        self.assertEqual(data["state"], "stale_revision")
        self.assertEqual(data["details"][0], "stale_revision")
        self.assertIn("app.py", data["touched"])
        tracker = [sys.executable, str(SCRIPTS / "fsa-task")]
        show = subprocess.run([*tracker, "show", "--json", "--root", str(self.case.root), "--file", "ledger.md"],
                              env=self.case.env, check=True, capture_output=True, text=True)
        row = json.loads(show.stdout)["items"][0]
        self.assertEqual(row["status"], "in_progress")
        self.assertNotIn("stale_revision", row["note"] or "")


class StopCommandTests(unittest.TestCase):
    def setUp(self):
        self.case = DispatchCase("codex")
        self.addCleanup(self.case.cleanup)
        self.runs = self.case.base / "runs"
        self.runs.mkdir()
        self.case.env["FSA_CODEX_RUNS_DIR"] = str(self.runs)
        self.procs = []
        self.addCleanup(self.kill_leftovers)

    def kill_leftovers(self):
        for p in self.procs:
            try:
                os.killpg(p.pid, 9)
            except OSError:
                pass
            p.wait()

    def pid_start(self, pid):
        out = subprocess.run([sys.executable, "-I", str(SCRIPTS / "lib/liveness.py"), "pid-start", str(pid)],
                             capture_output=True, text=True)
        return out.stdout.strip()

    def spawn_dispatcher(self, rid):
        result_path = self.runs / f"{rid}.result.json"
        line = f"  printf '%s' '{{\"state\": \"cancelled\"}}' > '{result_path}'"
        script = self.case.base / f"{rid}.sh"
        script.write_text("\n".join(["#!/usr/bin/env bash", "write_result() {", line, "  exit 0", "}",
                                      "trap write_result TERM", "sleep 30 &", "wait $!"]) + "\n")
        script.chmod(0o755)
        p = subprocess.Popen(["bash", str(script)], start_new_session=True)
        self.procs.append(p)
        time.sleep(0.3)
        return p

    def write_meta(self, rid, pid, started):
        (self.runs / f"{rid}.meta.json").write_text(json.dumps({"dispatcher_pid": pid, "dispatcher_started": started}))

    def stop(self, rid):
        return subprocess.run(["bash", str(SCRIPTS / "codex-task.sh"), "stop", rid], env=self.case.env,
                              capture_output=True, text=True, cwd=self.case.root, timeout=30)

    def test_stop_terminates_the_matching_dispatcher_and_waits_for_the_result(self):
        rid = "run-stop-1"
        proc = self.spawn_dispatcher(rid)
        self.write_meta(rid, proc.pid, self.pid_start(proc.pid))
        result = self.stop(rid)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("STOPPED (state cancelled)", result.stdout)

    def test_stop_refuses_a_pid_that_does_not_match_the_recorded_start_time(self):
        rid = "run-stop-2"
        proc = self.spawn_dispatcher(rid)
        self.write_meta(rid, proc.pid, "0")
        result = self.stop(rid)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("MUST RECONCILE", result.stdout)
        self.assertIsNone(proc.poll(), "a pid that cannot be tied to the run is never signalled")

    def test_stop_reports_an_unknown_run(self):
        result = self.stop("no-such-run")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not found in the registry", result.stderr)


if __name__ == "__main__":
    unittest.main()
