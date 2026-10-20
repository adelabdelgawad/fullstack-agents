"""Deterministic recovery rendering (pure) and its I/O collector."""
import copy
import importlib.util
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
import task_checkpoint as checkpoint
import task_recovery as recovery
CLI = REPO / "plugins/fullstack-agents/scripts/fsa-task"


def _checkpoint_payload(**overrides):
    base = {
        "goal": "Ship the recovery renderer",
        "scope": {"in": ["recovery renderer"], "out": ["hooks"]},
        "approvals": [{"quote": "yes do that", "at": "2026-10-20T10:00:00Z", "scope": "recovery renderer",
                        "kind": "task", "used": False, "clarity": "ambiguous"}],
        "decisions": [{"id": "D1", "text": "Keep render pure", "source": "user 2026-10-20"}],
        "constraints": [],
        "done": [],
        "next": {"action": "Write tests", "owner": "claude"},
        "evidence": ["tests/dashboard/test_task_recovery.py"],
        "verification": [{"command": "python3 -m unittest", "result": "pass", "log": "scratch/log.txt",
                           "run_at": "2026-10-20T10:05:00Z", "paths": ["TASKS.md"]}],
        "status": "active",
    }
    base.update(overrides)
    return base


def _info(**overrides):
    base = {
        "task_id": "T",
        "ledger": {"title": "T", "items": [{"id": "T1", "status": "pending", "title": "Do a thing", "note": ""}]},
        "checkpoint_path": "/repo/TASKS.md",
        "checkpoint": None,
        "checkpoint_error": None,
        "owner": {"session_id": "sess-1"},
        "owner_state": "live",
        "git_identity": {"checkout": "/repo", "branch": "main", "head": "a" * 40, "detached": False},
        "compaction": None,
        "verification_tags": [],
    }
    base.update(overrides)
    return base


class RenderBudgetTests(unittest.TestCase):
    def _big_checkpoint(self):
        checkpoint = _checkpoint_payload(
            decisions=[{"id": f"D{i}", "text": "decide " * 20, "source": "u"} for i in range(40)],
            approvals=[{"quote": "q" * 50, "at": "t", "scope": "s" * 50, "kind": "task", "used": False,
                        "clarity": "ambiguous"} for _ in range(40)],
            scope={"in": ["x" * 400], "out": ["y" * 400]},
            evidence=[f"evidence/{i}.txt" for i in range(40)],
            verification=[{"command": f"cmd {i}", "result": "pass", "log": "l", "run_at": "t", "paths": ["x"]}
                          for i in range(40)],
        )
        checkpoint["identity"] = {"schema": 1, "task_id": "T", "root": "/repo", "checkout": "/repo",
                                  "branch": "main", "head": "a" * 40, "detached": False, "session_id": "s",
                                  "written_at": "2026-10-20T00:00:00Z"}
        return checkpoint

    def test_stays_under_cap_with_tier0_intact_and_exact_omission_counts(self):
        big = self._big_checkpoint()
        info = _info(checkpoint=big, verification_tags=["inputs unchanged"] * 40)
        rendered = recovery.render(info)
        self.assertLessEqual(len(rendered), recovery.CAP)
        self.assertIn("Task: T", rendered)
        self.assertIn("Checkout: /repo", rendered)
        self.assertIn("Owner: sess-1 (live)", rendered)
        self.assertIn("Omitted:", rendered)
        self.assertIn("40 decisions", rendered)
        self.assertIn("40 verification entries", rendered)
        self.assertIn("40 evidence", rendered)
        self.assertIn("Reading the full checkpoint is required before any edit or dispatch.", rendered)
        self.assertTrue(rendered.rstrip().endswith(recovery.FOOTER))

    def test_huge_blockers_and_next_action_stay_under_cap_with_footer_and_omission_intact(self):
        checkpoint = self._big_checkpoint()
        checkpoint["blockers"] = ["blocker " * 62 + str(i) for i in range(40)]
        checkpoint["next"] = {"action": "do " * 125, "owner": "claude"}
        warnings_info = _info(
            checkpoint=checkpoint, verification_tags=["inputs unchanged"] * 40,
            checkpoint_error="x" * 500,
            compaction={"stale_checkpoint": True},
            git_identity={"checkout": "/repo", "branch": "main", "head": "a" * 40, "detached": False},
        )
        rendered = recovery.render(warnings_info)
        self.assertLessEqual(len(rendered), recovery.CAP)
        self.assertTrue(rendered.rstrip().endswith(recovery.FOOTER))
        self.assertIn("Task: T", rendered)
        self.assertIn("Checkout: /repo", rendered)
        self.assertIn("Checkpoint path: /repo/TASKS.md", rendered)
        self.assertIn("Blockers:", rendered)
        self.assertIn("(+", rendered)
        self.assertIn("Next:", rendered)
        self.assertIn("Omitted:", rendered)
        first = recovery.render(copy.deepcopy(warnings_info))
        second = recovery.render(copy.deepcopy(warnings_info))
        self.assertEqual(first, second)

    def test_cut_blockers_bounds_line_and_counts_dropped_items(self):
        blockers = ["blocker " * 62 + str(i) for i in range(40)]
        text, truncated = recovery._cut_blockers(blockers, recovery.BLOCKERS_CUT)
        self.assertLessEqual(len(text), recovery.BLOCKERS_CUT)
        self.assertIn("more)", text)
        self.assertIn("[truncated]", text)
        self.assertTrue(truncated)

    def test_rendering_is_deterministic(self):
        big = self._big_checkpoint()
        info = _info(checkpoint=big, verification_tags=["inputs unchanged"] * 40)
        first = recovery.render(copy.deepcopy(info))
        second = recovery.render(copy.deepcopy(info))
        self.assertEqual(first, second)

    def test_ambiguous_approval_wording(self):
        payload = _checkpoint_payload()
        payload["identity"] = {"schema": 1, "task_id": "T", "root": "/repo", "checkout": "/repo", "branch": "main",
                               "head": "a" * 40, "detached": False, "session_id": "s", "written_at": "t"}
        info = _info(checkpoint=payload, verification_tags=["inputs unchanged"])
        rendered = recovery.render(info)
        self.assertIn("ambiguous: confirm with the user", rendered)

    def test_footer_present_and_verbatim(self):
        rendered = recovery.render(_info())
        self.assertIn(recovery.FOOTER, rendered)


class RenderVariantTests(unittest.TestCase):
    def test_no_checkpoint_shows_open_rows_and_notice(self):
        rendered = recovery.render(_info())
        self.assertIn("no checkpoint written; read the ledger", rendered)
        self.assertIn("T1 pending Do a thing", rendered)
        self.assertNotIn("Scope in:", rendered)

    def test_malformed_checkpoint_section_is_a_warning_not_a_wipeout(self):
        info = _info(checkpoint_error="Checkpoint JSON is invalid: bad")
        rendered = recovery.render(info)
        self.assertIn("Warning: checkpoint section malformed", rendered)
        self.assertIn("T1 pending Do a thing", rendered)

    def test_missing_ledger_is_a_short_fatal_message(self):
        info = {"fatal": "registered task file missing at /repo/TASKS.md — ask the user"}
        rendered = recovery.render(info)
        self.assertEqual(rendered, info["fatal"])

    def test_malformed_ledger_is_error_and_path_only(self):
        info = {"fatal": "Task Markdown must contain exactly one start marker and one end marker"}
        rendered = recovery.render(info)
        self.assertEqual(rendered, info["fatal"])

    def test_detached_branch_display(self):
        info = _info(git_identity={"checkout": "/repo", "branch": None, "head": "deadbeef" * 5, "detached": True})
        rendered = recovery.render(info)
        self.assertIn("Branch: detached deadbeef", rendered)


class RenderWarningTests(unittest.TestCase):
    def _checkpoint_with_identity(self, **identity_overrides):
        payload = _checkpoint_payload()
        identity = {"schema": 1, "task_id": "T", "root": "/repo", "checkout": "/repo", "branch": "main",
                    "head": "a" * 40, "detached": False, "session_id": "s", "written_at": "t"}
        identity.update(identity_overrides)
        payload["identity"] = identity
        return payload

    def test_head_moved_warning(self):
        payload = self._checkpoint_with_identity(head="a" * 40)
        info = _info(checkpoint=payload, verification_tags=["inputs unchanged"],
                     git_identity={"checkout": "/repo", "branch": "main", "head": "b" * 40, "detached": False})
        self.assertIn("HEAD moved since checkpoint", recovery.render(info))

    def test_branch_changed_warning(self):
        payload = self._checkpoint_with_identity(branch="main")
        info = _info(checkpoint=payload, verification_tags=["inputs unchanged"],
                     git_identity={"checkout": "/repo", "branch": "feature", "head": "a" * 40, "detached": False})
        self.assertIn("branch changed since checkpoint", recovery.render(info))

    def test_checkout_mismatch_warning(self):
        payload = self._checkpoint_with_identity(checkout="/repo")
        info = _info(checkpoint=payload, verification_tags=["inputs unchanged"],
                     git_identity={"checkout": "/other", "branch": "main", "head": "a" * 40, "detached": False})
        self.assertIn("checkout mismatch", recovery.render(info))

    def test_stale_marker_warning(self):
        payload = self._checkpoint_with_identity()
        info = _info(checkpoint=payload, verification_tags=["inputs unchanged"],
                     compaction={"stale_checkpoint": True})
        self.assertIn("stale checkpoint", recovery.render(info))

    def test_unavailable_identity_warns_without_detached_claim(self):
        payload = self._checkpoint_with_identity(branch="main")
        info = _info(checkpoint=payload, verification_tags=["inputs unchanged"],
                     git_identity={"unavailable": True, "checkout": "/repo", "branch": None, "head": None,
                                   "detached": False})
        rendered = recovery.render(info)
        self.assertIn("repository state unavailable (git failed); re-check before editing", rendered)
        self.assertNotIn("detached", rendered)
        self.assertNotIn("branch changed since checkpoint", rendered)

    def test_real_detached_identity_still_warns_branch_changed(self):
        payload = self._checkpoint_with_identity(branch="main")
        info = _info(checkpoint=payload, verification_tags=["inputs unchanged"],
                     git_identity={"checkout": "/repo", "branch": None, "head": "deadbeef" * 5, "detached": True})
        rendered = recovery.render(info)
        self.assertIn("Branch: detached deadbeef", rendered)
        self.assertIn("branch changed since checkpoint", rendered)


class TruncationMarkerTests(unittest.TestCase):
    NOTICE = "Reading the full checkpoint is required before any edit or dispatch."

    def _info_with_checkpoint(self, **overrides):
        payload = _checkpoint_payload(**overrides)
        payload["identity"] = {"schema": 1, "task_id": "T", "root": "/repo", "checkout": "/repo", "branch": "main",
                               "head": "a" * 40, "detached": False, "session_id": "s", "written_at": "t"}
        return _info(checkpoint=payload, verification_tags=["inputs unchanged"])

    def test_truncated_scope_carries_marker_and_mandatory_sentence_once(self):
        info = self._info_with_checkpoint(scope={"in": ["x" * 400], "out": []})
        rendered = recovery.render(info)
        scope_line = next(line for line in rendered.splitlines() if line.startswith("Scope in:"))
        self.assertIn("[truncated]", scope_line)
        self.assertEqual(rendered.count(self.NOTICE), 1)

    def test_truncated_next_action_carries_marker_and_mandatory_sentence_once(self):
        info = self._info_with_checkpoint(next={"action": "a" * 400, "owner": "o"})
        rendered = recovery.render(info)
        next_line = next(line for line in rendered.splitlines() if line.startswith("Next:"))
        self.assertIn("[truncated] (owner: o)", next_line)
        self.assertEqual(rendered.count(self.NOTICE), 1)

    def test_truncated_blockers_carry_marker_and_mandatory_sentence_once(self):
        info = self._info_with_checkpoint(blockers=["b" * 400])
        rendered = recovery.render(info)
        blockers_line = next(line for line in rendered.splitlines() if line.startswith("Blockers:"))
        self.assertIn("[truncated]", blockers_line)
        self.assertEqual(rendered.count(self.NOTICE), 1)

    def test_truncated_decision_carries_marker_and_mandatory_sentence_once(self):
        info = self._info_with_checkpoint(decisions=[{"id": "D1", "text": "d" * 400, "source": "u"}])
        rendered = recovery.render(info)
        decision_line = next(line for line in rendered.splitlines() if line.startswith("D1:"))
        self.assertIn("[truncated]", decision_line)
        self.assertEqual(rendered.count(self.NOTICE), 1)

    def test_long_checkpoint_path_is_never_cut(self):
        long_path = "/repo/" + "d" * 294 + "/TASKS.md"
        info = _info(checkpoint_path=long_path)
        rendered = recovery.render(info)
        self.assertIn(f"Checkpoint path: {long_path}", rendered)
        self.assertNotIn("…", rendered)


class RepoTestCase(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-recovery-")
        self.addCleanup(self.scratch.cleanup)
        self.base = Path(self.scratch.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=self.root, check=True)
        self.state = self.base / "state"
        self.env = patch.dict(os.environ, {"FSA_TASKS_DIR": str(self.state), "CLAUDE_PID": str(os.getpid())})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.path = self.root / "TASKS.md"
        self.path.write_text("# T\n\n" + tasks.START + tasks._render([tasks._item("T1", "pending", "Task", "")]) + tasks.END + "\n")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=self.root, check=True)

    def invoke(self, *args):
        return subprocess.run([sys.executable, str(CLI), *args], text=True, capture_output=True)

    def write_input(self, data):
        input_path = self.base / "checkpoint.json"
        input_path.write_text(json.dumps(data))
        return input_path

    def checkpoint_payload(self, paths=("code.py",)):
        return {"goal": "g", "scope": {"in": [], "out": []}, "approvals": [], "decisions": [], "constraints": [],
                "done": [], "next": {"action": "a", "owner": "o"}, "evidence": [],
                "verification": [{"command": "c", "result": "pass", "log": "l", "run_at": "t",
                                   "paths": list(paths)}], "status": "active"}


class CollectTests(RepoTestCase):
    def test_verification_tag_flips_after_a_commit_touching_a_listed_path(self):
        (self.root / "code.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "add code"], cwd=self.root, check=True)
        tasks.bind_tasks("sess-1", self.root, self.path)
        input_path = self.write_input(self.checkpoint_payload())
        self.invoke("checkpoint", "--root", str(self.root), "--file", "TASKS.md", "--session", "sess-1",
                    "--input", str(input_path))
        info = recovery.collect("sess-1", str(self.root))
        self.assertEqual(info["verification_tags"], ["inputs unchanged"])
        (self.root / "code.py").write_text("x = 2\n")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "touch"], cwd=self.root, check=True)
        info = recovery.collect("sess-1", str(self.root))
        self.assertEqual(info["verification_tags"], ["inputs changed"])

    def test_head_moved_and_branch_changed_warnings_surface_through_render(self):
        tasks.bind_tasks("sess-1", self.root, self.path)
        input_path = self.write_input(self.checkpoint_payload())
        self.invoke("checkpoint", "--root", str(self.root), "--file", "TASKS.md", "--session", "sess-1",
                    "--input", str(input_path))
        subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "move"], cwd=self.root, check=True)
        subprocess.run(["git", "checkout", "-q", "-b", "other"], cwd=self.root, check=True)
        info = recovery.collect("sess-1", str(self.root))
        rendered = recovery.render(info)
        self.assertIn("HEAD moved since checkpoint", rendered)
        self.assertIn("branch changed since checkpoint", rendered)

    def test_missing_ledger_file_is_a_fatal_message(self):
        tasks.bind_tasks("sess-1", self.root, self.path)
        self.path.unlink()
        info = recovery.collect("sess-1", str(self.root))
        self.assertIn("fatal", info)
        self.assertIn("ask the user", info["fatal"])

    def test_no_binding_is_a_fatal_message(self):
        info = recovery.collect("never-bound", str(self.root))
        self.assertIn("fatal", info)


class CliTests(RepoTestCase):
    def test_recover_prints_rendered_text_and_exits_zero(self):
        tasks.bind_tasks("sess-1", self.root, self.path)
        result = self.invoke("recover", "--session", "sess-1", "--cwd", str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Task: TASKS", result.stdout)
        self.assertIn(recovery.FOOTER, result.stdout)

    def test_recover_exits_two_on_error(self):
        result = self.invoke("recover", "--session", "never-bound", "--cwd", str(self.root))
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stdout.strip())

    def test_adopt_json_includes_recovery_text(self):
        tasks.bind_tasks("old-session", self.root, self.path)
        import task_ownership as ownership
        ownership.release("old-session", self.root, self.path)
        adopted = self.invoke("adopt", "--root", str(self.root), "--file", "TASKS.md",
                              "--session", "new-session", "--from", "old-session")
        self.assertEqual(adopted.returncode, 0, adopted.stderr)
        payload = json.loads(adopted.stdout)
        self.assertIn("recovery", payload)
        self.assertIn(recovery.FOOTER, payload["recovery"])


if __name__ == "__main__":
    unittest.main()
