"""Brief -> completion-evidence spec parsing and merge (docs/TASK_LIFECYCLE_DESIGN.md §14.6 item 8)."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "plugins/fullstack-agents/scripts/lib"
sys.path.insert(0, str(LIB))
SPEC = importlib.util.spec_from_file_location("task_tracking_brief", LIB / "task_tracking.py")
tasks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tasks)
import task_brief
import task_evidence

SKILL_GUIDE_EXAMPLE = """ALLOWED_PATHS:
src/backend/crates/x/

ACCEPTANCE:
1. Journey B restarts the bot — check: scripts/test-backend.sh -p x --test journeys expect: test result: ok\\. [1-9]
2. Restart notice text matches the design — review: diff of chatbot_restart.rs against §8.3
3. Builder shows the restart toggle — inspection: screenshot of /chatbot/builder after next build
KIND: code
DEPENDS:
src/backend/crates/shared/
src/backend/Cargo.lock
INPUTS: src/backend/.env.example
ENV: SQLX_OFFLINE
SCOPE_WHY: x and the shared crate it calls; the journeys read the helpers and env example
AFFECTED_TESTS:
src/backend/crates/x/tests/journeys.rs
"""


def git(args, cwd):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


class ParseBriefTests(unittest.TestCase):
    def test_skill_guide_example_parses_to_the_expected_spec(self):
        spec = task_brief.parse_brief(SKILL_GUIDE_EXAMPLE)
        self.assertEqual(spec["kind"], "code")
        self.assertEqual(sorted(spec["scope"]["paths"]),
                          sorted(["src/backend/crates/x/", "src/backend/crates/x/tests/journeys.rs"]))
        self.assertEqual(spec["scope"]["dependencies"], ["src/backend/crates/shared/", "src/backend/Cargo.lock"])
        self.assertEqual(spec["scope"]["inputs"], ["src/backend/.env.example"])
        self.assertEqual(spec["scope"]["env"], ["SQLX_OFFLINE"])
        self.assertEqual(spec["scope"]["rationale"],
                          "x and the shared crate it calls; the journeys read the helpers and env example")
        self.assertEqual(spec["criteria"], [
            {"id": "1", "text": "Journey B restarts the bot", "checks": ["C1"]},
            {"id": "2", "text": "Restart notice text matches the design", "checks": ["R1"]},
            {"id": "3", "text": "Builder shows the restart toggle", "checks": ["R2"]},
        ])
        self.assertEqual(spec["checks"], {
            "C1": {"method": "command", "command": "scripts/test-backend.sh -p x --test journeys",
                   "expect": {"patterns": ["test result: ok\\. [1-9]"]}},
            "R1": {"method": "review"},
            "R2": {"method": "inspection"},
        })

    def test_untagged_item_is_refused_naming_it(self):
        text = "ACCEPTANCE:\n1. Some outcome with no verification tag\nKIND: code\nSCOPE_WHY: x\n"
        with self.assertRaises(ValueError) as ctx:
            task_brief.parse_brief(text)
        self.assertIn("item 1", str(ctx.exception))

    def test_command_without_expect_is_refused(self):
        text = "ACCEPTANCE:\n1. Script runs — check: true\nKIND: code\nSCOPE_WHY: x\n"
        with self.assertRaises(ValueError) as ctx:
            task_brief.parse_brief(text)
        self.assertIn("needs expect", str(ctx.exception))

    def test_review_inspection_document_analysis_tags_map_to_methods(self):
        text = ("ACCEPTANCE:\n"
                "1. Doc updated — document: docs/x.md\n"
                "2. Reviewed — review: manual comparison\n"
                "3. Inspected — inspection: screenshot\n"
                "4. Analysed — analysis: docs/report.md\n"
                "KIND: docs\nSCOPE_WHY: x\n")
        spec = task_brief.parse_brief(text)
        self.assertEqual([spec["checks"][f"R{n}"]["method"] for n in range(1, 5)],
                          ["document", "review", "inspection", "analysis"])

    def test_build_tag_becomes_a_command_check_with_default_expect(self):
        text = "ACCEPTANCE:\n1. Script runs — check: true expect: none (silent)\nKIND: code\nSCOPE_WHY: x\nBUILD: make test\n"
        spec = task_brief.parse_brief(text)
        self.assertEqual(spec["checks"]["BUILD"],
                          {"method": "command", "command": "make test",
                           "expect": {"none": "compile/lint success is silent"}})
        self.assertIn({"id": "BUILD", "text": "BUILD passes", "checks": ["BUILD"]}, spec["criteria"])

    def test_merge_from_a_repair_brief_with_fewer_allowed_paths_keeps_the_union_scope(self):
        first = task_brief.parse_brief(
            "ALLOWED_PATHS:\nsrc/a.py\nsrc/b.py\n"
            "ACCEPTANCE:\n1. First behaviour — check: true expect: none (silent)\n"
            "KIND: code\nDEPENDS: none (self-contained)\nSCOPE_WHY: initial reason\n")
        repair = task_brief.parse_brief(
            "ALLOWED_PATHS:\nsrc/a.py\n"
            "ACCEPTANCE:\n1. First behaviour repaired — check: true expect: none (silent)\n"
            "KIND: code\nDEPENDS: none (self-contained)\nSCOPE_WHY: repair reason\n")
        merged = task_brief.merge_spec(first, repair)
        self.assertEqual(set(merged["scope"]["paths"]), {"src/a.py", "src/b.py"})
        self.assertEqual(len(merged["criteria"]), 1)
        self.assertEqual(merged["criteria"][0]["text"], "First behaviour repaired")


class AcceptFromBriefTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-brief-")
        self.root = Path(self.scratch.name) / "repo"
        self.root.mkdir()
        git(["init", "-q"], self.root)
        git(["config", "user.email", "a@example.com"], self.root)
        git(["config", "user.name", "Test"], self.root)
        (self.root / "src").mkdir()
        (self.root / "src/app.py").write_text("print('hi')\n")
        (self.root / "docs").mkdir()
        (self.root / "docs/example.md").write_text("doc content\n")
        git(["add", "-A"], self.root)
        git(["commit", "-q", "-m", "initial"], self.root)
        self.state = Path(self.scratch.name) / "state"
        self.env = patch.dict(os.environ, {"FSA_TASKS_DIR": str(self.state), "CODEX_THREAD_ID": "brief-session"})
        self.env.start()
        self.path = self.root / "TASKS.md"
        self.call("init", "--task", "D1|pending|Deliverable|")

    def tearDown(self):
        self.env.stop()
        self.scratch.cleanup()

    def call(self, command, *args, fails=False):
        argv = [command, "--root", str(self.root), "--file", "TASKS.md", "--session", "brief-session", *args]
        if fails:
            error = io.StringIO()
            with contextlib.redirect_stderr(error), self.assertRaises(SystemExit):
                tasks.main(argv)
            return error.getvalue()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tasks.main(argv), 0)
        text = output.getvalue()
        return json.loads(text) if text.strip() else None

    def write_brief(self, name, text):
        path = Path(self.scratch.name) / name
        path.write_text(text)
        return str(path)

    def accept_from_brief(self, deliverable_id, text, name="brief.md", reason=None, fails=False):
        args = ["--id", deliverable_id, "--from-brief", self.write_brief(name, text)]
        if reason:
            args += ["--reason", reason]
        return self.call("accept", *args, fails=fails)

    CODE_BRIEF = ("ALLOWED_PATHS:\nsrc/app.py\n"
                  "ACCEPTANCE:\n1. The script runs — check: {command} expect: none (silent)\n"
                  "KIND: code\nDEPENDS: none (self-contained script)\nSCOPE_WHY: trivial\n")

    def test_depends_none_with_reason_is_accepted_for_code(self):
        self.accept_from_brief("D1", self.CODE_BRIEF.format(command="true"))
        block = task_evidence.load_block(self.path.read_text())
        self.assertEqual(block["deliverables"]["D1"]["scope"]["dependencies_none"], "self-contained script")

    def test_missing_depends_is_refused_for_code(self):
        text = ("ALLOWED_PATHS:\nsrc/app.py\n"
                "ACCEPTANCE:\n1. The script runs — check: true expect: none (silent)\n"
                "KIND: code\nSCOPE_WHY: trivial\n")
        self.assertIn("scope.dependencies", self.accept_from_brief("D1", text, fails=True))

    def test_replacing_a_check_with_results_requires_reason(self):
        self.accept_from_brief("D1", self.CODE_BRIEF.format(command="true"))
        run = self.call("check", "run", "--id", "D1", "--check", "C1")
        self.assertEqual(run["result"], "pass")
        changed = self.CODE_BRIEF.format(command="false")
        self.assertIn("requires --reason", self.accept_from_brief("D1", changed, fails=True))
        self.accept_from_brief("D1", changed, reason="swap command")
        block = task_evidence.load_block(self.path.read_text())
        self.assertEqual(block["deliverables"]["D1"]["checks"]["C1"]["command"], "false")

    def test_accept_from_brief_check_finish_and_set_done_end_to_end(self):
        text = ("ALLOWED_PATHS:\ndocs/example.md\n"
                "ACCEPTANCE:\n"
                "1. Content is correct — document: docs/example.md\n"
                "2. Content matches design — review: manual comparison against the design note\n"
                "KIND: docs\nSCOPE_WHY: trivial doc edit\n")
        self.accept_from_brief("D1", text)
        document_run = self.call("check", "start", "--id", "D1", "--check", "R1")
        self.call("check", "finish", "--id", "D1", "--check", "R1", "--run", document_run["run"],
                  "--result", "pass", "--evidence", str(self.root / "docs/example.md"))
        note = Path(self.scratch.name) / "review-note.txt"
        note.write_text("matches the design note\n")
        review_run = self.call("check", "start", "--id", "D1", "--check", "R2")
        self.call("check", "finish", "--id", "D1", "--check", "R2", "--run", review_run["run"],
                  "--result", "pass", "--evidence", str(note))
        self.call("set", "--id", "D1", "--status", "done")
        self.assertEqual(tasks.load_tasks("brief-session", self.root)["items"][0]["status"], "done")


if __name__ == "__main__":
    unittest.main()
