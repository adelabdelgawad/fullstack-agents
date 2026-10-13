"""Codex cards show their running agents and get a Haiku phase verdict, like Claude cards."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "plugins/fullstack-agents/scripts"
_loader = SourceFileLoader("fsa_dashboard_agents", str(SCRIPTS / "fsa-dashboard"))
dash = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_dashboard_agents", _loader))
_loader.exec_module(dash)


def rollout(path, *records):
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    return path


class CodexAgentTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-dash-agents-")
        self.base = Path(self.scratch.name)

    def tearDown(self):
        self.scratch.cleanup()

    def test_spawned_thread_with_open_turn_is_a_running_agent(self):
        busy = rollout(self.base / "child.jsonl", {"type": "event_msg", "payload": {"type": "task_started"}})
        done = rollout(self.base / "done.jsonl", {"type": "event_msg", "payload": {"type": "task_started"}},
                       {"type": "event_msg", "payload": {"type": "task_complete"}})
        children = {"p1": [("c1", "open", str(busy), "explorer"), ("c2", "closed", str(done), "worker")]}
        items = {i["id"]: i for i in dash.codex_agent_items("p1", children, None, {}, time.time())}
        self.assertEqual((items["c1"]["state"], items["c1"]["label"]), ("running", "codex · explorer"))
        self.assertEqual(items["c2"]["state"], "completed")

    def test_agent_cli_under_the_codex_process_is_listed(self):
        nap = f"{sys.executable} -c 'import time; time.sleep(30)'"
        parent = subprocess.Popen(["/bin/bash", "-c", f"(exec -a claude {nap}) & (exec -a helper {nap}) & wait"])
        try:
            deadline = time.time() + 5
            agents = []
            while time.time() < deadline and not agents:
                agents = dash.proc_agents(parent.pid, dash.proc_children(), time.time())
                time.sleep(0.1)
            self.assertEqual([a["label"].split()[0] for a in agents], ["claude"])
            self.assertEqual(agents[0]["state"], "running")
        finally:
            subprocess.run(["pkill", "-P", str(parent.pid)])
            parent.kill()
            parent.wait()

    def test_codex_transcript_renders_in_the_output_view(self):
        path = rollout(self.base / "r.jsonl",
                       {"type": "response_item", "payload": {"type": "message", "role": "user",
                                                             "content": [{"type": "input_text", "text": "fix it"}]}},
                       {"type": "response_item", "payload": {"type": "function_call", "name": "exec_command",
                                                             "arguments": json.dumps({"cmd": "make test"})}},
                       {"type": "response_item", "payload": {"type": "message", "role": "assistant",
                                                             "content": [{"type": "output_text", "text": "Fixed."}]}})
        text = dash.render_transcript(path)
        self.assertIn("› You: fix it", text)
        self.assertIn("⚙ exec_command: make test", text)
        self.assertIn("Codex: Fixed.", text)


class PhaseClassifierTests(unittest.TestCase):
    def test_phase_verdict_is_written_to_the_team_board(self):
        with tempfile.TemporaryDirectory(prefix="fsa-classify-phase-") as tmp:
            base = Path(tmp)
            repo = base / "repo"
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            fake = base / "fake-model"
            verdict = {"phase": "audit", "awaiting": "approval", "need": "approve the merge", "confidence": 0.9}
            fake.write_text(f"#!/bin/sh\ncat >/dev/null\necho '{json.dumps({'structured_output': verdict})}'\n")
            fake.chmod(0o755)
            transcript = rollout(base / "r.jsonl",
                                 {"type": "response_item", "payload": {"type": "message", "role": "user",
                                                                       "content": [{"type": "input_text", "text": "ship it"}]}},
                                 {"type": "response_item", "payload": {"type": "message", "role": "assistant",
                                                                       "content": [{"type": "output_text", "text": "Tests pass; merge?"}]}})
            hook = {"session_id": "codex-1", "transcript_path": str(transcript), "cwd": str(repo)}
            env = {**os.environ, "FSA_CLASSIFIER_CMD": str(fake), "CLAUDE_CONFIG_DIR": str(base / "claude"),
                   "PYTHONDONTWRITEBYTECODE": "1"}
            env.pop("FSA_CLASSIFIER_RUN", None)
            run = subprocess.run([sys.executable, str(SCRIPTS / "fsa-classify"), "phase"], input=json.dumps(hook),
                                 text=True, capture_output=True, env=env, timeout=60)
            self.assertEqual(run.returncode, 0, run.stderr)
            board = json.loads((repo / ".git/fsa-team/board.json").read_text())
            self.assertEqual(board["phases"]["codex-1"]["phase"], "audit")
            self.assertEqual(board["waits"]["codex-1"]["need"], "approval: approve the merge")


if __name__ == "__main__":
    unittest.main()
