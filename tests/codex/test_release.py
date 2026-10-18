"""Pinned plugin releases, session pins and run immutability for codex-task.sh."""
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from dispatch_support import REPO, DispatchCase


def copy_plugin_repo(dest):
    """A git repository holding the working tree's plugin, so tests exercise uncommitted code."""
    for rel in (".claude-plugin", "plugins/fullstack-agents"):
        shutil.copytree(REPO / rel, dest / rel, ignore=shutil.ignore_patterns("__pycache__"))
    git = ["git", "-C", str(dest), "-c", "user.email=t@example.invalid", "-c", "user.name=T"]
    subprocess.run(["git", "init", "-q", str(dest)], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "plugin"], check=True)
    return dest / "plugins/fullstack-agents"


def writable(path):
    for p in [path, *path.rglob("*")]:
        if not p.is_symlink():
            p.chmod(p.stat().st_mode | 0o200)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="fsa-release-")
        self.base = Path(self.tmp.name)
        self.plugin = copy_plugin_repo(self.base / "src")
        self.dest = self.base / "releases"
        self.case = DispatchCase("grok")

    def tearDown(self):
        writable(self.base)
        self.case.cleanup()
        self.tmp.cleanup()

    def tool(self, *args):
        return subprocess.run(["python3", "-I", str(self.plugin / "scripts/fsa-release"), *args],
                              capture_output=True, text=True)

    def export(self):
        out = self.tool("export", "HEAD", "--repo", str(self.base / "src"), "--dest", str(self.dest))
        self.assertEqual(out.returncode, 0, out.stderr)
        return Path(out.stdout.strip())

    def dispatch(self, script, **env):
        merged = {"FSA_FAKE_MODE": "touch", "FSA_FAKE_TOUCH": "app.py", **env}
        return subprocess.run(["bash", str(script), "implement", str(self.case.brief)], env={**self.case.env, **merged},
                              capture_output=True, text=True, cwd=self.case.root, stdin=subprocess.DEVNULL)

    def test_export_is_read_only_and_verifies(self):
        release = self.export()
        self.assertTrue((release / "RELEASE.json").exists())
        self.assertFalse(os.access(release / "plugins/fullstack-agents/scripts/codex-task.sh", os.W_OK))
        self.assertEqual(self.tool("verify", str(release)).returncode, 0)
        target = release / "plugins/fullstack-agents/scripts/lib/registry.sh"
        writable(release)
        target.write_text(target.read_text() + "# tampered\n")
        self.assertEqual(self.tool("verify", str(release)).returncode, 1)
        self.assertEqual(self.tool("export", "HEAD", "--repo", str(self.base / "src"), "--dest",
                                   str(self.dest)).returncode, 2, "an existing release is never overwritten")

    def test_intact_release_dispatches_even_when_a_newer_release_exists(self):
        release = self.export()
        newer = self.dest / "9.9.9-ffffffffffff"
        shutil.copytree(release, newer)
        result = self.dispatch(release / "plugins/fullstack-agents/scripts/codex-task.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("STATUS=OK", result.stdout)
        m = self.case.manifest(result)
        meta = json.loads((Path(m["log"]).parent / f"{m['run']}.meta.json").read_text())
        self.assertEqual(meta["plugin"]["mode"], "release")

    def test_tampered_release_refuses(self):
        release = self.export()
        target = release / "plugins/fullstack-agents/scripts/lib/extract-result.py"
        writable(release)
        target.write_text(target.read_text() + "\n# tampered\n")
        result = self.dispatch(release / "plugins/fullstack-agents/scripts/codex-task.sh")
        self.assertEqual(result.returncode, 2)
        self.assertIn("STATUS=PLUGIN_TAMPERED", result.stdout)
        self.assertEqual(self.case.call_log(), [])

    def pin(self, source="startup"):
        env_file = self.base / f"env-{source}"
        hook = subprocess.run(["bash", str(self.plugin / "hooks/session-start")],
                              input=json.dumps({"session_id": "s1", "source": source}), capture_output=True, text=True,
                              cwd=self.case.root, env={**self.case.env, "CLAUDE_CONFIG_DIR": str(self.base / "cfg"),
                                                       "CLAUDE_ENV_FILE": str(env_file)})
        self.assertEqual(hook.returncode, 0, hook.stderr)
        exports = env_file.read_text()
        self.assertIn("FSA_SESSION_PIN=", exports)
        return self.base / "cfg/fullstack-agents/pins/session-s1.json"

    def test_dev_mode_refuses_after_the_source_changes_unless_accepted(self):
        pin = self.pin()
        self.assertEqual(json.loads(pin.read_text())["mode"], "dev")
        script = self.plugin / "scripts/codex-task.sh"
        self.assertEqual(self.dispatch(script, FSA_SESSION_PIN=str(pin)).returncode, 0)
        (self.plugin / "scripts/lib/registry.sh").write_text((self.plugin / "scripts/lib/registry.sh").read_text() + "\n")
        refused = self.dispatch(script, FSA_SESSION_PIN=str(pin))
        self.assertEqual(refused.returncode, 2)
        self.assertIn("STATUS=PLUGIN_CHANGED", refused.stdout)
        accepted = self.dispatch(script, FSA_SESSION_PIN=str(pin), FSA_ACCEPT_PLUGIN_CHANGE="1")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_resume_keeps_the_original_pin(self):
        pin = self.pin()
        before = pin.read_text()
        (self.plugin / "scripts/lib/registry.sh").write_text("# changed\n")
        self.pin("resume")
        self.assertEqual(pin.read_text(), before)

    def test_a_running_dispatch_is_immune_to_source_rewrites(self):
        script = self.plugin / "scripts/codex-task.sh"
        proc = subprocess.Popen(["bash", str(script), "implement", str(self.case.brief)],
                                env={**self.case.env, "FSA_FAKE_MODE": "touch,sleep", "FSA_FAKE_TOUCH": "app.py",
                                     "FSA_FAKE_SLEEP": "3"},
                                cwd=self.case.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                stdin=subprocess.DEVNULL)
        time.sleep(1.5)
        script.write_text("#!/usr/bin/env bash\nexit 99\n")
        (self.plugin / "scripts/lib/extract-result.py").write_text("import sys\nsys.exit(5)\n")
        out, err = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0, out + err)
        self.assertIn("STATUS=OK", out)


if __name__ == "__main__":
    unittest.main()
