"""Interactive Codex sessions become dashboard sessions, read from Codex's own rollout transcripts."""
import json
import os
import subprocess
import sqlite3
import tempfile
import time
import types
import unittest
from unittest.mock import patch
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

    def test_fresh_ledger_overrides_stale_journal_and_cross_repository_binding(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.rollout("accuracy", self.root, [event("task_started", 30), message("user", "Fix dashboard", 29)])
        task = self.root / "TASKS.md"
        def ledger(status):
            return ("# Accuracy\n<!-- fsa:tasks:start -->\n| ID | Status | Task | Note |\n"
                    "| --- | --- | --- | --- |\n| T1 | " + status + " | Correct counts | Native evidence |\n<!-- fsa:tasks:end -->\n")
        task.write_text(ledger("in_progress"))
        journal = self.home / "fsa-flow" / "accuracy.json"
        journal.parent.mkdir(parents=True)
        journal.write_text(json.dumps({"session_id": "accuracy", "engine": "codex", "cwd": str(self.root),
            "phase": "implement", "updated": self.now, "history": [{"phase": "implement", "timestamp": self.now}],
            "task_tracking": {"file": str(task), "counts": {"in_progress": 1, "pending": 0}, "total": 1}}))
        with patch.dict(os.environ, {"FSA_TASKS_DIR": str(Path(self.scratch.name) / "registry")}):
            bind = dash.load_tasks.__globals__["bind_tasks"]
            bind("accuracy", self.root, task)
            repo = dash.Repo(str(self.root), str(Path(self.scratch.name) / "runs"), [])
            def tracked():
                state = dash.build_state(repo, dash.GitCache(repo))
                session = next(s for c in state["cards"] for s in c["sessions"] if s["id"] == "accuracy")
                self.assertEqual(self.collect()["accuracy"]["cwd"], str(self.root))
                return state, session["task_tracking"]
            self.assertEqual(tracked()[1]["counts"]["in_progress"], 1)
            task.write_text(ledger("pending"))
            counts = tracked()[1]["counts"]
            self.assertEqual((counts["pending"], counts["in_progress"]), (1, 0))
            plugin = self.root.parent / "plugin"
            plugin.mkdir()
            subprocess.run(["git", "init", "-q", str(plugin)], check=True)
            sibling = plugin / "PLUGIN-TASKS.md"
            sibling.write_text(ledger("done"))
            bind("accuracy", plugin, sibling)
            state, tasks = tracked()
            self.assertNotIn("error", tasks)
            self.assertEqual((tasks["file"], tasks["completed"]), (str(sibling), 1))
            self.assertIn(str(sibling), state["_docs"]["accuracy"])
            self.assertEqual(json.loads(journal.read_text())["cwd"], str(self.root))

    def test_registered_task_file_reaches_the_session_card_and_document_allowlist(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-q", "--allow-empty", "-m", "fixture"], check=True)
        self.rollout("tracked", self.root, [event("task_started", 30), message("user", "Implement canvas", 29)])
        task = self.root / "docs/tasks/canvas.md"
        task.parent.mkdir(parents=True)
        task.write_text("# Canvas\n<!-- fsa:tasks:start -->\n| ID | Status | Task | Note |\n| --- | --- | --- | --- |\n| T01 | running | Canvas | Browser pending |\n<!-- fsa:tasks:end -->\n")
        with patch.dict(os.environ, {"FSA_TASKS_DIR": str(Path(self.scratch.name) / "registry")}):
            dash.load_tasks.__globals__["bind_tasks"]("tracked", self.root, task)
            repo = dash.Repo(str(self.root), str(Path(self.scratch.name) / "runs"), [])
            state = dash.build_state(repo, dash.GitCache(repo))
            card = next(c for c in state["cards"] if any(s["id"] == "tracked" for s in c["sessions"]))
            tracked = next(s["task_tracking"] for s in card["sessions"] if s["id"] == "tracked")
            self.assertEqual(tracked["counts"]["in_progress"], 1)
            self.assertIn(str(task), state["_docs"]["tracked"])
            missing = self.collect()["tracked"]
            missing["cwd"] = ""
            with patch.object(dash, "collect_codex_sessions", return_value=[missing]):
                missing_state = dash.build_state(repo, dash.GitCache(repo))
            missing_card = next(c for c in missing_state["cards"] if any(s["id"] == "tracked" for s in c["sessions"]))
            self.assertIn("error", missing_card["sessions"][0]["task_tracking"])
            self.assertNotIn("completed", missing_card["sessions"][0]["task_tracking"])

            task.write_text(task.read_text().replace("| running |", "| done |"))
            state = dash.build_state(repo, dash.GitCache(repo))
            card = next(c for c in state["cards"] if any(s["id"] == "tracked" for s in c["sessions"]))
            self.assertEqual(card["sessions"][0]["task_tracking"]["completed"], 1)

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

    def ask(self, name, title, ago):
        return {"timestamp": stamp(ago), "type": "response_item", "payload": {"type": "function_call", "name": name, "call_id": "q1",
                "arguments": json.dumps({"questions": [{"title": title, "options": ["a", "b"]}]})}}

    def test_async_question_while_working_stays_working_and_shows_the_question(self):
        path = self.rollout("s-async", self.root, [event("task_started", 60), message("user", "revise the chatbot", 50),
                                                    self.ask("request_user_input_async", "Does <it> mean Infobip?", 40),
                                                    message("assistant", "Editing the tables", 5)])
        s = dash.read_codex_session(self.repo, path, dash.codex_meta(path), self.now, {}, {}, "w2:p1", "blocked")
        self.assertEqual((s["state"], s["question"], s["need"]), ("working", "Does <it> mean Infobip?", ""))

    def test_async_question_after_codex_goes_quiet_is_waiting_with_the_question(self):
        path = self.rollout("s-quiet", self.root, [event("task_started", 400), message("user", "revise", 390),
                                                    self.ask("request_user_input_async", "Which flow?", 380)])
        s = dash.read_codex_session(self.repo, path, dash.codex_meta(path), self.now, {}, {}, "w2:p1", "blocked")
        self.assertEqual((s["state"], s["need"], s["question"]), ("waiting", "Which flow?", ""))

    def test_blocking_question_is_waiting_at_once(self):
        path = self.rollout("s-sync", self.root, [event("task_started", 30), message("user", "revise", 25),
                                                   self.ask("request_user_input", "Approve the plan?", 10)])
        s = dash.read_codex_session(self.repo, path, dash.codex_meta(path), self.now, {}, {}, "w2:p1", "blocked")
        self.assertEqual((s["state"], s["need"]), ("waiting", "Approve the plan?"))

    def test_question_far_back_in_a_long_log_is_still_found(self):
        filler = [message("assistant", "x" * 4000, 50 - i * 0.01) for i in range(400)]
        path = self.rollout("s-long", self.root, [event("task_started", 200), message("user", "revise", 190),
                                                   self.ask("request_user_input_async", "Which flow?", 180), *filler])
        self.assertEqual(dash.codex_pending_question(path), ("Which flow?", True))
        with path.open("a") as fh:
            fh.write(json.dumps(message("user", "the first", 1)) + "\n")
        self.assertEqual(dash.codex_pending_question(path), ("", False))

    def test_subagent_task_name_comes_from_its_delegation_message(self):
        inherited = [message("user", "parent history", 300 - i) for i in range(5)]
        task = {"timestamp": stamp(100), "type": "response_item", "payload": {"type": "agent_message", "author": "/root",
                "recipient": "/root/chatbot_readiness", "content": [{"type": "input_text", "text": "Message Type: NEW_TASK"},
                                                                   {"type": "encrypted_content", "encrypted_content": "x"}]}}
        path = self.rollout("s-child", self.root, [*inherited, task])
        self.assertEqual(dash.codex_task_name(str(path)), "chatbot readiness")

    def test_answered_question_is_not_pending(self):
        path = self.rollout("s-answered", self.root, [event("task_started", 60), self.ask("request_user_input_async", "Which?", 40),
                                                       message("user", "the first one", 30), message("assistant", "ok", 5)])
        s = dash.read_codex_session(self.repo, path, dash.codex_meta(path), self.now, {}, {}, "w2:p1", "working")
        self.assertEqual((s["state"], s["question"]), ("working", ""))

    def test_worktree_follows_the_paths_codex_edits(self):
        other = self.root.parent / "repo-dev"
        patch_call = {"timestamp": stamp(10), "type": "response_item", "payload": {"type": "custom_tool_call", "name": "apply_patch", "call_id": "p1",
                      "input": f"*** Update File: {other}/src/a.tsx\n*** Update File: {other}/src/b.tsx"}}
        path = self.rollout("s-wt", self.root, [event("task_started", 20), message("user", "edit", 19), patch_call])
        wt_re = dash.worktree_re(self.repo, {str(self.root), str(other)})
        s = dash.read_codex_session(self.repo, path, dash.codex_meta(path), self.now, {}, {}, None, None, (), wt_re)
        self.assertEqual(s["worktree"], str(other))

    def test_session_in_another_repo_is_not_collected(self):
        self.rollout("s-other", self.root.parent / "elsewhere", [event("task_complete", 10)])
        self.assertNotIn("s-other", self.collect())

    def journal(self, sid, phase="plan", **overrides):
        record = {"session_id": sid, "engine": "codex", "cwd": str(self.root),
                  "phase": phase, "updated": self.now,
                  "history": [{"phase": "investigate", "timestamp": self.now - 10},
                              {"phase": phase, "timestamp": self.now}]}
        record.update(overrides)
        path = self.home / "fsa-flow" / f"{sid}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record))
        return path

    def test_journal_and_turn_model_are_exposed(self):
        self.rollout("s-flow", self.root, [
            {"timestamp": stamp(20), "type": "turn_context",
             "payload": {"cwd": str(self.root), "model": "configured-codex-model"}},
            event("task_complete", 10),
        ])
        self.journal("s-flow", checks=["diff clean"], summary="Finished", auditor="sonnet")
        session = self.collect()["s-flow"]
        self.assertEqual(session["model"], "configured-codex-model")
        self.assertEqual(session["workflow_checks"], ["diff clean"])
        self.assertEqual(session["workflow_summary"], "Finished")
        self.assertEqual(session["workflow_auditor"], "sonnet")
        self.assertEqual(session["workflow_phase"], "plan")
        self.assertEqual(session["workflow_at"], self.now)
        self.assertEqual([e["phase"] for e in session["workflow_history"]], ["investigate", "plan"])

    def test_model_database_fallback_is_exact_and_transcript_has_priority(self):
        self.home.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.home / "state_5.sqlite") as con:
            con.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, model)")
            con.executemany("INSERT INTO threads VALUES (?, ?)",
                            [("s-model", "current-model"), ("other", "wrong-model"),
                             ("invalid", 42), ("blank", " "), ("control", "bad\nmodel")])
        # The old turn context is beyond both transcript windows.
        self.rollout("s-model", self.root, [
            {"timestamp": stamp(30), "type": "turn_context", "payload": {"model": "old-model"}},
            message("assistant", "x" * 1100000, 20), event("task_complete", 10)])
        self.assertEqual(self.collect()["s-model"]["model"], "current-model")
        self.rollout("s-model", self.root, [
            {"timestamp": stamp(20), "type": "turn_context", "payload": {"model": "transcript-model"}},
            event("task_complete", 10)])
        self.assertEqual(self.collect()["s-model"]["model"], "transcript-model")
        for sid in ("missing", "invalid", "blank", "control"):
            self.assertEqual(dash.codex_thread_model(sid), "")
        with sqlite3.connect(self.home / "state_6.sqlite") as con:
            con.execute("CREATE TABLE threads (id TEXT)")
        self.assertEqual(dash.codex_thread_model("s-model"), "")
        (self.home / "state_6.sqlite").write_text("not sqlite")
        self.assertEqual(dash.codex_thread_model("s-model"), "")
        for db in self.home.glob("state_*.sqlite"):
            db.unlink()
        self.assertEqual(dash.codex_thread_model("s-model"), "")

    def test_invalid_journals_are_rejected(self):
        for fields in ({"checks": [True]}, {"summary": {}}, {"auditor": []}, {"session_id": "other"}, {"cwd": str(self.root.parent)},
                       {"engine": "claude"}, {"phase": "unknown"},
                       {"phase": []}, {"updated": float("nan")},
                       {"updated": self.now + 3600}, {"updated": True},
                       {"history": []}, {"history": [{"phase": "plan", "timestamp": -1}]}):
            with self.subTest(fields=fields):
                self.journal("s-flow", **fields)
                self.assertEqual(dash.codex_workflow("s-flow", str(self.root), self.now), {})
        path = self.journal("s-flow")
        path.write_text("invalid json")
        self.assertEqual(dash.codex_workflow("s-flow", str(self.root), self.now), {})
        self.assertEqual(dash.codex_workflow("../s-flow", str(self.root), self.now), {})

    def test_explicit_phases_override_legacy_and_edits(self):
        card = {"tree": {"edited": self.now + 10},
                "declared": {"phase": "review", "at": self.now + 5}}
        session = {"id": "s-flow", "engine": "codex", "state": "working",
                   "workflow_at": self.now, "briefs": []}
        for phase in ("investigate", "plan", "implement", "validate", "audit", "complete"):
            with self.subTest(phase=phase):
                session["workflow_phase"] = phase
                result = dash.phase_of(card, [], [session])
                self.assertEqual(result, "audit" if phase == "validate" else phase)

    def dashboard_state(self, session, board, runs=(), only=None):
        self.repo.board = self.root / "board.json"
        self.repo.board.write_text(json.dumps(board))
        self.repo.favourites = self.root / "dashboard-favourites.json"
        self.repo.main = "main"
        self.repo.projects = []
        gc = types.SimpleNamespace(worktrees=lambda now: {session["worktree"] or str(self.root): {},
                                                         **{r["root"]: {} for r in runs}},
                                   detail=lambda key: {"branch": "main", "head": "a" * 40,
                                                       "dirty": 0, "ahead": 0, "merged": True,
                                                       "edited": 0})
        with patch.object(dash, "collect_runs", return_value=list(runs)), \
                patch.object(dash, "collect_sessions", return_value=[]), \
                patch.object(dash, "fresh_sessions", return_value=[]), \
                patch.object(dash, "collect_codex_sessions", return_value=[session]), \
                patch.object(dash, "judge_turns"), patch.object(dash, "own_count", return_value=0), \
                patch.object(dash, "newest_brief", return_value=None):
            return dash.build_state(self.repo, gc, only=only)

    def test_herdr_lead_has_one_card_even_with_runs_from_two_checkouts(self):
        self.rollout("s-flow", self.root, [event("task_started", 20)])
        session = self.collect()["s-flow"]
        runs = [{"id": f"run-{n}", "session": "s-flow", "mode": "investigate", "state": "done",
                 "root": str(self.root / f"checkout-{n}"), "unit": f"unit-{n}", "flags": [], "started": self.now - 10,
                 "updated": self.now - 5, "goal": "", "desc": ""} for n in range(2)]
        state = self.dashboard_state(session, {}, runs=runs, only={"s-flow"})
        self.assertEqual(len(state["cards"]), 1)
        self.assertEqual(state["cards"][0]["key"], "session:s-flow")
        self.assertEqual(len(state["cards"][0]["runs"]), 2)
        self.assertEqual(state["cards"][0]["worktree"], str(self.root / "checkout-1"))

    def test_claude_declared_complete_shows_done_until_a_new_working_turn(self):
        card = {"declared": {"phase": "complete", "at": self.now}}
        session = {"id": "s-claude", "engine": "claude", "state": "idle", "turn_at": self.now - 60, "briefs": []}
        self.assertIn("complete", dash.PHASES)
        self.assertEqual(dash.phase_of(card, [], [session]), "complete")
        session.update(state="working", turn_at=self.now - 30)
        self.assertEqual(dash.phase_of(card, [], [session]), "complete")
        session["turn_at"] = self.now + 30
        self.assertEqual(dash.phase_of(card, [], [session]), "investigate")

    def test_git_and_deployment_metadata_cannot_override_working_phase(self):
        self.rollout("s-flow", self.root, [event("task_started", 20)])
        self.journal("s-flow", "implement")
        session = self.collect()["s-flow"]
        session["worktree"] = str(self.root / "worktree")
        board = {"locks": {"deploy": {"session": "s-flow"}},
                 "events": [{"text": "DEPLOYED " + "a" * 40}]}
        state = self.dashboard_state(session, board)
        self.assertEqual(state["cards"][0]["phase"], "implement")
        self.assertEqual(state["cards"][0]["sessions"][0]["state"], "working")
        self.assertEqual(state["locks"], board["locks"])
        session.pop("workflow_phase")
        self.assertEqual(self.dashboard_state(session, board)["cards"][0]["phase"], "investigate")

    def test_historical_dismissals_cannot_hide_sessions_or_attention(self):
        self.rollout("s-flow", self.root, [event("task_complete", 10)])
        self.journal("s-flow", "plan")
        session = self.collect()["s-flow"]
        session.update(state="still_open", pane="w2:p1")
        historical = self.root / "dashboard-dismissed.json"
        historical.write_text(json.dumps({"session:s-flow": self.now + 3600}))
        self.repo.dismissed = historical
        original = historical.read_bytes()
        for status in ("still_open", "waiting"):
            with self.subTest(status=status):
                session["state"] = status
                state = self.dashboard_state(session, {})
                self.assertEqual([c["key"] for c in state["cards"]], ["session:s-flow"])
                self.assertEqual([s["id"] for s in state[status]], ["s-flow"])
                self.assertEqual(state["session_panes"]["s-flow"], "w2:p1")
        self.assertEqual(historical.read_bytes(), original)

    def test_dismiss_endpoint_is_rejected_before_body_or_state_access(self):
        handler = object.__new__(dash.Handler)
        handler.path = "/api/dismiss"
        handler.authorised = lambda body: True
        with patch.object(handler, "send") as send:
            handler.do_POST()
        send.assert_called_once_with(403, b"forbidden", "text/plain")
        self.assertFalse(handler.body_read)

    def test_codex_never_calls_classifier(self):
        session = {"id": "s-flow", "engine": "codex", "state": "working"}
        with patch.object(dash, "run_mode") as mode, patch.object(dash, "run_classifier") as classifier, \
                patch.object(dash.threading, "Thread") as thread:
            dash.judge_turns(self.repo, [session], self.now)
            dash.judge_codex(session, self.now)
            mode.assert_not_called()
            classifier.assert_not_called()
            thread.assert_not_called()


if __name__ == "__main__":
    unittest.main()
