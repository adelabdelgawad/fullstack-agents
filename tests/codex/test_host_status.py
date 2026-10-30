"""fsa-host-status: cross-host Git facts in disposable repositories, never a real checkout."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from dispatch_support import SCRIPTS

SCRIPT = SCRIPTS / "fsa-host-status"
ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
       "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": "/nonexistent"}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=ENV,
                          check=True).stdout.strip()


def commit(repo, name, text="x"):
    (Path(repo) / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", name)
    return git(repo, "rev-parse", "HEAD")


def status(repo, *args):
    proc = subprocess.run([str(SCRIPT), "--repo", str(repo), *args], capture_output=True, text=True,
                          env=ENV, timeout=60, check=False)
    return json.loads(proc.stdout)


def snapshot(repo):
    return (git(repo, "status", "--porcelain=v1", "--untracked-files=all"),
            git(repo, "for-each-ref", "--format=%(refname) %(objectname)"),
            git(repo, "stash", "list"), git(repo, "rev-parse", "HEAD"))


class HostStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.remote, self.ucm, self.asr = root / "remote.git", root / "ucm", root / "asr"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.remote)], check=True, env=ENV)
        subprocess.run(["git", "clone", "-q", str(self.remote), str(self.ucm)], check=True, env=ENV,
                       capture_output=True)
        git(self.ucm, "checkout", "-q", "-b", "main")
        self.base = commit(self.ucm, "base.txt")
        git(self.ucm, "push", "-q", "-u", "origin", "main")
        subprocess.run(["git", "clone", "-q", str(self.remote), str(self.asr)], check=True, env=ENV)
        git(self.asr, "checkout", "-q", "-b", "asr-work")

    def tearDown(self):
        self.tmp.cleanup()

    def test_unpushed_asr_commit_is_not_available_to_ucm(self):
        local = commit(self.asr, "asr.txt")
        asr = status(self.asr, "--target", "origin/main", "--commits", local)
        self.assertFalse(asr["remote"]["branch_published"])
        self.assertEqual(asr["commits"][0]["ancestry"], "not-contained")
        self.assertIn("fast-forward", asr["commits"][0]["options"])
        ucm = status(self.ucm, "--fetch", "--commits", local)
        self.assertEqual(ucm["fetch"], "ok")
        self.assertIsNone(ucm["commits"][0]["resolved"])
        self.assertEqual(ucm["commits"][0]["options"], ["unknown: fetch or push first"])

    def test_pushed_ucm_commit_needs_fetch_then_merge_on_a_published_branch(self):
        commit(self.asr, "asr.txt")
        git(self.asr, "push", "-q", "-u", "origin", "asr-work")
        pushed = commit(self.ucm, "ucm.txt")
        git(self.ucm, "push", "-q", "origin", "main")
        self.assertIsNone(status(self.asr, "--commits", pushed)["commits"][0]["resolved"])
        fetched = status(self.asr, "--fetch", "--commits", pushed)["commits"][0]
        self.assertEqual(fetched["ancestry"], "not-contained")
        self.assertIn("merge", fetched["options"])
        self.assertFalse(any(o.startswith("rebase") for o in fetched["options"]))

    def test_diverged_dirty_worktrees_are_reported_and_left_untouched(self):
        commit(self.asr, "asr.txt")
        git(self.asr, "push", "-q", "-u", "origin", "asr-work")
        git(self.asr, "reset", "-q", "--hard", "HEAD~1")
        commit(self.asr, "other.txt")
        (self.asr / "base.txt").write_text("unfinished")
        (self.asr / "new.txt").write_text("untracked")
        before = snapshot(self.asr)
        report = status(self.asr)
        self.assertEqual((report["ahead"], report["behind"]), (1, 1))
        self.assertEqual((report["dirty"]["unstaged"], report["dirty"]["untracked"]), (1, 1))
        self.assertEqual(snapshot(self.asr), before)

    def test_unreachable_remote_is_reported_not_assumed_in_sync(self):
        git(self.ucm, "remote", "set-url", "origin", str(Path(self.tmp.name) / "missing.git"))
        report = status(self.ucm, "--timeout", "5")
        self.assertFalse(report["remote"]["reachable"])
        self.assertIsNone(report["remote"]["branch_published"])
        self.assertEqual((report["ahead"], report["behind"]), (0, 0))

    def test_missing_remote_branch_and_stale_tracking_ref(self):
        self.assertFalse(status(self.asr)["remote"]["branch_published"])
        commit(self.ucm, "ucm.txt")
        subprocess.run(["git", "-C", str(self.ucm), "push", "-q", str(self.remote), "main"], check=True, env=ENV)
        self.assertTrue(status(self.ucm)["upstream_stale"])

    def test_running_revision_is_a_comparison_not_deployment_evidence(self):
        new = commit(self.ucm, "ucm.txt")
        report = status(self.ucm, "--commits", new, "--running", self.base)
        self.assertEqual(report["commits"][0]["ancestry"], "contained")
        self.assertEqual(report["running"]["contains"][new], "not-contained")
        self.assertIn("comparison only", report["running"]["evidence"])

    def test_cherry_picked_commit_is_patch_equivalent_but_not_an_ancestor(self):
        git(self.asr, "checkout", "-q", "-b", "feature")
        picked = commit(self.asr, "fix.txt", "fix")
        git(self.asr, "checkout", "-q", "asr-work")
        commit(self.asr, "unrelated.txt")
        git(self.asr, "cherry-pick", picked)
        entry = status(self.asr, "--commits", picked)["commits"][0]
        self.assertEqual((entry["ancestry"], entry["patch"]), ("not-contained", "equivalent"))
        self.assertTrue(entry["options"][0].startswith("none: an equivalent patch"))

    def test_merge_commit_patch_identity_is_unknown(self):
        git(self.asr, "checkout", "-q", "-b", "side")
        commit(self.asr, "side.txt")
        git(self.asr, "checkout", "-q", "asr-work")
        commit(self.asr, "main-side.txt")
        git(self.asr, "merge", "-q", "--no-edit", "side")
        merge = git(self.asr, "rev-parse", "HEAD")
        git(self.asr, "checkout", "-q", "-b", "elsewhere", self.base)
        entry = status(self.asr, "--commits", merge)["commits"][0]
        self.assertEqual((entry["ancestry"], entry["patch"]), ("not-contained", "unknown"))


if __name__ == "__main__":
    unittest.main()
