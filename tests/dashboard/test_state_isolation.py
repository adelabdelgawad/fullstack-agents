"""Regression guard for FSA1 unit E item 2: these test suites must never touch the real
~/.local/state/fullstack-agents or ~/.claude directories. Each runs in a subprocess with HOME pointed at a fresh
temp directory and FSA_TASKS_DIR/CLAUDE_CONFIG_DIR/FSA_STOP_GUARD_DIR unset, so a test that forgets to patch its
own isolated state directories leaks into that temp HOME and this test catches it."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

DASHBOARD = Path(__file__).resolve().parent
FILES = ("test_deploy_hold.py", "test_task_controls.py", "test_control_regressions.py")
LEAK_ENV_VARS = ("FSA_TASKS_DIR", "CLAUDE_CONFIG_DIR", "FSA_STOP_GUARD_DIR")

RUNNER = """
import importlib.util, sys, unittest
from pathlib import Path
loader = unittest.TestLoader()
suite = unittest.TestSuite()
for index, path in enumerate(sys.argv[1:]):
    spec = importlib.util.spec_from_file_location(f"fsa_isolation_target_{index}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite.addTests(loader.loadTestsFromModule(module))
result = unittest.TextTestRunner(verbosity=0).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
"""


class StateIsolationTests(unittest.TestCase):
    def test_running_the_suites_creates_nothing_under_a_clean_home(self):
        with tempfile.TemporaryDirectory(prefix="fsa-state-isolation-home-") as home:
            env = {key: value for key, value in os.environ.items() if key not in LEAK_ENV_VARS}
            env["HOME"] = home
            paths = [str(DASHBOARD / name) for name in FILES]
            result = subprocess.run([sys.executable, "-c", RUNNER, *paths], env=env, capture_output=True, text=True,
                                     timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            created = [str(path) for path in Path(home).rglob("*")]
            self.assertEqual(created, [], f"files created under a clean HOME: {created}")


if __name__ == "__main__":
    unittest.main()
