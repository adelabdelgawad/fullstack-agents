"""Codex cards group session-owned runs and native descendants."""
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
from unittest.mock import patch

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

    def test_long_native_turn_is_not_lost_after_sixty_four_kibibytes(self):
        path = rollout(self.base / "long.jsonl", {"type": "event_msg", "payload": {"type": "task_started"}})
        with path.open("a") as stream:
            for _ in range(300):
                stream.write(json.dumps({"type": "response_item", "payload": {"type": "reasoning", "text": "x" * 500}}) + "\n")
        children = {"lead": [("child", "open", str(path), "worker")]}
        self.assertEqual(dash.codex_agent_items("lead", children, None, {}, time.time())[0]["state"], "running")
        with path.open("a") as stream:
            stream.write(json.dumps({"type": "event_msg", "payload": {"type": "task_complete"}}) + "\n")
        self.assertFalse(dash.codex_turn_open(path))

    def test_turn_scan_is_incremental_and_only_native_boundaries_count(self):
        path = rollout(self.base / "events.jsonl", {"type": "event_msg", "payload": {"type": "task_started"}})
        self.assertTrue(dash.codex_turn_open(path))
        self.assertEqual(dash.CODEX_TURN_SCAN[str(path)][3], path.stat().st_size)
        offset = path.stat().st_size
        real_open = open
        with real_open(path, "rb") as stream:
            with patch("builtins.open", return_value=stream), patch.object(stream, "seek", wraps=stream.seek) as seek:
                self.assertTrue(dash.codex_turn_open(path))
                seek.assert_called_once_with(offset)
        with path.open("a") as stream:
            stream.write(json.dumps({"type": "response_item", "payload": {"type": "task_complete"}}) + "\n")
            stream.write(json.dumps({"type": "response_item", "payload": {"type": "task_complete"}, "oversized": "x" * 200000}) + "\n")
            stream.write('{"type":"event_msg","payload":{"type":"task_complete"}}')
        self.assertTrue(dash.codex_turn_open(path))
        self.assertLess(dash.CODEX_TURN_SCAN[str(path)][3], path.stat().st_size)
        with path.open("a") as stream:
            stream.write("\n")
        self.assertFalse(dash.codex_turn_open(path))
        with path.open("a") as stream:
            stream.write(json.dumps({"type": "event_msg", "payload": {"type": "task_started"}}) + "\n")
        self.assertTrue(dash.codex_turn_open(path))

    def test_turn_scan_resets_on_truncation_replacement_and_same_size_rewrite(self):
        path = rollout(self.base / "replace.jsonl", {"type": "event_msg", "payload": {"type": "task_started"}})
        self.assertTrue(dash.codex_turn_open(path))
        path.write_text("{}\n")
        self.assertFalse(dash.codex_turn_open(path))
        replacement = rollout(self.base / "new.jsonl", {"type": "event_msg", "payload": {"type": "task_started"}})
        replacement.replace(path)
        self.assertTrue(dash.codex_turn_open(path))
        size, mtime = path.stat().st_size, path.stat().st_mtime_ns
        path.write_text(" " * (size - 3) + "{}\n")
        os.utime(path, ns=(mtime + 1000000, mtime + 1000000))
        self.assertFalse(dash.codex_turn_open(path))

    def test_large_native_completion_closes_turn_but_tool_text_does_not(self):
        path = rollout(self.base / "large-final.jsonl", {"type": "event_msg", "payload": {"type": "task_started"}})
        self.assertTrue(dash.codex_turn_open(path))
        fake = {"type": "response_item", "payload": {"type": "message", "text":
            '{"type":"event_msg","payload":{"type":"task_complete"}}' + "x" * 200000}}
        with path.open("a") as stream:
            stream.write(json.dumps(fake) + "\n")
        self.assertTrue(dash.codex_turn_open(path))
        complete = json.dumps({"timestamp": "2026-10-15T20:00:00Z", "type": "event_msg",
            "payload": {"type": "task_complete", "last_agent_message": "x" * 200000}})
        with path.open("a") as stream:
            stream.write(complete)
        self.assertTrue(dash.codex_turn_open(path))  # incomplete native write
        with path.open("a") as stream:
            stream.write("\n")
        self.assertFalse(dash.codex_turn_open(path))
        # Cold startup and append scans must agree for the same large record.
        dash.CODEX_TURN_SCAN.pop(str(path))
        self.assertFalse(dash.codex_turn_open(path))

    def test_no_boundary_and_copytruncate_regrowth_do_not_reuse_old_turn(self):
        path = rollout(self.base / "copytruncate.jsonl", {"type": "event_msg", "payload": {"type": "task_started"}})
        padding = json.dumps({"type": "response_item", "payload": {"text": "x" * 200000}}) + "\n"
        with path.open("a") as stream:
            stream.write(padding)
        self.assertTrue(dash.codex_turn_open(path))
        # Same inode, file grows past the cached size before the next poll.
        path.write_text(json.dumps({"type": "event_msg", "payload": {"type": "task_complete"}}) + "\n" + padding + "{}\n")
        self.assertFalse(dash.codex_turn_open(path))
        with path.open("a") as stream:
            stream.write(json.dumps({"type": "event_msg", "payload": {"type": "task_started"}}) + "\n")
        self.assertTrue(dash.codex_turn_open(path))
        no_boundary = rollout(self.base / "no-boundary.jsonl", {"type": "event_msg", "payload": {"type": "token_count"}})
        self.assertFalse(dash.codex_turn_open(no_boundary))

    def test_closed_native_edge_cannot_report_an_open_rollout_as_running(self):
        path = rollout(self.base / "closed.jsonl", {"type": "event_msg", "payload": {"type": "task_started"}})
        children = {"lead": [("child", "closed", str(path), "worker")]}
        self.assertEqual(dash.codex_agent_items("lead", children, None, {}, time.time())[0]["state"], "completed")

    def test_shared_app_server_does_not_mix_independent_leads(self):
        with patch.object(dash, "proc_agents") as processes:
            for sid in ("lead-one", "lead-two"):
                self.assertEqual(dash.codex_agent_items(sid, {}, ("", 42, 2), {}, time.time()), [])
            processes.assert_not_called()

    def test_native_grandchildren_cycle_and_no_six_agent_cap(self):
        path = rollout(self.base / "busy.jsonl", {"type": "event_msg", "payload": {"type": "task_started"}})
        edges = {"lead": [("child", "open", str(path), "worker")],
                 "child": [(f"grand-{i}", "open", str(path), "worker") for i in range(8)],
                 "grand-0": [("lead", "open", str(path), "cycle")]}
        agents = dash.codex_agent_items("lead", edges, None, {}, time.time())
        self.assertEqual(len(agents), 9)
        self.assertEqual(next(a for a in agents if a["id"] == "grand-0")["parent_id"], "child")

    def test_registered_headless_child_is_hidden_from_root_cards(self):
        now = time.time()
        home = self.base / "home"
        artifact = self.base / "worker"
        artifact.mkdir()
        events = rollout(artifact / "events.jsonl", {"type": "thread.started", "thread_id": "headless"})
        events.write_text('{broken\n[]\n' + events.read_text())
        directory = home / "fsa-flow/runs/lead"
        directory.mkdir(parents=True)
        record = {"session_id": "lead", "run_id": "worker-run", "role": "implementer", "engine": "codex",
                  "model": None, "root": str(self.base / "different-checkout"), "state": "running", "started": now, "updated": now,
                  "artifact": str(artifact), "events_path": str(events), "summary": "", "verdict": None}
        (directory / "worker-run.json").write_text(json.dumps(record))
        paths = []
        for sid in ("lead", "headless", "unrelated"):
            path = rollout(self.base / (sid + ".jsonl"),
                           {"type": "session_meta", "payload": {"id": sid, "cwd": str(self.base)}})
            paths.append(path)
        repo = type("Repo", (), {"root": self.base})()
        def read(repo, path, meta, *args):
            return {"id": meta["id"]}
        with patch.object(dash, "CODEX_HOME", home), patch.object(dash, "codex_rollouts", return_value=paths), \
                patch.object(dash, "codex_live", return_value={}), patch.object(dash, "codex_children", return_value={}), \
                patch.object(dash, "read_codex_session", side_effect=read):
            sessions = dash.collect_codex_sessions(repo, [], now, {})
        self.assertEqual({s["id"] for s in sessions}, {"lead", "unrelated"})
        lead = next(s for s in sessions if s["id"] == "lead")
        self.assertEqual(lead["workflow_runs"][0]["child_session_id"], "headless")

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
