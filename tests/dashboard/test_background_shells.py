"""Claude background shells appear as session agents, read from the transcript and its tasks directory."""
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


if __name__ == "__main__":
    unittest.main()
