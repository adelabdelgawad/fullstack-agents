import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/fullstack-agents/scripts"
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": os.environ["PATH"], "HOME": "/nonexistent"}


def run(*args, env=None, cwd=None):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, env=env, cwd=cwd, timeout=120,
                          check=False)


class FsaSessionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        project = Path(self.tmp.name) / "projects" / "-home-u-workspace-shop"
        project.mkdir(parents=True)
        lines = [
            {"type": "user", "timestamp": "2026-10-30T08:00:00Z", "message": {"content": "fix the invoice totals"}},
            {"type": "user", "timestamp": "2026-10-30T08:01:00Z", "isMeta": True, "message": {"content": "meta"}},
            {"type": "user", "timestamp": "2026-10-30T08:02:00Z",
             "message": {"content": "<task-notification>done</task-notification>"}},
            {"type": "user", "timestamp": "2026-10-30T08:03:00Z",
             "message": {"content": "<command-name>/copy</command-name>"}},
            {"type": "assistant", "timestamp": "2026-10-30T08:04:00Z",
             "message": {"id": "m1", "model": "claude-opus-5-5",
                         "usage": {"input_tokens": 10, "output_tokens": 20, "cache_read_input_tokens": 1000}}},
        ]
        (project / "abcdef12-0000-0000-0000-000000000000.jsonl").write_text("\n".join(map(json.dumps, lines)))
        self.env = {**os.environ, "CLAUDE_CONFIG_DIR": self.tmp.name, "HOME": self.tmp.name}

    def tearDown(self):
        self.tmp.cleanup()

    def test_find_matches_only_typed_prompts(self):
        out = run(SCRIPTS / "fsa-sessions", "find", "invoice", env=self.env).stdout
        self.assertIn("abcdef12-0000", out)
        self.assertIn("fix the invoice totals", out)
        self.assertEqual(run(SCRIPTS / "fsa-sessions", "find", "done", env=self.env).stdout, "")

    def test_prompts_and_list(self):
        prompts = run(SCRIPTS / "fsa-sessions", "prompts", env=self.env).stdout.splitlines()
        self.assertEqual([p.split("\t")[3] for p in prompts], ["fix the invoice totals", "/copy"])
        listing = run(SCRIPTS / "fsa-sessions", "list", env=self.env).stdout
        self.assertIn("abcdef12", listing)
        self.assertIn("1 sessions", listing)


class FsaHygieneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "app"
        self.git("init", "-q", "-b", "main", self.repo)
        (self.repo / "a.txt").write_text("a")
        self.git("-C", self.repo, "add", "a.txt")
        self.git("-C", self.repo, "commit", "-qm", "a")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        p = run("git", *args, env=GIT_ENV)
        self.assertEqual(p.returncode, 0, p.stderr)

    def add_worktree(self, name, commit=False, untracked=False):
        path = Path(self.tmp.name) / name
        self.git("-C", self.repo, "worktree", "add", "-q", "-b", name, path)
        if commit:
            (path / f"{name}.txt").write_text(name)
            self.git("-C", path, "add", f"{name}.txt")
            self.git("-C", path, "commit", "-qm", name)
        if untracked:
            (path / "notes.md").write_text("brief")
        return path

    def test_worktrees_are_classified_and_left_untouched(self):
        self.add_worktree("merged")
        self.add_worktree("notes", untracked=True)
        self.add_worktree("unmerged", commit=True)
        before = run("git", "-C", self.repo, "worktree", "list", env=GIT_ENV).stdout
        out = run(SCRIPTS / "fsa-hygiene", self.tmp.name, "--no-size", env={**os.environ, **GIT_ENV}).stdout
        verdicts = {line.split("[")[1].split("]")[0]: line.split()[0] + (" safe" if line.startswith("probably")
                                                                         else "") for line in out.splitlines()
                    if "[" in line}
        self.assertEqual(verdicts["merged"], "safe")
        self.assertEqual(verdicts["notes"], "probably safe")
        self.assertEqual(verdicts["unmerged"], "keep")
        self.assertEqual(verdicts["main"], "keep")
        self.assertEqual(run("git", "-C", self.repo, "worktree", "list", env=GIT_ENV).stdout, before)


if __name__ == "__main__":
    unittest.main()
