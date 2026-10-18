"""codex-task.sh dispatch contract with fake engines: registry location, records and arguments."""
import unittest
from pathlib import Path

from dispatch_support import DispatchCase


class RegistryLocationTests(unittest.TestCase):
    def setUp(self):
        self.case = DispatchCase("codex")

    def tearDown(self):
        self.case.cleanup()

    def run_dir_of(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(self.case.manifest(result)["log"]).parent

    def test_default_without_binding_or_env(self):
        self.assertEqual(self.run_dir_of(self.case.dispatch()), self.case.home / ".codex/fsa-runs")

    def test_project_binding_selects_the_registry(self):
        self.case.binding(runs_dir="~/.codex/kc-runs")
        self.assertEqual(self.run_dir_of(self.case.dispatch()), self.case.home / ".codex/kc-runs")

    def test_env_wins_over_the_binding(self):
        self.case.binding(runs_dir="~/.codex/kc-runs")
        chosen = self.case.base / "explicit"
        result = self.case.dispatch(env={"FSA_CODEX_RUNS_DIR": str(chosen)})
        self.assertEqual(self.run_dir_of(result), chosen)


if __name__ == "__main__":
    unittest.main()
