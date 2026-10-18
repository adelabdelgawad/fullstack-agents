"""The Codex bundle hook is role-aware: a dispatched implementer gets no lead doctrine; standalone Codex is unchanged."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "integrations/codex/scripts"
sys.path.insert(0, str(SCRIPTS))
from build import render  # noqa: E402

BASELINE = "5e78c14"
SUBSTANTIVE = {"prompt": "Please investigate the slow backend request and fix it", "session_id": "s-roles"}


def hook(script, mode, payload, role=None, home=None):
    env = {k: v for k, v in os.environ.items() if k != "FSA_ROLE"}
    if role:
        env["FSA_ROLE"] = role
    if home:
        env.update(HOME=str(home), CODEX_HOME=str(home / ".codex"))
    return subprocess.run([sys.executable, str(script), mode], input=json.dumps(payload), capture_output=True,
                          text=True, env=env)


class CodexRoleHookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="fsa-roles-")
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_implementer_role_gets_only_the_implementer_pointer(self):
        start = hook(SCRIPTS / "hook.py", "start", {"source": "startup"}, "implementer", self.home)
        self.assertEqual(start.returncode, 0, start.stderr)
        text = json.loads(start.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("dispatched implementer run", text)
        self.assertNotIn("Codex leads", text)
        self.assertNotIn("Ownership and flow", text)
        for mode, payload in (("prompt", SUBSTANTIVE), ("stop", {"session_id": "s-roles", "cwd": str(self.home)})):
            with self.subTest(mode=mode):
                result = hook(SCRIPTS / "hook.py", mode, payload, "implementer", self.home)
                self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)

    def test_without_a_role_the_hook_output_is_unchanged(self):
        sandbox = Path(self.tmp.name) / "codex"
        shutil.copytree(REPO / "integrations/codex", sandbox, ignore=shutil.ignore_patterns("__pycache__"))
        old = subprocess.run(["git", "-C", str(REPO), "show", f"{BASELINE}:integrations/codex/scripts/hook.py"],
                             capture_output=True, text=True, check=True).stdout
        (sandbox / "scripts/hook_baseline.py").write_text(old)
        for mode, payload in (("start", {"source": "startup"}), ("start", {"source": "resume"}), ("prompt", SUBSTANTIVE)):
            with self.subTest(mode=mode, payload=payload):
                new = hook(sandbox / "scripts/hook.py", mode, payload, home=self.home)
                base = hook(sandbox / "scripts/hook_baseline.py", mode, payload, home=self.home)
                self.assertEqual(new.stdout, base.stdout)
                self.assertEqual(new.returncode, base.returncode)

    def test_the_rendered_bundle_carries_the_role_aware_hook(self):
        bundle = Path(self.tmp.name) / "bundle"
        render(bundle)
        start = hook(bundle / "scripts/hook.py", "start", {"source": "startup"}, "implementer", self.home)
        self.assertIn("dispatched implementer run", json.loads(start.stdout)["hookSpecificOutput"]["additionalContext"])


if __name__ == "__main__":
    unittest.main()
