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


if __name__ == "__main__":
    unittest.main()
