"""The dashboard is built from herdr's agent panes, across repositories, whatever harness runs in them."""
import importlib.util
import json
import os
import subprocess
import tempfile
import time
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("fsa_dashboard_herdr", str(REPO / "plugins/fullstack-agents/scripts/fsa-dashboard"))
dash = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_dashboard_herdr", _loader))
_loader.exec_module(dash)


def git_repo(path):
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "init"], check=True)
    return path


def snapshot(*panes, running=True):
    return {"running": running, "workspaces": [], "tabs": [], "focused_pane_id": None, "agent_kinds": [],
            "panes": [{"pane_id": p, "tab_id": "t", "workspace_id": "w", "title": "", "status": s, "cwd": str(c), "agent": a}
                      for p, a, s, c in panes]}


class HerdrSessionTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-dash-herdr-")
        base = Path(self.scratch.name)
        self.home, self.other = git_repo(base / "home"), git_repo(base / "other")
        self.server = dash.Server(("127.0.0.1", 0), dash.Repo(str(self.home), None, None), "t")

    def tearDown(self):
        self.server.server_close()
        self.scratch.cleanup()

    def build(self, snap):
        self.server.herdr_state = lambda: snap
        return self.server.build()

    def test_agent_pane_without_transcript_gets_a_card_in_its_own_repo(self):
        st = self.build(snapshot(("x9:p1", "grok", "blocked", self.other), ("x9:p2", None, "unknown", self.home)))
        [card] = st["cards"]
        self.assertEqual(Path(card["repo"]).resolve(), self.other.resolve())
        [s] = card["now"]
        self.assertEqual((s["engine"], s["state"]), ("grok", "waiting"))
        self.assertIn("x9:p1", s["need"])
        self.assertEqual(st["session_panes"][s["id"]], "x9:p1")

    def test_pane_outside_any_repository_is_ignored(self):
        st = self.build(snapshot(("x9:p1", "gemini", "working", Path(self.scratch.name))))
        self.assertEqual(st["cards"], [])

    def test_without_herdr_the_home_repository_is_shown(self):
        st = self.build(snapshot(running=False))
        self.assertEqual(Path(st["repo"]).resolve(), self.home.resolve())
        self.assertNotIn("x9:p1", str(st["session_panes"]))

    def test_claude_dispatched_by_another_agent_is_not_its_own_session(self):
        base = Path(self.scratch.name) / "claude"
        (base / "sessions").mkdir(parents=True)
        child = subprocess.Popen(["sleep", "30"])
        self.addCleanup(child.kill)
        for pid, sid in ((os.getpid(), "lead"), (child.pid, "implementer")):
            (base / "sessions" / f"{pid}.json").write_text(json.dumps(
                {"pid": pid, "sessionId": sid, "cwd": str(self.home), "kind": "interactive"}))
        with mock.patch.multiple(dash, CLAUDE_BASES=[str(base)], proc_pane=lambda pid: "x1:p1",
                                 codex_live=dict, codex_children=dict):
            agents = dash.herdr_agents(snapshot(("x1:p1", "claude", "working", self.home)))
        self.assertEqual(agents, {"lead": (str(self.home), "x1:p1")})

    def test_nested_in_walks_ancestors_and_stops_at_cycles(self):
        parents = {5: 4, 4: 3, 3: 1, 7: 8, 8: 7}
        self.assertTrue(dash.nested_in(5, {3}, parents.get))
        self.assertFalse(dash.nested_in(5, {9}, parents.get))
        self.assertFalse(dash.nested_in(7, {9}, parents.get))

    def test_pane_session_maps_herdr_status(self):
        now = time.time()
        pane = {"pane_id": "x1:p1", "agent": "opencode", "status": "working", "cwd": str(self.home), "title": "fix it"}
        s = dash.pane_session(pane, str(self.home), now)
        self.assertEqual((s["id"], s["state"], s["name"], s["worktree"]), ("herdr-x1:p1", "working", "fix it", ""))


if __name__ == "__main__":
    unittest.main()
