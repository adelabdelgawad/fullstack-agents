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

    def init_repo(self, conf=None):
        repo = Path(self.tmp.name) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        if conf is not None:
            (repo / ".claude").mkdir()
            (repo / ".claude/fsa-team.conf").write_text(conf)
        return repo

    def test_standalone_start_delivers_the_configured_policy_profile(self):
        repo = self.init_repo("policy_profile=engineering-conventions\n")
        start = hook(SCRIPTS / "hook.py", "start", {"source": "startup", "cwd": str(repo)}, home=self.home)
        text = json.loads(start.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Policy profile engineering-conventions", text)
        self.assertIn("Repro before hypothesis", text)

    def test_unconfigured_repo_gets_no_profile_text(self):
        repo = self.init_repo()
        start = hook(SCRIPTS / "hook.py", "start", {"source": "startup", "cwd": str(repo)}, home=self.home)
        no_conf = hook(SCRIPTS / "hook.py", "start", {"source": "startup"}, home=self.home)
        self.assertEqual(start.stdout, no_conf.stdout)
        self.assertNotIn("Policy profile", start.stdout)

    def test_dispatched_implementer_gets_no_profile_text_even_when_configured(self):
        repo = self.init_repo("policy_profile=engineering-conventions\n")
        start = hook(SCRIPTS / "hook.py", "start", {"source": "startup", "cwd": str(repo)}, "implementer", self.home)
        text = json.loads(start.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("Policy profile", text)
        self.assertIn("dispatched implementer run", text)

    def test_unknown_policy_profile_name_appends_one_warning_line(self):
        repo = self.init_repo("policy_profile=does-not-exist\n")
        start = hook(SCRIPTS / "hook.py", "start", {"source": "startup", "cwd": str(repo)}, home=self.home)
        text = json.loads(start.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("Policy profile", text)
        warnings = [line for line in text.splitlines() if "policy profile" in line.lower()]
        self.assertEqual(len(warnings), 1)
        self.assertIn("does-not-exist", warnings[0])

    def test_resume_also_delivers_the_configured_policy_profile(self):
        repo = self.init_repo("policy_profile=engineering-conventions\n")
        start = hook(SCRIPTS / "hook.py", "start", {"source": "resume", "cwd": str(repo)}, home=self.home)
        text = json.loads(start.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Policy profile engineering-conventions", text)

    def test_the_rendered_bundle_ships_policy_files_and_delivers_the_profile(self):
        bundle = Path(self.tmp.name) / "bundle"
        render(bundle)
        self.assertTrue((bundle / "scripts/team_conf.py").is_file())
        self.assertTrue((bundle / "policies/engineering-conventions.md").is_file())
        repo = self.init_repo("policy_profile=engineering-conventions\n")
        start = hook(bundle / "scripts/hook.py", "start", {"source": "startup", "cwd": str(repo)}, home=self.home)
        text = json.loads(start.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Policy profile engineering-conventions", text)
        self.assertIn("Repro before hypothesis", text)


if __name__ == "__main__":
    unittest.main()
