"""Claude background shells appear as session agents, read from the transcript and its tasks directory."""
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("fsa_dashboard_shells", str(REPO / "plugins/fullstack-agents/scripts/fsa-dashboard"))
dash = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_dashboard_shells", _loader))
_loader.exec_module(dash)


def launch(uid, task, description):
    use = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": uid, "name": "Bash",
           "input": {"command": "sleep 1", "description": description, "run_in_background": True}}]}}
    result = {"type": "user", "toolUseResult": {"backgroundTaskId": task},
              "message": {"content": [{"type": "tool_result", "tool_use_id": uid, "content": ""}]}}
    return [use, result]


class BackgroundShellTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.transcript = root / "projects" / "-repo" / "sess-1.jsonl"
        self.transcript.parent.mkdir(parents=True)
        self.tasks = root / f"claude-{os.getuid()}" / "-repo" / "sess-1" / "tasks"
        self.tasks.mkdir(parents=True)
        self.env = patch.dict(os.environ, {"CLAUDE_CODE_TMPDIR": str(root)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def items(self, records, ended=None):
        bg = {"labels": {}, "tasks": {}, "exit": {}, "bash": {}, "pending": []}
        for d in records:
            dash.note_background(d, d.get("message") or {}, bg)
        return dash.shell_items(self.transcript, bg, ended or {}, time.time())

    def test_launched_shell_is_running_with_its_description(self):
        (self.tasks / "bx1.output").write_text("\x1b[90mcompiling\x1b[0m\n")
        items = self.items(launch("toolu_1", "bx1", "Dispatch P1 with Grok"))
        self.assertEqual([("bx1", "shell · Dispatch P1 with Grok", "running")], [(x["id"], x["label"], x["state"]) for x in items])
        self.assertEqual("compiling", dash.shell_output(items[0]["path"]))
        facts = items[0]["shell"]
        self.assertEqual(("Dispatch P1 with Grok", "sleep 1", None), (facts["description"], facts["command"], facts["exit"]))

    def test_facts_link_target_brief_run_and_exit_code(self):
        (self.tasks / "bx4.output").write_text("allowed_paths=/h/.codex/kc-runs/implement-20261014-125741-77.allow\n")
        records = launch("toolu_4", "bx4", "Dispatch P4")
        records[0]["message"]["content"][0]["input"]["command"] = "cd /wt/p4 && codex-task.sh implement .codex-briefs/p4-api.md"
        bg = {"labels": {}, "tasks": {}, "exit": {"bx4": 2}, "bash": {}, "pending": []}
        for d in records:
            dash.note_background(d, d["message"], bg)
        facts = dash.shell_items(self.transcript, bg, {"bx4": "failed"}, time.time(), cwd="/repo")[0]["shell"]
        self.assertEqual(("/wt/p4", "p4-api", "implement-20261014-125741-77", 2),
                         (facts["cwd"], facts["brief"], facts["run"], facts["exit"]))

    def test_notification_status_wins_and_unlabelled_shell_falls_back_to_id(self):
        (self.tasks / "bx2.output").write_text("done\n")
        items = self.items([], {"bx2": "completed"})
        self.assertEqual([("shell · bx2", "completed")], [(x["label"], x["state"]) for x in items])

    def test_an_undescribed_shell_is_named_by_what_its_command_does(self):
        wait = {"command": "S=/tmp/x; while kill -0 1011912 2>/dev/null; do sleep 30; done; grep -E Summary $S/a.log"}
        self.assertEqual(dash.shell_label(wait, "b8x"), "waits for process 1011912, then grep -E Summary $S/a.log")
        self.assertEqual(dash.shell_label({"command": "cd /repo && cargo test -p api"}, "b8x"), "cargo test -p api")
        self.assertEqual(dash.shell_label({"description": "Run checks", "command": "make"}, "b8x"), "Run checks")
        self.assertEqual(dash.shell_label({}, "b8x"), "b8x")

    def test_unannounced_output_shows_only_while_its_bash_call_runs(self):
        (self.tasks / "bx5.output").write_text("committing\n")
        use = launch("toolu_5", "bx5", "Commit")[0]
        use["message"]["content"][0]["input"].pop("run_in_background")
        bg = {"labels": {}, "tasks": {}, "exit": {}, "bash": {}, "pending": []}
        dash.note_background(use, use["message"], bg)
        bg["pending"] = list(bg["bash"].values())
        items = dash.shell_items(self.transcript, bg, {}, time.time())
        self.assertEqual([("shell · Commit", "running", True)], [(x["label"], x["state"], x["shell"]["moved"]) for x in items])
        bg["pending"] = []
        self.assertEqual([], dash.shell_items(self.transcript, bg, {}, time.time()))

    def test_stale_unannounced_output_is_hidden(self):
        out = self.tasks / "bx3.output"
        out.write_text("old\n")
        old = time.time() - dash.ACTIVITY_KEEP_S - 60
        os.utime(out, (old, old))
        self.assertEqual([], self.items([]))
        self.assertEqual(["running"], [x["state"] for x in self.items(launch("toolu_3", "bx3", "Long build"))])

    def write_transcript(self, records):
        compact = {"separators": (",", ":")}  # Claude Code writes transcripts without spaces
        filler = json.dumps({"type": "api-request-blob", "blob": "x" * 4096}, **compact)
        lines = [json.dumps(d, **compact) for d in records] + [filler] * (dash.TAIL_BYTES // 4096 + 8)
        with self.transcript.open("a") as f:
            f.write("\n".join(lines) + "\n")

    def session_shells(self):
        bg = {"labels": {}, "tasks": {}, "exit": {}, "bash": {}, "pending": []}
        for line in dash.tail_lines(self.transcript):
            d = json.loads(line)
            dash.note_background(d, d.get("message") or {}, bg)
        merged, ended = dash.with_shell_history(self.transcript, bg, {})
        return [(x["label"], x["state"]) for x in dash.shell_items(self.transcript, merged, ended, time.time())]

    def test_shell_launched_before_the_tail_stays_listed_until_it_ends(self):
        (self.tasks / "bx6.output").write_text("checking\n")
        self.write_transcript(launch("toolu_6", "bx6", "Run checks"))
        self.assertEqual([("shell · Run checks", "running")], self.session_shells())
        note = {"type": "user", "message": {"content": "<task-notification><task-id>bx6</task-id>"
                "<status>completed</status><summary>done (exit code 0)</summary></task-notification>"}}
        self.write_transcript([note])
        self.assertEqual([("shell · Run checks", "completed")], self.session_shells())


if __name__ == "__main__":
    unittest.main()
