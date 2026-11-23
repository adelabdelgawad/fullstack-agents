"""The session panel's History tab: one row per prompt of one session, with tokens, cost, fill and outcome."""
import importlib.util
import json
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("fsa_dashboard_turns", str(REPO / "plugins/fullstack-agents/scripts/fsa-dashboard"))
dash = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_dashboard_turns", _loader))
_loader.exec_module(dash)

MODEL = "claude-opus-5-5"


def user(content, ts="2026-11-21T10:00:00Z", **extra):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": content}, **extra}


def assistant(mid, blocks, stop, ts="2026-11-21T10:00:05Z", inp=1000, out=100):
    return {"type": "assistant", "timestamp": ts, "message": {
        "id": mid, "model": MODEL, "role": "assistant", "content": blocks, "stop_reason": stop,
        "usage": {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}}


def text(t):
    return {"type": "text", "text": t}


def tool(name):
    return {"type": "tool_use", "id": "t1", "name": name, "input": {}}


class SessionTurnsTests(unittest.TestCase):
    def read(self, rows):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as handle:
            handle.write("\n".join(json.dumps(row) for row in rows) + "\n")
        try:
            return dash.session_turns(handle.name)
        finally:
            Path(handle.name).unlink()

    def test_rows_per_prompt_with_outcomes_and_deduped_usage(self):
        result = self.read([
            user("Fix the login page"),
            assistant("m1", [tool("Read")], "tool_use"),
            assistant("m1", [tool("Read")], "tool_use"),  # same message id streamed twice: counted once
            user([{"type": "tool_result", "tool_use_id": "t1", "content": "x"}]),
            assistant("m2", [text("Fixed.")], "end_turn", ts="2026-11-21T10:01:00Z"),
            user("Base directory for this skill: /x", isMeta=True),
            user("Which colour?", ts="2026-11-21T10:02:00Z"),
            assistant("m3", [tool("AskUserQuestion")], "tool_use"),
            user("Long refactor", ts="2026-11-21T10:03:00Z"),
            assistant("m4", [tool("Bash")], "tool_use"),
            user("[Request interrupted by user]"),
            {"type": "system", "subtype": "compact_boundary", "compactMetadata": {"preTokens": 900000, "postTokens": 40000}},
            user("Still there?", ts="2026-11-21T10:04:00Z"),
            assistant("m5", [tool("Bash")], "tool_use", inp=2000),
        ])
        turns = result["turns"]
        self.assertEqual([t["prompt"] for t in turns], ["Fix the login page", "Which colour?", "Long refactor", "Still there?"])
        self.assertEqual([t["state"] for t in turns], ["answered", "asked", "interrupted", "working"])
        self.assertEqual(turns[0]["tokens"], 2200)
        self.assertEqual(turns[0]["model"], MODEL)
        self.assertAlmostEqual(turns[0]["cost"], (2000 * 4 + 200 * 20) / 1e6)
        self.assertEqual(turns[0]["updated"] - turns[0]["started"], 60)
        self.assertEqual(turns[2]["compactions"], 1)
        self.assertEqual(turns[3]["compactions"], 0)
        self.assertEqual(turns[3]["fill"], 0.002)
        totals = result["totals"]
        self.assertEqual((totals["turns"], totals["tokens"], totals["compactions"], totals["interrupted"]), (4, 6500, 1, 1))

    def test_question_in_final_text_counts_as_asked(self):
        turns = self.read([user("Deploy?"), assistant("m1", [text("Shall I deploy now?")], "end_turn")])["turns"]
        self.assertEqual(turns[0]["state"], "asked")

    def test_codex_prompts_and_token_deltas(self):
        def item(payload, kind="response_item"):
            return {"type": kind, "timestamp": "2026-11-21T10:00:00Z", "payload": payload}

        def tokens(total):
            return item({"type": "token_count", "info": {"total_token_usage": {"input_tokens": total, "output_tokens": 0},
                                                         "last_token_usage": {"input_tokens": total}, "model_context_window": 100000}}, "event_msg")
        turns = self.read([
            item({"model": "gpt-5"}, "turn_context"),
            item({"type": "message", "role": "user", "content": [{"type": "input_text", "text": "<env>ctx</env>"}]}),
            item({"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Add search"}]}),
            tokens(500), item({"type": "task_complete"}, "event_msg"),
            item({"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Now tests"}]}),
            tokens(1500),
        ])["turns"]
        self.assertEqual([(t["prompt"], t["state"], t["tokens"]) for t in turns],
                         [("Add search", "answered", 500), ("Now tests", "working", 1000)])
        self.assertEqual(turns[1]["fill"], 0.015)

    def test_missing_file_is_empty(self):
        self.assertEqual(dash.session_turns("/nonexistent/x.jsonl"), {"turns": [], "totals": {}})


class HistoryLineageTests(unittest.TestCase):
    def test_handoff_prompt_names_the_session_it_continues(self):
        old = "f0b9c55b-2e6f-465f-b94c-2afdd0994746"
        plan = f"Implement the following plan:\n\n# HANDOFF RESUME\n\nFirst: `fsa-task adopt --root /r --file t.md --from {old}`"
        with tempfile.TemporaryDirectory() as tmp:
            handoff, plain = Path(tmp, "a.jsonl"), Path(tmp, "b.jsonl")
            handoff.write_text("\n".join(json.dumps(r) for r in (user(plan), user("next"))) + "\n")
            plain.write_text("\n".join(json.dumps(r) for r in (user(f"look at --from {old}"), user("x"))) + "\n")
            self.assertEqual(dash.handoff_from(handoff), old)
            self.assertTrue(dash.first_prompt(handoff).startswith("Implement the following plan"))
            self.assertEqual(dash.handoff_from(plain), "")

    def test_history_lists_each_session_then_its_subagents_newest_first(self):
        usage = {"model": MODEL, "tokens": 10, "agent_tokens": 5, "agents": {
            "a1": {"model": "claude-sonnet-5-5", "tokens": 2, "cost": 0.1, "fill": 0.1, "compactions": 0,
                   "label": "test-runner · Run suite", "updated": 50},
            "a2": {"model": "claude-haiku-4-5", "tokens": 3, "cost": None, "fill": 0, "compactions": 0,
                   "label": "", "updated": 90}}}
        rows = dash.history_rows([{"id": "lead", "name": "lead", "state": "idle", "updated": 100, "branch": "main",
                                   "usage": usage, "previous": "older"}])
        self.assertEqual([(r["id"], r.get("parent")) for r in rows], [("lead", None), ("a2", "lead"), ("a1", "lead")])
        self.assertEqual(rows[0]["previous"], "older")
        self.assertEqual(rows[0]["tokens"], 15)
        self.assertEqual(rows[1]["name"], "subagent a2")
        self.assertEqual(rows[2]["name"], "test-runner · Run suite")


if __name__ == "__main__":
    unittest.main()
