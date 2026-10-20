"""Checkpoint schema validation, splicing, and the checkpoint/adopt/close CLI commands."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "plugins/fullstack-agents/scripts/lib"
sys.path.insert(0, str(LIB))
SPEC = importlib.util.spec_from_file_location("task_tracking", LIB / "task_tracking.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)
import task_ownership as ownership
import task_checkpoint as checkpoint
CLI = REPO / "plugins/fullstack-agents/scripts/fsa-task"


def payload(**overrides):
    base = {
        "goal": "Ship the checkpoint section",
        "scope": {"in": ["checkpoint section"], "out": ["recovery renderer"]},
        "approvals": [{"quote": "yes do that", "at": "2026-10-19T20:00:00Z", "scope": "checkpoint section",
                        "kind": "task", "used": False, "clarity": "explicit"}],
        "decisions": [{"id": "D1", "text": "Store JSON in a fenced block", "source": "user 2026-10-19"}],
        "constraints": ["AGENTS.md binding"],
        "done": [{"text": "Wrote schema", "evidence": "task_checkpoint.py"}],
        "next": {"action": "Write tests", "owner": "claude"},
        "evidence": ["tests/dashboard/test_task_checkpoint.py"],
        "verification": [{"command": "python3 -m unittest", "result": "pass", "log": "scratch/log.txt",
                           "run_at": "2026-10-19T20:05:00Z", "paths": ["task_checkpoint.py"]}],
        "status": "active",
    }
    base.update(overrides)
    return base


class SchemaTests(unittest.TestCase):
    def test_valid_payload_round_trips(self):
        result = checkpoint.validate(payload())
        self.assertEqual(result["status"], "active")
        self.assertNotIn("identity", result)

    def test_unknown_top_level_key_is_refused(self):
        with self.assertRaises(ValueError):
            checkpoint.validate(payload(authorized=True))

    def test_unknown_nested_key_is_refused(self):
        bad = payload()
        bad["next"]["confidence"] = "high"
        with self.assertRaises(ValueError):
            checkpoint.validate(bad)

    def test_oversize_string_is_refused(self):
        bad = payload(goal="x" * 501)
        with self.assertRaises(ValueError):
            checkpoint.validate(bad)

    def test_oversize_list_is_refused(self):
        bad = payload(constraints=["c"] * 41)
        with self.assertRaises(ValueError):
            checkpoint.validate(bad)

    def test_bad_type_is_refused(self):
        for key, value in (("goal", 5), ("scope", []), ("approvals", {}), ("status", "done")):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    checkpoint.validate(payload(**{key: value}))

    def test_missing_required_key_is_refused(self):
        bad = payload()
        del bad["next"]
        with self.assertRaises(ValueError):
            checkpoint.validate(bad)

    def test_blockers_is_optional(self):
        result = checkpoint.validate(payload())
        self.assertEqual(result["blockers"], [])

    def test_identity_rejected_unless_allowed(self):
        with self.assertRaises(ValueError):
            checkpoint.validate(payload(identity={"schema": 1}))
        checkpoint.validate(payload(identity={
            "schema": 1, "task_id": "t", "root": "/r", "checkout": "/r", "branch": "main",
            "head": "abc", "session_id": "s", "written_at": "now"}), allow_identity=True)


class GitIdentityTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-identity-")
        self.addCleanup(self.scratch.cleanup)
        self.base = Path(self.scratch.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=self.root, check=True)
        (self.root / "README.md").write_text("hi\n")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=self.root, check=True)

    def test_normal_checkout(self):
        identity = checkpoint.git_identity(self.root)
        self.assertEqual(identity["branch"], "main")
        self.assertFalse(identity["detached"])
        self.assertEqual(identity["checkout"], os.path.realpath(self.root))
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, text=True,
                              capture_output=True, check=True).stdout.strip()
        self.assertEqual(identity["head"], head)

    def test_linked_worktree(self):
        worktree = self.base / "worktree"
        subprocess.run(["git", "worktree", "add", "-q", "-b", "feature", str(worktree)], cwd=self.root, check=True)
        identity = checkpoint.git_identity(worktree)
        self.assertEqual(identity["branch"], "feature")
        self.assertFalse(identity["detached"])
        self.assertEqual(identity["checkout"], os.path.realpath(worktree))

    def test_detached_head(self):
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, text=True,
                              capture_output=True, check=True).stdout.strip()
        subprocess.run(["git", "checkout", "-q", "--detach", head], cwd=self.root, check=True)
        identity = checkpoint.git_identity(self.root)
        self.assertIsNone(identity["branch"])
        self.assertTrue(identity["detached"])
        self.assertEqual(identity["head"], head)

    def test_symlinked_path_equals_target(self):
        link = self.base / "link"
        link.symlink_to(self.root)
        self.assertEqual(checkpoint.git_identity(link)["checkout"], checkpoint.git_identity(self.root)["checkout"])


class LoadCheckpointTests(unittest.TestCase):
    def test_no_section_returns_none_none(self):
        self.assertEqual(checkpoint.load_checkpoint("# T\n"), (None, None))

    def test_missing_end_marker_is_an_error_with_no_partial_data(self):
        text = checkpoint.CP_START + "\n```json\n{}\n```\n"
        result, error = checkpoint.load_checkpoint(text)
        self.assertIsNone(result)
        self.assertIsNotNone(error)

    def test_bad_json_is_an_error_with_no_partial_data(self):
        text = checkpoint.CP_START + "\n```json\nnot json\n```\n" + checkpoint.CP_END
        result, error = checkpoint.load_checkpoint(text)
        self.assertIsNone(result)
        self.assertIn("JSON", error)

    def test_schema_failure_is_an_error_with_no_partial_data(self):
        body = json.dumps({"goal": "g"})
        text = checkpoint.CP_START + f"\n```json\n{body}\n```\n" + checkpoint.CP_END
        result, error = checkpoint.load_checkpoint(text)
        self.assertIsNone(result)
        self.assertIsNotNone(error)


class RepoTestCase(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-checkpoint-")
        self.base = Path(self.scratch.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=self.root, check=True)
        self.state = self.base / "state"
        self.env = patch.dict(os.environ, {"FSA_TASKS_DIR": str(self.state), "CLAUDE_PID": str(os.getpid())})
        self.env.start()
        self.path = self.root / "TASKS.md"
        self.path.write_text("# T\n\n" + tasks.START + tasks._render([tasks._item("T1", "pending", "Task", "")]) + tasks.END + "\n")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=self.root, check=True)

    def tearDown(self):
        self.env.stop()
        self.scratch.cleanup()

    def invoke(self, *args):
        return subprocess.run([sys.executable, str(CLI), *args], text=True, capture_output=True)

    def write_input(self, data):
        input_path = self.base / "checkpoint.json"
        input_path.write_text(json.dumps(data))
        return input_path


class ApplyAndSpliceTests(RepoTestCase):
    def test_apply_inserts_after_table_and_adds_identity_and_fingerprint(self):
        text = self.path.read_text()
        new_text, changed = checkpoint.apply(text, payload(), self.root, "TASKS", "session-1")
        self.assertTrue(changed)
        self.assertIn(checkpoint.CP_START, new_text)
        self.assertLess(new_text.index(tasks.END), new_text.index(checkpoint.CP_START))
        loaded, error = checkpoint.load_checkpoint(new_text)
        self.assertIsNone(error)
        self.assertEqual(loaded["identity"]["task_id"], "TASKS")
        self.assertEqual(loaded["identity"]["session_id"], "session-1")
        self.assertIn("fingerprint", loaded["verification"][0])

    def test_unchanged_checkpoint_skips_write(self):
        text = self.path.read_text()
        first, changed = checkpoint.apply(text, payload(), self.root, "TASKS", "session-1")
        self.assertTrue(changed)
        second, changed_again = checkpoint.apply(first, payload(), self.root, "TASKS", "session-1")
        self.assertFalse(changed_again)
        self.assertEqual(first, second)

    def test_replacing_an_existing_section_keeps_it_in_place(self):
        text = self.path.read_text()
        first, _ = checkpoint.apply(text, payload(), self.root, "TASKS", "session-1")
        second, changed = checkpoint.apply(first, payload(goal="Different goal"), self.root, "TASKS", "session-1")
        self.assertTrue(changed)
        self.assertEqual(second.count(checkpoint.CP_START), 1)
        loaded, _ = checkpoint.load_checkpoint(second)
        self.assertEqual(loaded["goal"], "Different goal")

    def test_oversize_section_is_refused(self):
        huge = payload(evidence=["e" * 500] * 40)
        with self.assertRaises(ValueError):
            checkpoint.apply(self.path.read_text(), huge, self.root, "TASKS", "session-1")

    def test_fingerprint_exposes_head_and_status_hash(self):
        result = checkpoint.fingerprint(self.root, ["TASKS.md"])
        self.assertIn("head", result)
        self.assertIn("status_sha256", result)

    def test_unchanged_verification_keeps_fingerprint_new_entry_gets_fresh_one(self):
        text = self.path.read_text()
        first, _ = checkpoint.apply(text, payload(), self.root, "TASKS", "session-1")
        loaded, _ = checkpoint.load_checkpoint(first)
        head_a = loaded["verification"][0]["fingerprint"]["head"]
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "move head"], cwd=self.root, check=True)
        new_entry = {"command": "python3 -m unittest other", "result": "pass", "log": "scratch/log2.txt",
                     "run_at": "2026-10-19T20:10:00Z", "paths": ["task_checkpoint.py"]}
        updated = payload(decisions=[{"id": "D2", "text": "Carry fingerprints", "source": "lead 2026-10-19"}],
                           verification=payload()["verification"] + [new_entry])
        second, changed = checkpoint.apply(first, updated, self.root, "TASKS", "session-1")
        self.assertTrue(changed)
        loaded2, _ = checkpoint.load_checkpoint(second)
        self.assertEqual(loaded2["verification"][0]["fingerprint"]["head"], head_a)
        self.assertNotEqual(loaded2["verification"][1]["fingerprint"]["head"], head_a)

    def test_verification_entry_without_fingerprint_is_not_a_match_source(self):
        text = self.path.read_text()
        first, _ = checkpoint.apply(text, payload(), self.root, "TASKS", "session-1")
        loaded, _ = checkpoint.load_checkpoint(first)
        del loaded["verification"][0]["fingerprint"]
        hand_edited = checkpoint.splice(first, checkpoint.render(loaded, loaded["identity"]))
        second, changed = checkpoint.apply(hand_edited, payload(), self.root, "TASKS", "session-1")
        self.assertTrue(changed)
        loaded2, _ = checkpoint.load_checkpoint(second)
        self.assertIn("fingerprint", loaded2["verification"][0])


class CliCheckpointTests(RepoTestCase):
    def test_checkpoint_command_writes_section_and_is_refused_for_non_owner(self):
        bound = self.invoke("bind", "--root", str(self.root), "--file", "TASKS.md", "--session", "owner-session")
        self.assertEqual(bound.returncode, 0, bound.stderr)
        input_path = self.write_input(payload())
        result = self.invoke("checkpoint", "--root", str(self.root), "--file", "TASKS.md",
                              "--session", "owner-session", "--input", str(input_path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(checkpoint.CP_START, self.path.read_text())
        refused = self.invoke("checkpoint", "--root", str(self.root), "--file", "TASKS.md",
                               "--session", "intruder", "--input", str(input_path))
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("owner-session", refused.stderr)

    def test_checkpoint_rejects_unknown_key_without_writing(self):
        self.invoke("bind", "--root", str(self.root), "--file", "TASKS.md", "--session", "owner-session")
        original = self.path.read_bytes()
        input_path = self.write_input(payload(authorized=True))
        result = self.invoke("checkpoint", "--root", str(self.root), "--file", "TASKS.md",
                              "--session", "owner-session", "--input", str(input_path))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.path.read_bytes(), original)

    def test_unchanged_checkpoint_leaves_mtime_untouched(self):
        self.invoke("bind", "--root", str(self.root), "--file", "TASKS.md", "--session", "owner-session")
        input_path = self.write_input(payload())
        self.invoke("checkpoint", "--root", str(self.root), "--file", "TASKS.md",
                    "--session", "owner-session", "--input", str(input_path))
        before = self.path.stat().st_mtime_ns
        result = self.invoke("checkpoint", "--root", str(self.root), "--file", "TASKS.md",
                              "--session", "owner-session", "--input", str(input_path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["changed"], False)
        self.assertEqual(self.path.stat().st_mtime_ns, before)


class CliAdoptCloseTests(RepoTestCase):
    def bind(self, session):
        result = self.invoke("bind", "--root", str(self.root), "--file", "TASKS.md", "--session", session)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_adopt_moves_binding_and_removes_old_one_and_parked_record(self):
        self.bind("old-session")
        ownership.release("old-session", self.root, self.path)
        parked_dir = self.state / "parked"
        parked_dir.mkdir(parents=True, exist_ok=True)
        parked = parked_dir / "123-456.json"
        parked.write_text(json.dumps({"old_session": "old-session", "file": str(self.path)}))
        adopted = self.invoke("adopt", "--root", str(self.root), "--file", "TASKS.md",
                               "--session", "new-session", "--from", "old-session")
        self.assertEqual(adopted.returncode, 0, adopted.stderr)
        self.assertFalse((self.state / "old-session.json").exists())
        self.assertTrue((self.state / "new-session.json").exists())
        self.assertFalse(parked.exists())
        self.assertIn("## Ownership log", self.path.read_text())
        self.assertIn("adopted by new-session from old-session", self.path.read_text())

    def test_adopt_refused_when_from_session_not_bound_to_this_file(self):
        result = self.invoke("adopt", "--root", str(self.root), "--file", "TASKS.md",
                              "--session", "new-session", "--from", "never-bound")
        self.assertNotEqual(result.returncode, 0)

    def test_adopt_live_owner_requires_takeover_equal_to_from_session(self):
        self.bind("old-session")
        refused = self.invoke("adopt", "--root", str(self.root), "--file", "TASKS.md",
                               "--session", "new-session", "--from", "old-session")
        self.assertNotEqual(refused.returncode, 0)
        wrong = self.invoke("adopt", "--root", str(self.root), "--file", "TASKS.md",
                             "--session", "new-session", "--from", "old-session", "--takeover", "someone-else")
        self.assertNotEqual(wrong.returncode, 0)
        accepted = self.invoke("adopt", "--root", str(self.root), "--file", "TASKS.md",
                                "--session", "new-session", "--from", "old-session", "--takeover", "old-session")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_two_concurrent_adopts_exactly_one_wins(self):
        self.bind("old-session")
        ownership.release("old-session", self.root, self.path)
        children = [subprocess.Popen([sys.executable, str(CLI), "adopt", "--root", str(self.root), "--file", "TASKS.md",
                                       "--session", f"new-{index}", "--from", "old-session"],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for index in range(2)]
        outcomes = [child.communicate(timeout=10) for child in children]
        codes = [child.returncode for child in children]
        self.assertEqual(sorted(codes), [0, 2], outcomes)

    def test_close_refused_with_open_rows_then_completes_and_sets_checkpoint_status(self):
        self.bind("owner-session")
        input_path = self.write_input(payload())
        self.invoke("checkpoint", "--root", str(self.root), "--file", "TASKS.md",
                    "--session", "owner-session", "--input", str(input_path))
        refused = self.invoke("close", "--root", str(self.root), "--file", "TASKS.md", "--session", "owner-session")
        self.assertNotEqual(refused.returncode, 0)
        self.invoke("set", "--root", str(self.root), "--file", "TASKS.md", "--session", "owner-session",
                    "--id", "T1", "--status", "done")
        completed = self.invoke("close", "--root", str(self.root), "--file", "TASKS.md", "--session", "owner-session")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        text = self.path.read_text()
        loaded, error = checkpoint.load_checkpoint(text)
        self.assertIsNone(error)
        self.assertEqual(loaded["status"], "completed")
        self.assertTrue(json.loads(ownership._record_path(self.root, self.path).read_text())["released_at"])

    def test_close_keeps_original_verification_fingerprint(self):
        self.bind("owner-session")
        input_path = self.write_input(payload())
        self.invoke("checkpoint", "--root", str(self.root), "--file", "TASKS.md",
                    "--session", "owner-session", "--input", str(input_path))
        before, _ = checkpoint.load_checkpoint(self.path.read_text())
        before_fingerprint = before["verification"][0]["fingerprint"]
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "move head"], cwd=self.root, check=True)
        self.invoke("set", "--root", str(self.root), "--file", "TASKS.md", "--session", "owner-session",
                    "--id", "T1", "--status", "done")
        completed = self.invoke("close", "--root", str(self.root), "--file", "TASKS.md", "--session", "owner-session")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        after, _ = checkpoint.load_checkpoint(self.path.read_text())
        self.assertEqual(after["verification"][0]["fingerprint"], before_fingerprint)
        self.assertNotEqual(after["identity"]["head"], before["identity"]["head"])

    def test_close_refused_for_non_owner_session(self):
        self.bind("owner-session")
        self.invoke("set", "--root", str(self.root), "--file", "TASKS.md", "--session", "owner-session",
                    "--id", "T1", "--status", "done")
        refused = self.invoke("close", "--root", str(self.root), "--file", "TASKS.md", "--session", "intruder")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("owner-session", refused.stderr)

    def test_close_refused_with_malformed_checkpoint_section(self):
        self.bind("owner-session")
        self.invoke("set", "--root", str(self.root), "--file", "TASKS.md", "--session", "owner-session",
                    "--id", "T1", "--status", "done")
        malformed = self.path.read_text() + checkpoint.CP_START + "\n```json\nnot json\n```\n" + checkpoint.CP_END + "\n"
        self.path.write_text(malformed)
        before = self.path.read_bytes()
        refused = self.invoke("close", "--root", str(self.root), "--file", "TASKS.md", "--session", "owner-session")
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_close_deletes_parked_records_naming_this_file(self):
        self.bind("owner-session")
        self.invoke("set", "--root", str(self.root), "--file", "TASKS.md", "--session", "owner-session",
                    "--id", "T1", "--status", "done")
        parked_dir = self.state / "parked"
        parked_dir.mkdir(parents=True, exist_ok=True)
        parked = parked_dir / "9-9.json"
        parked.write_text(json.dumps({"old_session": "owner-session", "file": str(self.path)}))
        result = self.invoke("close", "--root", str(self.root), "--file", "TASKS.md", "--session", "owner-session")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(parked.exists())


if __name__ == "__main__":
    unittest.main()
