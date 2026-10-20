"""Session lifecycle hooks: SessionEnd releases this session's owner records and parks an eligible open ledger
on clear/resume; PreCompact records a compaction marker and never blocks compaction; SessionStart offers recovery
on compact, re-acquires ownership on resume, and notices a parked task on clear/fork without ever binding."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins/fullstack-agents"
LIB = PLUGIN / "scripts/lib"
HOOKS = PLUGIN / "hooks"
CLI = PLUGIN / "scripts/fsa-task"
sys.path.insert(0, str(LIB))
SPEC = importlib.util.spec_from_file_location("task_tracking", LIB / "task_tracking.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)
import task_checkpoint as checkpoint
import task_ownership as ownership
import task_lifecycle as lifecycle

STALE_PID = 2**22 + 7

CHECKPOINT_PAYLOAD = {"goal": "g", "scope": {"in": [], "out": []}, "approvals": [], "decisions": [],
                      "constraints": [], "done": [], "next": {"action": "a", "owner": "o"}, "evidence": [],
                      "verification": [], "status": "active"}


class LifecycleTestCase(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-lifecycle-")
        self.addCleanup(self.scratch.cleanup)
        self.base = Path(self.scratch.name)
        self.root = self.base / "repo"
        self.root.mkdir(parents=True)
        git_env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                  "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, env=git_env, check=True)
        self.state = self.base / "state"
        self.env = {**os.environ, "FSA_TASKS_DIR": str(self.state), "CLAUDE_PID": str(os.getpid())}
        self.path = self.root / "TASKS.md"
        self.path.write_text("# T\n\n" + tasks.START + tasks._render([tasks._item("T1", "pending", "Task", "")]) + tasks.END + "\n")
        subprocess.run(["git", "add", "-A"], cwd=self.root, env=git_env, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=self.root, env=git_env, check=True)

    def bind(self, session_id):
        old = {k: os.environ.get(k) for k in ("FSA_TASKS_DIR", "CLAUDE_PID")}
        os.environ["FSA_TASKS_DIR"] = str(self.state)
        os.environ["CLAUDE_PID"] = str(os.getpid())
        try:
            return tasks.bind_tasks(session_id, self.root, self.path)
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def run_hook(self, name, payload, env=None):
        return subprocess.run(["bash", str(HOOKS / name)], input=json.dumps(payload), capture_output=True,
                              text=True, cwd=self.root, env={**self.env, **(env or {})})

    def parked_path(self, pid=None, start=None):
        pid = os.getpid() if pid is None else pid
        start = ownership._pid_start(pid) if start is None else start
        return self.state / "parked" / f"{pid}-{start}.json"

    def compaction_path(self, session_id):
        return self.state / "compactions" / f"{session_id}.json"

    def owner_path(self):
        # Computed without ownership._record_path: that helper reads FSA_TASKS_DIR from the live
        # environment, which this process's os.environ no longer carries once the hook subprocess exits.
        key = hashlib.sha256(f"{self.root}\0{self.path}".encode()).hexdigest()
        return self.state / "owners" / (key + ".json")

    def owner_record(self):
        path = self.owner_path()
        return json.loads(path.read_text()) if path.exists() else None

    def set_owner_session(self, session_id):
        path = self.owner_path()
        record = json.loads(path.read_text())
        record["session_id"] = session_id
        path.write_text(json.dumps(record))

    def run_session_start(self, payload, env=None):
        return subprocess.run([sys.executable, "-I", str(LIB / "task_lifecycle.py"), "session-start"],
                              input=json.dumps(payload), capture_output=True, text=True, cwd=self.root,
                              env={**self.env, **(env or {})})

    def use_long_repo(self, title):
        """Rebind self.root/self.path to a repo with a long root path and the given (long) title."""
        long_root = self.base / ("root_" + "d" * 200)
        long_root.mkdir()
        git_env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                  "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=long_root, env=git_env, check=True)
        path = long_root / "TASKS.md"
        path.write_text(f"# {title}\n\n" + tasks.START + tasks._render([tasks._item("T1", "pending", "Task", "")])
                        + tasks.END + "\n")
        subprocess.run(["git", "add", "-A"], cwd=long_root, env=git_env, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=long_root, env=git_env, check=True)
        self.root, self.path = long_root, path

    def write_parked(self, old_session="sess-1", **overrides):
        identity = checkpoint.git_identity(self.root)
        record = {"schema": 1, "old_session": old_session, "reason": "clear", "root": str(self.root),
                  "file": str(self.path), "task_id": self.path.stem, "title": "T", "checkout": identity["checkout"],
                  "branch": identity["branch"], "head": identity["head"], "detached": identity["detached"],
                  "parked_at": lifecycle._now()}
        record.update(overrides)
        path = self.parked_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record))
        return path


class SessionEndTests(LifecycleTestCase):
    def test_clear_releases_and_parks_open_ledger(self):
        self.bind("sess-1")
        proc = self.run_hook("session-end", {"session_id": "sess-1", "reason": "clear", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.owner_record()["released_at"])
        parked = json.loads(self.parked_path().read_text())
        self.assertEqual(parked["old_session"], "sess-1")
        self.assertEqual(parked["file"], str(self.path))
        self.assertEqual(parked["branch"], "main")
        self.assertEqual(parked["schema"], 1)
        self.assertEqual(parked["reason"], "clear")
        self.assertFalse(parked["detached"])
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, text=True,
                              capture_output=True, check=True).stdout.strip()
        self.assertEqual(parked["head"], head)

    def test_branch_with_a_slash_is_kept_whole(self):
        subprocess.run(["git", "checkout", "-q", "-b", "feature/x"], cwd=self.root, check=True)
        self.bind("sess-1")
        proc = self.run_hook("session-end", {"session_id": "sess-1", "reason": "clear", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        parked = json.loads(self.parked_path().read_text())
        self.assertEqual(parked["branch"], "feature/x")

    def test_resume_also_parks(self):
        self.bind("sess-1")
        proc = self.run_hook("session-end", {"session_id": "sess-1", "reason": "resume", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.parked_path().exists())
        self.assertEqual(json.loads(self.parked_path().read_text())["reason"], "resume")

    def test_other_reason_releases_without_parking(self):
        self.bind("sess-1")
        proc = self.run_hook("session-end", {"session_id": "sess-1", "reason": "other", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.owner_record()["released_at"])
        self.assertFalse(self.parked_path().exists())

    def test_delayed_or_repeated_session_end_does_not_touch_new_owner(self):
        self.bind("sess-1")
        key = hashlib.sha256(f"{self.root}\0{self.path}".encode()).hexdigest()
        record_path = self.state / "owners" / (key + ".json")
        record = json.loads(record_path.read_text())
        record["session_id"] = "sess-2"
        record_path.write_text(json.dumps(record))
        for _ in range(2):
            proc = self.run_hook("session-end", {"session_id": "sess-1", "reason": "clear", "cwd": str(self.root)})
            self.assertEqual(proc.returncode, 0, proc.stderr)
        current = json.loads(record_path.read_text())
        self.assertEqual(current["session_id"], "sess-2")
        self.assertIsNone(current["released_at"])
        self.assertFalse(self.parked_path().exists())

    def test_resumed_elsewhere_different_claude_pid_skips_release(self):
        self.bind("sess-1")
        other_pid = os.getppid()
        proc = self.run_hook("session-end", {"session_id": "sess-1", "reason": "other", "cwd": str(self.root)},
                             env={"CLAUDE_PID": str(other_pid)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(self.owner_record()["released_at"])

    def test_fork_like_same_pid_never_releases_parent_record_for_a_different_session(self):
        self.bind("sess-parent")
        proc = self.run_hook("session-end", {"session_id": "sess-fork", "reason": "clear", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(self.owner_record()["released_at"])
        self.assertFalse(self.parked_path().exists())

    def test_completed_ledger_skips_parking(self):
        self.bind("sess-1")
        done = "# T\n\n" + tasks.START + tasks._render([tasks._item("T1", "done", "Task", "")]) + tasks.END + "\n"
        self.path.write_text(done)
        proc = self.run_hook("session-end", {"session_id": "sess-1", "reason": "clear", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(self.parked_path().exists())

    def test_no_binding_skips_parking(self):
        proc = self.run_hook("session-end", {"session_id": "sess-unbound", "reason": "clear", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(self.parked_path().exists())

    def test_missing_claude_pid_skips_parking_but_still_exits_zero(self):
        self.bind("sess-1")
        env = {k: v for k, v in self.env.items() if k != "CLAUDE_PID"}
        proc = subprocess.run(["bash", str(HOOKS / "session-end")],
                              input=json.dumps({"session_id": "sess-1", "reason": "clear", "cwd": str(self.root)}),
                              capture_output=True, text=True, cwd=self.root, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(self.parked_path().exists())


class PreCompactTests(LifecycleTestCase):
    def _written_timestamp(self):
        loaded, _error = checkpoint.load_checkpoint(self.path.read_text())
        return datetime.fromisoformat(loaded["identity"]["written_at"].replace("Z", "+00:00")).timestamp()

    def test_null_when_no_binding(self):
        proc = self.run_hook("pre-compact", {"session_id": "sess-x", "trigger": "manual", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")
        marker = json.loads(self.compaction_path("sess-x").read_text())
        self.assertEqual(marker["trigger"], "manual")
        self.assertIsNone(marker["stale_checkpoint"])

    def test_false_when_ledger_mtime_matches_the_checkpoint(self):
        self.bind("sess-1")
        text, _changed = checkpoint.apply(self.path.read_text(), CHECKPOINT_PAYLOAD, self.root, "TASKS", "sess-1")
        self.path.write_text(text)
        written = self._written_timestamp()
        os.utime(self.path, (written, written))
        proc = self.run_hook("pre-compact", {"session_id": "sess-1", "trigger": "auto", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        marker = json.loads(self.compaction_path("sess-1").read_text())
        self.assertFalse(marker["stale_checkpoint"])

    def test_true_when_ledger_is_written_well_after_the_checkpoint(self):
        self.bind("sess-1")
        text, _changed = checkpoint.apply(self.path.read_text(), CHECKPOINT_PAYLOAD, self.root, "TASKS", "sess-1")
        self.path.write_text(text)
        written = self._written_timestamp()
        os.utime(self.path, (written + 5, written + 5))
        proc = self.run_hook("pre-compact", {"session_id": "sess-1", "trigger": "manual", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        marker = json.loads(self.compaction_path("sess-1").read_text())
        self.assertTrue(marker["stale_checkpoint"])

    def test_garbage_stdin_exits_zero_and_silent(self):
        proc = subprocess.run(["bash", str(HOOKS / "pre-compact")], input="not json{{{", capture_output=True,
                              text=True, cwd=self.root, env=self.env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")


class ClearForkOfferTests(LifecycleTestCase):
    def test_clear_offer_happy_path_and_consumed_on_second_call(self):
        self.bind("sess-1")
        self.write_parked(old_session="sess-1")
        proc = self.run_session_start({"session_id": "sess-2", "source": "clear", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Task from the previous conversation: 'T' (1 open rows)", proc.stdout)
        self.assertIn("left by session sess-1", proc.stdout)
        self.assertIn("fsa-task adopt --root", proc.stdout)
        self.assertIn("--from sess-1", proc.stdout)
        self.assertLessEqual(len(proc.stdout.strip()), 600)
        self.assertFalse(self.parked_path().exists())
        again = self.run_session_start({"session_id": "sess-2", "source": "clear", "cwd": str(self.root)})
        self.assertEqual(again.stdout, "")

    def test_fork_wording_and_no_binding_or_owner_created(self):
        self.bind("sess-1")
        self.write_parked(old_session="sess-1", reason="fork")
        before_owner = self.owner_record()
        proc = self.run_session_start({"session_id": "sess-fork", "source": "fork", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("This fork copies session sess-1's conversation", proc.stdout)
        self.assertIn("does not own the task", proc.stdout)
        self.assertIn("fsa-task adopt --root", proc.stdout)
        self.assertLessEqual(len(proc.stdout.strip()), 600)
        self.assertEqual(self.owner_record(), before_owner)
        self.assertFalse((self.state / "sess-fork.json").exists())

    def test_expired_record_is_silent_and_consumed(self):
        self.bind("sess-1")
        old = (datetime.now(timezone.utc) - timedelta(seconds=301)).isoformat().replace("+00:00", "Z")
        self.write_parked(old_session="sess-1", parked_at=old)
        proc = self.run_session_start({"session_id": "sess-2", "source": "clear", "cwd": str(self.root)})
        self.assertEqual(proc.stdout, "")
        self.assertFalse(self.parked_path().exists())

    def test_offer_at_299_seconds_is_shown(self):
        self.bind("sess-1")
        just_in_time = (datetime.now(timezone.utc) - timedelta(seconds=299)).isoformat().replace("+00:00", "Z")
        self.write_parked(old_session="sess-1", parked_at=just_in_time)
        proc = self.run_session_start({"session_id": "sess-2", "source": "clear", "cwd": str(self.root)})
        self.assertIn("Task from the previous conversation", proc.stdout)

    def test_offer_at_301_seconds_is_not_shown(self):
        self.bind("sess-1")
        too_old = (datetime.now(timezone.utc) - timedelta(seconds=301)).isoformat().replace("+00:00", "Z")
        self.write_parked(old_session="sess-1", parked_at=too_old)
        proc = self.run_session_start({"session_id": "sess-2", "source": "clear", "cwd": str(self.root)})
        self.assertEqual(proc.stdout, "")

    def test_completed_checkpoint_is_silent(self):
        self.bind("sess-1")
        payload = dict(CHECKPOINT_PAYLOAD, status="completed")
        text, _changed = checkpoint.apply(self.path.read_text(), payload, self.root, "TASKS", "sess-1")
        self.path.write_text(text)
        self.write_parked(old_session="sess-1")
        proc = self.run_session_start({"session_id": "sess-2", "source": "clear", "cwd": str(self.root)})
        self.assertEqual(proc.stdout, "")

    def test_no_open_rows_is_silent(self):
        self.bind("sess-1")
        done = "# T\n\n" + tasks.START + tasks._render([tasks._item("T1", "done", "Task", "")]) + tasks.END + "\n"
        self.path.write_text(done)
        self.write_parked(old_session="sess-1")
        proc = self.run_session_start({"session_id": "sess-2", "source": "clear", "cwd": str(self.root)})
        self.assertEqual(proc.stdout, "")

    def test_malformed_record_is_silent_and_consumed(self):
        path = self.parked_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json")
        proc = self.run_session_start({"session_id": "sess-2", "source": "clear", "cwd": str(self.root)})
        self.assertEqual(proc.stdout, "")
        self.assertFalse(path.exists())

    def test_checkout_mismatch_other_worktree_is_silent(self):
        self.bind("sess-1")
        self.write_parked(old_session="sess-1")
        other = self.base / "other-repo"
        other.mkdir()
        git_env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                  "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=other, env=git_env, check=True)
        proc = self.run_session_start({"session_id": "sess-2", "source": "clear", "cwd": str(other)})
        self.assertEqual(proc.stdout, "")

    def test_owner_is_a_third_session_is_silent(self):
        self.bind("sess-1")
        self.set_owner_session("sess-3")
        self.write_parked(old_session="sess-1")
        proc = self.run_session_start({"session_id": "sess-2", "source": "clear", "cwd": str(self.root)})
        self.assertEqual(proc.stdout, "")

    def test_binding_gone_is_silent(self):
        self.write_parked(old_session="sess-1")
        proc = self.run_session_start({"session_id": "sess-2", "source": "clear", "cwd": str(self.root)})
        self.assertEqual(proc.stdout, "")

    def test_long_title_and_root_keep_adopt_command_intact_in_clear_notice(self):
        self.use_long_repo("x" * 200)
        self.bind("sess-1")
        self.write_parked(old_session="sess-1")
        proc = self.run_session_start({"session_id": "sess-2", "source": "clear", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        command = f"fsa-task adopt --root {self.root} --file {self.path.relative_to(self.root)} --from sess-1"
        self.assertTrue(proc.stdout.strip().endswith(command))

    def test_long_title_and_root_keep_adopt_command_intact_in_fork_notice(self):
        self.use_long_repo("x" * 200)
        self.bind("sess-1")
        self.write_parked(old_session="sess-1", reason="fork")
        proc = self.run_session_start({"session_id": "sess-fork", "source": "fork", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        command = f"fsa-task adopt --root {self.root} --file {self.path.relative_to(self.root)} --from sess-1"
        self.assertTrue(proc.stdout.strip().endswith(f"`{command}` runs."))


class CompactTests(LifecycleTestCase):
    def test_recovery_printed_and_owner_record_unchanged(self):
        self.bind("sess-1")
        text, _changed = checkpoint.apply(self.path.read_text(), CHECKPOINT_PAYLOAD, self.root, "TASKS", "sess-1")
        self.path.write_text(text)
        before = self.owner_path().read_bytes()
        proc = self.run_session_start({"session_id": "sess-1", "source": "compact", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertLessEqual(len(proc.stdout.rstrip("\n")), 2500)
        self.assertIn("Historical record written by the lead", proc.stdout)
        self.assertEqual(self.owner_path().read_bytes(), before)

    def test_other_owner_gives_one_line_and_deletes_marker(self):
        self.bind("sess-1")
        self.set_owner_session("sess-3")
        self.compaction_path("sess-1").parent.mkdir(parents=True, exist_ok=True)
        self.compaction_path("sess-1").write_text(json.dumps({"at": "x", "trigger": "manual", "stale_checkpoint": None}))
        proc = self.run_session_start({"session_id": "sess-1", "source": "compact", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("owned by session sess-3", proc.stdout)
        self.assertNotIn("Historical record written by the lead", proc.stdout)
        self.assertFalse(self.compaction_path("sess-1").exists())

    def test_no_binding_is_silent(self):
        proc = self.run_session_start({"session_id": "sess-unbound", "source": "compact", "cwd": str(self.root)})
        self.assertEqual(proc.stdout, "")


class ResumeTests(LifecycleTestCase):
    def test_acquired_when_free(self):
        self.bind("sess-1")
        self.set_owner_session("sess-1")
        record = self.owner_record()
        record["released_at"] = ownership._now()
        self.owner_path().write_text(json.dumps(record))
        proc = self.run_session_start({"session_id": "sess-1", "source": "resume", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ownership reacquired", proc.stdout)
        self.assertLessEqual(len(proc.stdout.strip()), 300)
        self.assertIsNone(self.owner_record()["released_at"])

    def test_acquired_when_stale(self):
        self.bind("sess-1")
        record = self.owner_record()
        record.update(claude_pid=STALE_PID, pid_start=1)
        self.owner_path().write_text(json.dumps(record))
        proc = self.run_session_start({"session_id": "sess-1", "source": "resume", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ownership reacquired", proc.stdout)
        self.assertEqual(self.owner_record()["claude_pid"], int(self.env["CLAUDE_PID"]))

    def test_live_elsewhere_is_untouched(self):
        self.bind("sess-1")
        child = subprocess.Popen(["sleep", "30"])
        try:
            record = self.owner_record()
            record.update(claude_pid=child.pid, pid_start=ownership._pid_start(child.pid))
            self.owner_path().write_text(json.dumps(record))
            before = self.owner_path().read_bytes()
            proc = self.run_session_start({"session_id": "sess-1", "source": "resume", "cwd": str(self.root)})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("not reacquired", proc.stdout)
            self.assertEqual(self.owner_path().read_bytes(), before)
        finally:
            child.kill()
            child.wait()

    def test_other_owner_is_untouched(self):
        self.bind("sess-1")
        self.set_owner_session("sess-3")
        before = self.owner_path().read_bytes()
        proc = self.run_session_start({"session_id": "sess-1", "source": "resume", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("owned by session sess-3", proc.stdout)
        self.assertIn("takeover needs the user's word", proc.stdout)
        self.assertEqual(self.owner_path().read_bytes(), before)

    def test_other_session_stale_record_is_untouched(self):
        self.bind("sess-1")
        self.set_owner_session("sess-3")
        record = self.owner_record()
        record.update(claude_pid=STALE_PID, pid_start=1)
        self.owner_path().write_text(json.dumps(record))
        before = self.owner_path().read_bytes()
        proc = self.run_session_start({"session_id": "sess-1", "source": "resume", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("owned by session sess-3 (stale)", proc.stdout)
        self.assertEqual(self.owner_path().read_bytes(), before)

    def test_unowned_creates_no_record(self):
        self.bind("sess-1")
        self.owner_path().unlink()
        proc = self.run_session_start({"session_id": "sess-1", "source": "resume", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("no owner record", proc.stdout)
        self.assertFalse(self.owner_path().exists())

    def test_long_title_keeps_outcome_words_and_checkpoint_note_in_resume_line(self):
        self.use_long_repo("x" * 200)
        self.bind("sess-1")
        self.set_owner_session("sess-1")
        record = self.owner_record()
        record["released_at"] = ownership._now()
        self.owner_path().write_text(json.dumps(record))
        proc = self.run_session_start({"session_id": "sess-1", "source": "resume", "cwd": str(self.root)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.strip().endswith("ownership reacquired. no checkpoint written."))
        self.assertIn("x" * 80 + "…", proc.stdout)
        self.assertNotIn("x" * 200, proc.stdout)

    def test_concurrent_resume_and_adopt_leave_exactly_one_owner(self):
        self.bind("sess-1")
        resume = subprocess.Popen([sys.executable, "-I", str(LIB / "task_lifecycle.py"), "session-start"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  cwd=self.root, env=self.env)
        adopt = subprocess.Popen([sys.executable, str(CLI), "adopt", "--root", str(self.root), "--file", "TASKS.md",
                                  "--session", "sess-2", "--from", "sess-1", "--takeover", "sess-1"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env)
        resume.communicate(json.dumps({"session_id": "sess-1", "source": "resume", "cwd": str(self.root)}), timeout=10)
        adopt.communicate(timeout=10)
        self.assertEqual(resume.returncode, 0)
        self.assertEqual(adopt.returncode, 0, adopt.communicate())
        record = self.owner_record()
        self.assertEqual(record["session_id"], "sess-2")
        self.assertFalse((self.state / "sess-1.json").exists())


class PruneTests(LifecycleTestCase):
    def test_prunes_dead_process_mismatched_start_and_expired_records(self):
        directory = self.state / "parked"
        directory.mkdir(parents=True)
        dead = directory / "999999998-1.json"
        dead.write_text(json.dumps({"schema": 1}))
        mismatched_start = directory / f"{os.getpid()}-999999.json"
        mismatched_start.write_text(json.dumps({"schema": 1}))
        expired = directory / f"{os.getppid()}-{ownership._pid_start(os.getppid())}.json"
        expired.write_text(json.dumps({"schema": 1}))
        old_time = time.time() - 90000
        os.utime(expired, (old_time, old_time))
        proc = self.run_session_start({"session_id": "sess-x", "source": "startup", "cwd": str(self.root)},
                                      env={"CLAUDE_PID": "999999997"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertFalse(dead.exists())
        self.assertFalse(mismatched_start.exists())
        self.assertFalse(expired.exists())


if __name__ == "__main__":
    unittest.main()
