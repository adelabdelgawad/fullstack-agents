"""Business goals: `fsa-task goal` events and the dashboard's goal rows."""
import contextlib
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
import coordination_log
import goals

SPEC = importlib.util.spec_from_file_location("task_tracking_goal_test", LIB / "task_tracking.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)


class GoalTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-goals-")
        base = Path(self.scratch.name)
        self.root = base / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.env = patch.dict(os.environ, {"FSA_TASKS_DIR": str(base / "tasks")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.scratch.cleanup()

    def fsa(self, *argv, session="lead"):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = tasks.main(["goal", "--root", str(self.root), "--session", session, *argv])
        self.assertEqual(code, 0)
        return json.loads(out.getvalue())

    def test_add_numbers_goals_and_set_updates_them(self):
        self.assertEqual(self.fsa("add", "--title", "Launch IVR v2", "--owner", "CTO")["id"], "G1")
        self.assertEqual(self.fsa("add", "--title", "Cut cost")["id"], "G2")
        self.fsa("set", "--id", "G1", "--status", "done")
        listed = {goal["id"]: goal for goal in self.fsa("list")["goals"]}
        self.assertEqual((listed["G1"]["status"], listed["G1"]["owner"]), ("done", "CTO"))
        self.assertEqual(listed["G2"]["status"], "active")

    def test_link_defaults_to_the_current_session_and_rejects_unknown_ids(self):
        self.fsa("add", "--title", "Goal")
        self.assertEqual(self.fsa("link", "--id", "G1")["sessions"], ["lead"])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            tasks.main(["goal", "--root", str(self.root), "--session", "lead", "link", "--id", "G9"])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            tasks.main(["goal", "--root", str(self.root), "--session", "lead", "link", "--id", "G1", "--requests", "R7"])

    def test_cards_join_goals_through_sessions_and_requests(self):
        coordination_log.append(str(self.root), "worker", "request.received", id="R1", text="build it")
        self.fsa("add", "--title", "Ship")
        self.fsa("link", "--id", "G1", "--requests", "R1")
        self.fsa("link", "--id", "G1", "--sessions", "lead")
        cards = [
            {"key": "a", "phase": "complete", "sessions": [{"id": "worker"}]},
            {"key": "b", "phase": "implement", "sessions": [{"id": "lead"}]},
            {"key": "c", "phase": "plan", "sessions": [{"id": "other"}]},
        ]
        [row] = goals.for_cards(str(self.root), cards)
        self.assertEqual((row["cards"], row["done"], row["total"]), (["a", "b"], 1, 2))
        self.assertEqual([card.get("goals") for card in cards], [["G1"], ["G1"], None])


if __name__ == "__main__":
    unittest.main()
