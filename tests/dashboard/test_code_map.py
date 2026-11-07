import fcntl
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

PLUGIN = Path(__file__).resolve().parents[2] / "plugins/fullstack-agents"
sys.path.insert(0, str(PLUGIN / "scripts/lib"))

import code_map


class FakeExtractor:
    """ROUTE:<key> lines are providers and CALL:<key> lines consumers; records every scanned path."""

    def __init__(self, version="t1"):
        self.VERSION = version
        self.calls = []

    def extract(self, path, text):
        self.calls.append(path)
        facts = []
        for number, line in enumerate(text.splitlines(), 1):
            for marker, role in (("ROUTE:", "provider"), ("CALL:", "calls")):
                if marker in line:
                    facts.append(["route", line.split(marker, 1)[1].strip(), number, role, "fake"])
        return facts


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t"})


class CodeMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "repo"
        self.cache = base / "cache"
        self.env = mock.patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.cache), "HOME": str(base)})
        self.env.start()
        self.root.mkdir()
        git(self.root, "init", "-q", "-b", "main")
        self.write("api.py", "ROUTE: GET /items\n")
        self.write("page.ts", "CALL: GET /items\n")
        self.write(".claude/fsa-team.conf", "code_map=on\n")
        self.commit()
        self.fx = FakeExtractor()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def write(self, rel, text, age_s=100):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        stamp = time.time_ns() - int(age_s * 1e9)
        os.utime(path, ns=(stamp, stamp))

    def commit(self):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "c")

    def query(self, seeds=("/items",), **kw):
        return code_map.query(str(self.root), list(seeds), extractor=self.fx, **kw)

    def keys(self, result):
        return {(r["from"], r["to"]) for r in result["rows"]}

    def store(self):
        return code_map.store_dir(str(self.root.resolve()))

    def test_off_by_default_touches_nothing(self):
        (self.root / ".claude/fsa-team.conf").write_text("")
        result = self.query()
        self.assertEqual(result["status"], "off")
        self.assertFalse(self.cache.exists())
        self.assertEqual(self.fx.calls, [])

    def test_joins_consumer_to_provider_and_tree_stays_clean(self):
        result = self.query()
        self.assertEqual(result["status"], "ok", result)
        self.assertEqual(self.keys(result), {("page.ts:1", "api.py:1")})
        self.assertEqual(result["rows"][0]["relation"], "calls")
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.root, capture_output=True, text=True,
                                check=False)
        self.assertEqual(status.stdout, "")
        self.assertFalse(str(self.store()).startswith(str(self.root)))

    def test_unchanged_files_are_reused_without_reading(self):
        self.query()
        self.fx.calls.clear()
        result = self.query()
        self.assertEqual(self.fx.calls, [])
        self.assertEqual(result["stats"]["reused"], 2)

    def test_edit_rescans_only_that_file(self):
        self.query()
        self.fx.calls.clear()
        self.write("page.ts", "\nCALL: GET /items\nCALL: GET /items\n", age_s=50)
        result = self.query()
        self.assertEqual(self.fx.calls, ["page.ts"])
        self.assertEqual(self.keys(result), {("page.ts:2", "api.py:1"), ("page.ts:3", "api.py:1")})

    def test_racy_same_size_same_mtime_edit_is_detected(self):
        self.write("page.ts", "CALL: GET /items\n", age_s=0)
        before = (self.root / "page.ts").stat().st_mtime_ns
        self.query()
        (self.root / "page.ts").write_text("CALL: GET /itemz\n")
        os.utime(self.root / "page.ts", ns=(before, before))
        result = self.query(seeds=("/itemz",))
        self.assertEqual([r["from"] for r in result["rows"]], ["page.ts:1"])

    def test_rename_and_delete_drop_old_entries(self):
        self.query()
        git(self.root, "mv", "page.ts", "client.ts")
        (self.root / "api.py").unlink()
        self.write("routes.py", "ROUTE: GET /items\n")
        result = self.query()
        self.assertEqual(self.keys(result), {("client.ts:1", "routes.py:1")})
        self.assertEqual(result["stats"]["dropped"], 2)

    def test_untracked_files_count_and_ignored_files_do_not(self):
        self.write(".gitignore", "build/\n")
        self.write("build/gen.ts", "CALL: GET /items\n")
        self.write("extra.ts", "CALL: GET /items\n")
        result = self.query()
        froms = {r["from"] for r in result["rows"]}
        self.assertIn("extra.ts:1", froms)
        self.assertNotIn("build/gen.ts:1", froms)

    def test_branch_switch_reflects_the_checked_out_tree(self):
        git(self.root, "checkout", "-q", "-b", "other")
        self.write("api.py", "ROUTE: GET /other/branch\n")
        self.commit()
        self.assertEqual(self.query(seeds=("/other",))["status"], "fallback")
        git(self.root, "checkout", "-q", "main")
        result = self.query()
        self.assertEqual(self.keys(result), {("page.ts:1", "api.py:1")})
        self.assertEqual(self.query(seeds=("/other",))["rows"], [])

    def test_interrupted_or_partial_store_is_rebuilt(self):
        self.query()
        store = self.store()
        (store / "index.json.999.tmp").write_text("{")
        (store / "index.json").write_text('{"format": 1, "complete": false, "files": {}}')
        result = self.query()
        self.assertTrue(result["stats"]["rebuilt"])
        self.assertEqual(result["status"], "ok")

    def test_format_or_extractor_version_change_rebuilds(self):
        self.query()
        with mock.patch.object(code_map, "FORMAT", 99):
            self.assertTrue(self.query()["stats"]["rebuilt"])
        self.fx.VERSION = "t2"
        self.assertTrue(self.query()["stats"]["rebuilt"])
        self.assertFalse(self.query()["stats"]["rebuilt"])

    def test_git_unavailable_falls_back(self):
        with mock.patch.dict(os.environ, {"PATH": self.tmp.name}):
            result = self.query()
        self.assertEqual(result["status"], "fallback")
        self.assertIn("git unavailable", result["reason"])

    def test_busy_lock_falls_back(self):
        store = self.store()
        store.mkdir(parents=True)
        with open(store / "lock", "w") as handle, mock.patch.object(code_map, "LOCK_TIMEOUT_S", 0.1):
            fcntl.flock(handle, fcntl.LOCK_EX)
            result = self.query()
        self.assertEqual(result["status"], "fallback")
        self.assertIn("lock busy", result["reason"])

    def test_invalid_conf_value_falls_back(self):
        (self.root / ".claude/fsa-team.conf").write_text("code_map=maybe\n")
        result = self.query()
        self.assertEqual(result["status"], "fallback")
        self.assertIn("code_map", result["reason"])

    def test_unborn_head_works(self):
        fresh = Path(self.tmp.name) / "fresh"
        fresh.mkdir()
        git(fresh, "init", "-q")
        (fresh / ".claude").mkdir()
        (fresh / ".claude/fsa-team.conf").write_text("code_map=on\n")
        (fresh / "a.py").write_text("ROUTE: GET /items\n")
        (fresh / "b.ts").write_text("CALL: GET /items\n")
        result = code_map.query(str(fresh), ["/items"], extractor=self.fx)
        self.assertEqual(result["status"], "ok", result)

    def test_unmatched_provider_and_budget(self):
        self.write("more.ts", "CALL: GET /items\nCALL: GET /items\nCALL: GET /missing\n")
        missing = self.query(seeds=("/missing",))
        self.assertEqual(missing["status"], "fallback")
        self.assertEqual(missing["rows"][0]["to"], "")
        self.assertIn("no joined row", missing["reason"])
        capped = self.query(budget=2)
        self.assertEqual(len(capped["rows"]), 2)
        self.assertTrue(capped["truncated"])

    def test_binary_and_oversized_files_yield_no_facts(self):
        (self.root / "blob.json").write_bytes(b"\0CALL: GET /items\n")
        with mock.patch.object(code_map, "MAX_BYTES", 30):
            self.write("big.ts", "CALL: GET /items\n" * 5)
            result = self.query()
        froms = {r["from"].split(":")[0] for r in result["rows"]}
        self.assertNotIn("blob.json", froms)
        self.assertNotIn("big.ts", froms)

    def test_extractor_crash_falls_back_and_symlinks_are_skipped(self):
        os.symlink(self.root / "api.py", self.root / "link.py")
        self.assertNotIn("link.py", {r["to"].split(":")[0] for r in self.query()["rows"]})
        self.fx.VERSION = "boom"
        self.fx.extract = mock.Mock(side_effect=RuntimeError("bad pattern"))
        result = self.query()
        self.assertEqual(result["status"], "fallback")
        self.assertIn("RuntimeError", result["reason"])

    def test_cli_exit_codes(self):
        with mock.patch.object(code_map, "_default_extractor", return_value=self.fx):
            self.assertEqual(code_map.main(["--cwd", str(self.root), "--seed", "/items"]), 0)
            self.assertEqual(code_map.main(["--cwd", str(self.root), "--seed", "/nothing"]), 3)


class EligibleTests(unittest.TestCase):
    def test_env_examples_and_code_are_eligible(self):
        for path in ("a/b.rs", "env.dev.example", ".env", ".env.local", "x.tsx", "q.sql"):
            self.assertTrue(code_map.eligible(path), path)
        for path in ("img.png", "README.md", "Cargo.lock"):
            self.assertFalse(code_map.eligible(path), path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
