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

    def test_herdr_reported_identity_overrides_headless_process_sessions(self):
        snap = snapshot(("x9:p1", "codex", "working", self.home),
                        ("x9:p2", "claude", "idle", self.other))
        snap["panes"][0]["agent_session"] = {"agent": "codex", "kind": "id", "value": "lead-codex"}
        snap["panes"][1]["agent_session"] = {"agent": "claude", "kind": "id", "value": "lead-claude"}
        with mock.patch.object(dash, "codex_live", return_value={"worker": ("x9:p1", 123, 2)}), \
                mock.patch.object(dash, "codex_meta", return_value={"id": "headless", "cwd": str(self.home)}), \
                mock.patch.object(dash, "codex_run_records", return_value=[]), \
                mock.patch.object(dash, "codex_children", return_value={}):
            self.assertEqual(dash.herdr_agents(snap), {
                "lead-codex": (str(self.home), "x9:p1"),
                "lead-claude": (str(self.other), "x9:p2"),
            })

    def test_without_herdr_the_home_repository_is_shown(self):
        st = self.build(snapshot(running=False))
        self.assertEqual(Path(st["repo"]).resolve(), self.home.resolve())
        self.assertNotIn("x9:p1", str(st["session_panes"]))

    def test_shared_app_server_cannot_bind_both_codex_leads_to_one_pane(self):
        snap = snapshot(("x9:p1", "codex", "working", self.home),
                        ("x9:p2", "codex", "idle", self.home))
        for pane, title in zip(snap["panes"], ["Dashboard | home", "Tags | home"]):
            pane["title"] = title
            pane["agent_session"] = {"agent": "codex", "kind": "id", "value": "tags"}
        holders = {"dashboard-path": ("x9:p1", 123, 2), "tags-path": ("x9:p1", 123, 2)}
        def metadata(path):
            return {"id": "dashboard" if str(path) == "dashboard-path" else "tags", "cwd": str(self.home)}
        with mock.patch.object(dash, "codex_live", return_value=holders), \
                mock.patch.object(dash, "codex_meta", side_effect=metadata), \
                mock.patch.object(dash, "codex_thread_names", return_value={"dashboard": "Dashboard", "tags": "Tags"}), \
                mock.patch.object(dash, "codex_children", return_value={}), \
                mock.patch.object(dash, "codex_run_records", return_value=[]):
            self.assertEqual(dash.herdr_agents(snap), {
                "dashboard": (str(self.home), "x9:p1"), "tags": (str(self.home), "x9:p2")})

    def test_claude_declared_wait_is_preserved_when_binding_its_pane(self):
        for status in ("working", "idle", "done"):
            with self.subTest(status=status):
                snap = snapshot(("x9:p1", "claude", status, self.home))
                snap["panes"][0]["agent_session"] = {"agent": "claude", "kind": "id", "value": "claude-lead"}
                session = dash.pane_session(snap["panes"][0], str(self.home), time.time())
                session.update(id="claude-lead", state="waiting", need="Confirm policy", idle=40)
                with mock.patch.object(dash, "collect_sessions", return_value=[session]), \
                        mock.patch.object(dash, "collect_codex_sessions", return_value=[]), \
                        mock.patch.object(dash, "fresh_sessions", return_value=[]), \
                        mock.patch.object(dash, "collect_runs", return_value=[]), \
                        mock.patch.object(dash, "judge_turns"):
                    state = self.build(snap)
                self.assertEqual(state["cards"][0]["now"][0]["state"], "waiting")
                self.assertEqual(state["waiting"][0]["need"], "Confirm policy")
                self.assertEqual(state["session_panes"]["claude-lead"], "x9:p1")

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

    def test_waiting_pane_keeps_its_updated_time_across_polls(self):
        pane = {"pane_id": "x1:p9", "status": "blocked", "cwd": str(self.other), "agent": "grok"}
        first = dash.pane_session(pane, str(self.home), 1000.0)
        again = dash.pane_session(pane, str(self.home), 1004.0)
        self.assertEqual((first["state"], first["updated"], again["updated"]), ("waiting", 1000.0, 1000.0))
        moved = dash.pane_session({**pane, "status": "working"}, str(self.home), 1008.0)
        self.assertEqual(moved["updated"], 1008.0)

    def test_transcript_ending_in_large_attachments_is_still_read(self):
        path = Path(self.scratch.name) / "sess.jsonl"
        said = {"type": "assistant", "cwd": str(self.home), "timestamp": "2026-10-28T10:00:00Z",
                "message": {"role": "assistant", "stop_reason": "end_turn",
                            "content": [{"type": "text", "text": "Which option do you want?"}]}}
        pad = json.dumps({"type": "attachment", "attachment": {"content": "x" * 4096}}, separators=(",", ":"))
        path.write_text(json.dumps(said, separators=(",", ":")) + "\n" + (pad + "\n") * 80)
        self.assertGreater(path.stat().st_size, dash.TAIL_BYTES)
        s = dash.read_session(path, time.time(), None, {}, {})
        self.assertIsNotNone(s)
        self.assertEqual(s["cwd"], str(self.home))

    def test_cached_dashboard_finds_the_user_scope_install(self):
        plugins = Path(self.scratch.name) / "cfg" / "plugins"
        old, new = (plugins / "cache" / "mkt" / "fsa" / v / "scripts" for v in ("1.0.0", "1.0.1"))
        for d in (old, new):
            d.mkdir(parents=True)
            (d / "fsa-dashboard").write_text("")
        entries = [{"scope": "project", "installPath": str(old.parent)}, {"scope": "user", "installPath": str(new.parent)}]
        (plugins / "installed_plugins.json").write_text(json.dumps({"plugins": {"fsa@mkt": entries}}))
        self.assertEqual(dash.installed_dashboard(old / "fsa-dashboard"), new / "fsa-dashboard")
        self.assertIsNone(dash.installed_dashboard(REPO / "plugins/fullstack-agents/scripts/fsa-dashboard"))


if __name__ == "__main__":
    unittest.main()
