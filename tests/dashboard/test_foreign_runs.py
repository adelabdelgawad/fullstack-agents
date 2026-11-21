"""Codex runs a session filed in another project's registry still reach that session's card."""
import importlib.util
import json
import os
from importlib.machinery import SourceFileLoader
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("fsa_dashboard_foreign_runs", str(REPO / "plugins/fullstack-agents/scripts/fsa-dashboard"))
dash = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_dashboard_foreign_runs", _loader))
_loader.exec_module(dash)


def run(registry, rid, session, result=None):
    (registry / f"{rid}.log").write_text("working\n")
    (registry / f"{rid}.meta.json").write_text(json.dumps({"session": session, "brief": f"/b/{rid}.md"}))
    if result:
        (registry / f"{rid}.result.json").write_text(json.dumps(result))


class ForeignRunTests(unittest.TestCase):
    def test_live_runs_in_other_registries_are_matched_by_session(self):
        with tempfile.TemporaryDirectory() as scratch:
            home = Path(scratch)
            own, other = home / "fsa-runs", home / "kc-runs"
            own.mkdir()
            other.mkdir()
            pid = os.getpid()
            run(other, f"implement-20261121-120000-{pid}", "lead-a")
            run(other, f"implement-20261121-120001-{pid}", "someone-else")
            run(other, "implement-20261121-120002-1", "lead-a", {"status": "succeeded"})
            run(own, f"implement-20261121-120003-{pid}", "lead-a")
            repo = types.SimpleNamespace(run_dirs=[own], projects=[])
            # A legacy run is live while its codex-task process (the pid ending its id) runs: this test's pid stands in.
            alive = patch.object(dash, "pid_alive", lambda candidate: candidate == str(pid))
            with patch.object(dash, "CODEX_HOME", home), alive:
                found = dash.foreign_runs(repo, {"lead-a"}, time.time())
        self.assertEqual([r["id"] for r in found], [f"implement-20261121-120000-{pid}"])
        self.assertEqual((found[0]["session"], found[0]["state"]), ("lead-a", "running"))

    def test_no_sessions_reads_nothing(self):
        repo = types.SimpleNamespace(run_dirs=[], projects=[])
        self.assertEqual(dash.foreign_runs(repo, set(), time.time()), [])


if __name__ == "__main__":
    unittest.main()
