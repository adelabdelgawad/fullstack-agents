"""fsa-runs prune on disposable registries: preview deletes nothing; --apply removes only expired, settled runs."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from dispatch_support import SCRIPTS

TOOL = SCRIPTS / "fsa-runs"
DAY = 86400


class PruneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="fsa-prune-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.runs = self.base / "runs"
        self.runs.mkdir()
        self.root = self.base / "repo"
        self.root.mkdir()

    def run_files(self, rid, days_old, result=None, released=True, schema=2, ownership="free"):
        files = {f"{rid}.meta.json": json.dumps({"schema": schema, "engine": "codex", "cwd": str(self.root)}),
                 f"{rid}.log": "log", f"{rid}.prompt.md": "brief"}
        if result:
            files[f"{rid}.result.json"] = json.dumps({"state": result, "ownership": ownership})
        if released:
            files[f"{rid}.released"] = ""
        stamp = time.time() - days_old * DAY
        for name, text in files.items():
            path = self.runs / name
            path.write_text(text)
            os.utime(path, (stamp, stamp))
        lib = self.runs / f"{rid}.lib"
        lib.mkdir()
        (lib / "x.sh").write_text("x")
        os.utime(lib / "x.sh", (stamp, stamp))
        os.utime(lib, (stamp, stamp))

    def prune(self, *extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith("FSA_")}
        out = subprocess.run([sys.executable, "-I", str(TOOL), "prune", "--root", str(self.root),
                              "--runs-dir", str(self.runs), "--keep-last", "1", "--json", *extra],
                             capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        return {r["run"]: r["action"] for r in json.loads(out.stdout)["rows"]}

    def test_preview_deletes_nothing_and_apply_removes_only_expired_settled_runs(self):
        self.run_files("implement-20260901-000000-1", 40, "succeeded")
        self.run_files("implement-20260902-000000-2", 20, "failed")
        self.run_files("implement-20260903-000000-3", 20, "succeeded")
        self.run_files("implement-20261018-000000-9", 0, "succeeded")
        before = sorted(p.name for p in self.runs.iterdir())
        plan = self.prune()
        self.assertEqual(sorted(p.name for p in self.runs.iterdir()), before)
        self.assertEqual(plan["implement-20260901-000000-1"], "delete")
        self.assertEqual(plan["implement-20260903-000000-3"], "delete")
        self.assertTrue(plan["implement-20260902-000000-2"].startswith("keep: younger than 30d"))
        self.assertEqual(plan["implement-20261018-000000-9"], "keep: newest")
        self.prune("--apply")
        left = {p.name.split(".")[0] for p in self.runs.iterdir()}
        self.assertEqual(left, {"implement-20260902-000000-2", "implement-20261018-000000-9"})

    def test_unsettled_runs_are_never_pruned(self):
        self.run_files("implement-20260901-000000-1", 90, "succeeded", released=False)  # no engine record: uncertain
        self.run_files("implement-20260902-000000-2", 90, "failed", ownership="held")
        self.run_files("implement-20261018-000000-9", 0, "succeeded")
        plan = self.prune("--apply")
        self.assertEqual(plan["implement-20260901-000000-1"], "keep: liveness uncertain")
        self.assertEqual(plan["implement-20260902-000000-2"], "keep: ownership held")
        self.assertTrue((self.runs / "implement-20260901-000000-1.log").exists())

    def test_legacy_record_changed_today_is_kept_and_unknown_outcome_uses_the_failure_window(self):
        self.run_files("implement-20260901-000000-1", 0.2, schema=1)
        self.run_files("implement-20260902-000000-2", 20, schema=1)
        self.run_files("implement-20261018-000000-9", 0, "succeeded")
        plan = self.prune()
        self.assertEqual(plan["implement-20260901-000000-1"], "keep: pre-v2 record changed within a day")
        self.assertTrue(plan["implement-20260902-000000-2"].startswith("keep: younger than 30d"))

    def test_conf_sets_the_windows_and_dispatcher_copies_age_out(self):
        (self.root / ".claude").mkdir()
        (self.root / ".claude/fsa-team.conf").write_text("runs_keep_days=2\nruns_keep_failed_days=3\n")
        self.run_files("implement-20260902-000000-2", 5, "failed")
        self.run_files("implement-20261018-000000-9", 0, "succeeded")
        old = self.runs / "dispatch-20260901-000000-5.lib"
        old.mkdir()
        os.utime(old, (time.time() - 5 * DAY,) * 2)
        plan = self.prune()
        self.assertEqual(plan["implement-20260902-000000-2"], "delete")
        self.assertEqual(plan["dispatch-20260901-000000-5.lib"], "delete")


if __name__ == "__main__":
    unittest.main()
