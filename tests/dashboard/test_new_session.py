"""New sessions start the chosen agent, and a fresh Claude pane gets a card before its first prompt."""
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("fsa_dashboard_new_session", str(REPO / "plugins/fullstack-agents/scripts/fsa-dashboard"))
dash = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_dashboard_new_session", _loader))
_loader.exec_module(dash)

SNAPSHOT = {"workspaces": [{"workspace_id": "w1"}], "tabs": [], "panes": []}


def create(**extra):
    return dash.herdr_action_args({"action": "session.create", "workspace_id": "w1", "name": "probe", **extra}, SNAPSHOT)


class NewSessionTests(unittest.TestCase):
    def test_engine_is_optional_and_validated(self):
        self.assertEqual("tab", create()[0][0])
        for engine in ("claude", "codex", "grok"):
            self.assertEqual("tab", create(engine=engine)[0][0])
        with self.assertRaises(ValueError):
            create(engine="rm -rf /")

    def test_each_engine_types_its_own_command(self):
        typed = []
        ok = types.SimpleNamespace(returncode=0)

        def fake(*args, **_):
            typed.append(args)
            return ok

        created = {"root_pane": {"pane_id": "p1"}}
        with patch.object(dash, "run_herdr", fake):
            for engine in ("claude", "codex", "grok"):
                dash.start_session(created, "it's me", engine)
        texts = [a[3] for a in typed if a[:2] == ("pane", "send-text")]
        self.assertEqual(["cc -n 'it'\"'\"'s me'", "codex", "opencode -m xai/grok-4.7"], texts)
        self.assertEqual(3, sum(1 for a in typed if a[:2] == ("pane", "send-keys")))

    def test_claude_pane_without_transcript_still_gets_a_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            subprocess.run(["git", "init", "-q", "-b", "main", str(home)], check=True)
            subprocess.run(["git", "-C", str(home), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i"], check=True)
            server = dash.Server(("127.0.0.1", 0), dash.Repo(str(home), None, None), "t")
            self.addCleanup(server.server_close)
            pane = {"pane_id": "x9:p1", "tab_id": "t", "workspace_id": "w", "title": "probe", "status": "idle", "cwd": str(home),
                    "agent": "claude", "agent_session": {"agent": "claude", "kind": "id", "value": "fresh-sid"}}
            server.herdr_state = lambda: {"running": True, "workspaces": [], "tabs": [], "focused_pane_id": None, "agent_kinds": [], "panes": [pane]}
            with patch.object(dash, "collect_sessions", return_value=[]), patch.object(dash, "collect_codex_sessions", return_value=[]), \
                    patch.object(dash, "fresh_sessions", return_value=[]), patch.object(dash, "collect_runs", return_value=[]), \
                    patch.object(dash, "judge_turns"):
                st = server.build()
        [card] = st["cards"]
        self.assertEqual("fresh-sid", card["now"][0]["id"])
        self.assertEqual("x9:p1", st["session_panes"]["fresh-sid"])

if __name__ == "__main__":
    unittest.main()
