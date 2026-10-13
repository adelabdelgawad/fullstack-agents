"""Interactive Codex sessions become dashboard sessions, read from Codex's own rollout transcripts."""
import json
import tempfile
import time
import types
import unittest
from datetime import datetime, timedelta, timezone
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("fsa_dashboard", str(REPO / "plugins/fullstack-agents/scripts/fsa-dashboard"))
dash = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_dashboard", _loader))
_loader.exec_module(dash)


def stamp(ago):
    return (datetime.now(timezone.utc) - timedelta(seconds=ago)).isoformat().replace("+00:00", "Z")


def message(role, text, ago, phase=None):
    kind = "output_text" if role == "assistant" else "input_text"
    payload = {"type": "message", "role": role, "content": [{"type": kind, "text": text}]}
    if phase:
        payload["phase"] = phase
    return {"timestamp": stamp(ago), "type": "response_item", "payload": payload}


def event(kind, ago):
    return {"timestamp": stamp(ago), "type": "event_msg", "payload": {"type": kind, "turn_id": "t1"}}


class CodexSessionTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-dash-codex-")
        base = Path(self.scratch.name)
        self.root = base / "repo"
        self.root.mkdir()
        self.home = base / "codex"
        dash.CODEX_HOME, dash.CODEX_META = self.home, {}
        self.repo = types.SimpleNamespace(root=self.root)
        self.now = time.time()

    def tearDown(self):
        self.scratch.cleanup()

    def rollout(self, sid, cwd, records, name=""):
        day = datetime.fromtimestamp(self.now)
        path = self.home / "sessions" / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}" / f"rollout-{day:%Y-%m-%dT%H-%M-%S}-{sid}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        meta = {"timestamp": stamp(600), "type": "session_meta",
                "payload": {"id": sid, "cwd": str(cwd), "git": {"branch": "main"}}}
        path.write_text("".join(json.dumps(r) + "\n" for r in [meta, *records]))
        if name:
            with (self.home / "session_index.jsonl").open("a") as fh:
                fh.write(json.dumps({"id": sid, "thread_name": name}) + "\n")
        return path

    def collect(self):
        return {s["id"]: s for s in dash.collect_codex_sessions(self.repo, set(), self.now, {})}

    def test_finished_turn_is_an_idle_named_codex_session(self):
        self.rollout("s-done", self.root, [
            event("task_started", 300),
            message("user", "<environment_context><cwd>x</cwd></environment_context>", 299),
            message("user", "add the codex reader", 298),
            message("assistant", "Done: the reader is in place.", 120, "final_answer"),
            event("task_complete", 119),
        ], name="Codex reader")
        s = self.collect()["s-done"]
        self.assertEqual((s["engine"], s["name"], s["state"], s["branch"]), ("codex", "Codex reader", "idle", "main"))
        self.assertEqual(s["ask"], "add the codex reader")
        self.assertIn("reader is in place", s["said"])

    def test_open_turn_with_unanswered_tool_call_is_working(self):
        self.rollout("s-busy", self.root, [
            event("task_started", 20),
            message("user", "run the tests", 19),
            {"timestamp": stamp(5), "type": "response_item",
             "payload": {"type": "function_call", "name": "exec_command", "call_id": "c1",
                         "arguments": json.dumps({"cmd": "python3 -m unittest"})}},
        ])
        s = self.collect()["s-busy"]
        self.assertEqual(s["state"], "working")
        self.assertTrue(s["action_running"])
        self.assertEqual(s["action"], "exec_command: python3 -m unittest")

    def test_blocked_herdr_pane_means_waiting_on_the_human(self):
        path = self.rollout("s-wait", self.root, [event("task_started", 20), message("user", "deploy", 19)])
        s = dash.read_codex_session(self.repo, path, dash.codex_meta(path), self.now, {}, {}, "w2:p1", "blocked")
        self.assertEqual((s["state"], s["pane"]), ("waiting", "w2:p1"))
        self.assertTrue(s["need"])

    def test_session_in_another_repo_is_not_collected(self):
        self.rollout("s-other", self.root.parent / "elsewhere", [event("task_complete", 10)])
        self.assertNotIn("s-other", self.collect())


if __name__ == "__main__":
    unittest.main()
