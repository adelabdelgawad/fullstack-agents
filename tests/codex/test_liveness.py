"""Run liveness: a run owns its paths until no process can still edit and the engine record shows completion."""
import json
import os
import sqlite3
import subprocess
import sys
import time
import unittest
from pathlib import Path

from dispatch_support import SCRIPTS, DispatchCase

sys.path.insert(0, str(SCRIPTS / "lib"))
import liveness  # noqa: E402


class LivenessTests(unittest.TestCase):
    def setUp(self):
        self.case = DispatchCase("codex")
        self.addCleanup(self.case.cleanup)
        self.runs = self.case.base / "runs"
        self.runs.mkdir()
        self.procs = []
        self.env = dict(os.environ)
        os.environ["CODEX_HOME"] = str(self.case.base / "codex-home")
        os.environ["XDG_DATA_HOME"] = str(self.case.base / "xdg")
        self.addCleanup(self.restore_env)

    def restore_env(self):
        for p in self.procs:
            try:
                os.killpg(p.pid, 9)
            except OSError:
                pass
            p.wait()
        os.environ.clear()
        os.environ.update(self.env)

    def record(self, rid, engine="codex", **extra):
        meta = {"id": rid, "schema": 2, "engine": engine, "cwd": str(self.case.root), "root": str(self.case.root),
                "engine_session_id": extra.pop("sid", None), **extra}
        (self.runs / f"{rid}.meta.json").write_text(json.dumps(meta))

    def spawn(self, args, **kw):
        p = subprocess.Popen(args, start_new_session=True, **kw)
        self.procs.append(p)
        time.sleep(0.2)
        return p

    def state(self, rid):
        return liveness.run_state(self.runs, rid)["state"]

    def test_v1_records_are_left_to_the_legacy_rule(self):
        (self.runs / "r1.meta.json").write_text(json.dumps({"id": "r1", "engine": "codex"}))
        self.assertEqual(self.state("r1"), "legacy")

    def test_a_detached_process_with_the_marker_keeps_the_run_running(self):
        self.record("r2")
        p = self.spawn(["sleep", "30"], env={**os.environ, "FSA_RUN_ID": "r2"})
        self.assertEqual(self.state("r2"), "running")
        p.kill(); p.wait()
        self.assertEqual(self.state("r2"), "uncertain", "no engine record: never stopped")

    def test_codex_delegated_executor_children_under_the_root_make_it_uncertain(self):
        self.record("r3", sid="0000-r3")
        self.rollout("0000-r3", complete=True)
        script = 'sleep 30 & exec -a codex-code-mode-host sleep 30'
        self.spawn(["bash", "-c", script], cwd=self.case.root)
        result = liveness.run_state(self.runs, "r3")
        self.assertEqual(result["state"], "uncertain")
        self.assertTrue(result["processes"])
        code, message = liveness.release(self.runs, "r3", confirm=True)
        self.assertEqual(code, 2, message)

    def rollout(self, sid, complete):
        path = Path(os.environ["CODEX_HOME"]) / "sessions/2026/10/18" / f"rollout-2026-10-18T00-00-00-{sid}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ['{"type":"event_msg","payload":{"type":"task_started"}}']
        if complete:
            lines.append('{"type":"event_msg","payload":{"type":"task_complete"}}')
        path.write_text("\n".join(lines) + "\n")

    def test_codex_completion_record_and_no_processes_mean_stopped(self):
        self.record("r4", sid="0000-r4")
        self.rollout("0000-r4", complete=False)
        self.assertEqual(self.state("r4"), "uncertain")
        self.rollout("0000-r4", complete=True)
        self.assertEqual(self.state("r4"), "stopped")

    def test_grok_completion_comes_from_the_opencode_database(self):
        self.record("r5", engine="grok", sid="ses_r5")
        db = Path(os.environ["XDG_DATA_HOME"]) / "opencode/opencode.db"
        db.parent.mkdir(parents=True)
        con = sqlite3.connect(db)
        con.execute("create table message (id text, session_id text, time_created int, data text)")
        msg = {"role": "assistant", "time": {"created": 1}}
        con.execute("insert into message values ('m1','ses_r5',1,?)", (json.dumps(msg),))
        con.commit()
        self.assertEqual(self.state("r5"), "uncertain")
        msg.update(time={"created": 1, "completed": 2}, finish="stop")
        con.execute("insert into message values ('m2','ses_r5',2,?)", (json.dumps(msg),))
        con.commit()
        con.close()
        self.assertEqual(self.state("r5"), "stopped")

    def test_claude_completion_is_the_result_line(self):
        self.record("r6", engine="claude", sid="uuid")
        (self.runs / "r6.log").write_text('{"type":"assistant"}\n')
        self.assertEqual(self.state("r6"), "uncertain")
        (self.runs / "r6.log").write_text('{"type":"assistant"}\n{"type":"result","is_error":false}\n')
        self.assertEqual(self.state("r6"), "stopped")

    def test_release_refuses_live_processes_and_needs_confirm_for_missing_records(self):
        self.record("r7")
        p = self.spawn(["sleep", "30"], env={**os.environ, "FSA_RUN_ID": "r7"})
        self.assertEqual(liveness.release(self.runs, "r7", confirm=True)[0], 2)
        p.kill(); p.wait()
        self.assertEqual(liveness.release(self.runs, "r7", confirm=False)[0], 2)
        self.assertEqual(liveness.release(self.runs, "r7", confirm=True)[0], 0)
        self.assertEqual(self.state("r7"), "stopped")


class DispatchOwnershipTests(unittest.TestCase):
    def test_launcher_exit_does_not_release_a_run_whose_child_still_runs(self):
        case = DispatchCase("codex")
        self.addCleanup(case.cleanup)
        result = case.dispatch(env={"FSA_FAKE_MODE": "detach", "FSA_FAKE_SLEEP": "5"})
        self.assertEqual(result.returncode, 0, result.stderr)
        rid = case.manifest(result)["run"]
        runs = Path(case.manifest(result)["log"]).parent
        meta = json.loads((runs / f"{rid}.meta.json").read_text())
        self.assertEqual(meta["runner_pgid"], meta["runner_pid"])
        self.assertEqual(liveness.run_state(runs, rid)["state"], "running")
        released = subprocess.run(["bash", str(SCRIPTS / "codex-task.sh"), "release", rid, "--confirm"],
                                  env=case.env, capture_output=True, text=True, cwd=case.root)
        self.assertEqual(released.returncode, 2, released.stdout + released.stderr)
        self.assertIn("refused", released.stdout)


if __name__ == "__main__":
    unittest.main()
