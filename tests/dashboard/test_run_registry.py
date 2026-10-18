"""The dashboard reads the same run registry as the dispatcher: env, then the project binding, then legacy dirs."""
import json
import os
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("fsa_dashboard_registry", str(REPO / "plugins/fullstack-agents/scripts/fsa-dashboard"))
dash = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_dashboard_registry", _loader))
_loader.exec_module(dash)


class RunRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "repo"
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.primary, self.legacy = base / "kc-runs", base / "fsa-runs"
        self.primary.mkdir()
        self.legacy.mkdir()
        (self.root / ".claude").mkdir()
        (self.root / ".claude/fsa-team.conf").write_text(
            f"runs_dir={self.primary}\nlegacy_runs_dirs={self.legacy}:{base / 'missing'}\n")
        env = {k: v for k, v in os.environ.items() if k != "FSA_CODEX_RUNS_DIR"}
        self.env = patch.dict(os.environ, {**env, "HOME": str(base / "home")}, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def repo(self, runs=None):
        return dash.Repo(str(self.root), runs, [str(Path(self.tmp.name) / "claude")])

    def test_binding_sets_primary_and_existing_legacy_dirs(self):
        repo = self.repo()
        self.assertEqual(repo.runs, self.primary)
        self.assertEqual(repo.run_dirs, [self.primary, self.legacy])

    def test_env_and_explicit_argument_win_over_the_binding(self):
        with patch.dict(os.environ, {"FSA_CODEX_RUNS_DIR": str(self.legacy)}):
            self.assertEqual(self.repo().runs, self.legacy)
        self.assertEqual(self.repo(str(self.legacy)).runs, self.legacy)

    def test_runs_in_legacy_dirs_are_listed_once(self):
        rid = "implement-20261018-063525-2702849"
        for d in (self.legacy, self.primary):
            (d / f"{rid}.log").write_text("x\n")
            (d / f"{rid}.meta.json").write_text(json.dumps({"root": str(self.root), "engine": "grok"}))
        other = "implement-20261018-064001-2718939"
        (self.legacy / f"{other}.log").write_text("x\n")
        (self.legacy / f"{other}.meta.json").write_text(json.dumps({"root": str(self.root)}))
        ids = [r["id"] for r in dash.collect_runs(self.repo(), time.time())]
        self.assertEqual(sorted(ids), sorted([rid, other]))
        self.assertEqual(self.repo().run_home(other), self.legacy)


if __name__ == "__main__":
    unittest.main()
