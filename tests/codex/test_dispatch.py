"""codex-task.sh dispatch contract with fake engines: registry location, records and arguments."""
import json
import unittest
from pathlib import Path

from dispatch_support import DispatchCase


class RegistryLocationTests(unittest.TestCase):
    def setUp(self):
        self.case = DispatchCase("codex")

    def tearDown(self):
        self.case.cleanup()

    def run_dir_of(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(self.case.manifest(result)["log"]).parent

    def test_default_without_binding_or_env(self):
        self.assertEqual(self.run_dir_of(self.case.dispatch()), self.case.home / ".codex/fsa-runs")

    def test_project_binding_selects_the_registry(self):
        self.case.binding(runs_dir="~/.codex/kc-runs")
        self.assertEqual(self.run_dir_of(self.case.dispatch()), self.case.home / ".codex/kc-runs")

    def test_env_wins_over_the_binding(self):
        self.case.binding(runs_dir="~/.codex/kc-runs")
        chosen = self.case.base / "explicit"
        result = self.case.dispatch(env={"FSA_CODEX_RUNS_DIR": str(chosen)})
        self.assertEqual(self.run_dir_of(result), chosen)


class RegistryRecordTests(unittest.TestCase):
    """Run record v2: plugin identity, requested settings, engine session ids and instruction hashes."""

    def dispatch(self, engine, **env):
        if getattr(self, "case", None) is None:
            self.case = DispatchCase(engine)
            self.addCleanup(self.case.cleanup)
        result = self.case.dispatch(env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        rid = self.case.manifest(result)["run"]
        runs = Path(self.case.manifest(result)["log"]).parent
        return result, json.loads((runs / f"{rid}.meta.json").read_text()), runs, rid

    def test_v2_fields_are_added_without_dropping_v1_fields(self):
        result, meta, runs, rid = self.dispatch("codex")
        for key in ("id", "mode", "engine", "model", "brief", "root", "session", "started"):
            self.assertIn(key, meta)
        self.assertEqual(meta["schema"], 2)
        self.assertEqual(meta["requested"]["engine_source"], "brief")
        self.assertEqual(meta["cwd"], str(self.case.root))
        self.assertTrue(meta["plugin"]["version"])
        self.assertEqual(len(meta["brief_sha256"]), 64)
        states = [json.loads(line)["state"] for line in (runs / f"{rid}.events.jsonl").read_text().splitlines()]
        self.assertEqual(states, ["created", "running", "engine_exited", "collected", "no_changes"])

    def test_codex_session_id_comes_from_the_log_banner(self):
        _, meta, _, _ = self.dispatch("codex")
        self.assertEqual(meta["engine_session_id"], "01a14614-0000-7000-8000-000000000001")

    def test_claude_gets_a_preassigned_session_id(self):
        _, meta, _, _ = self.dispatch("claude")
        args = next(c for c in self.case.call_log() if c["engine"] == "claude")["args"]
        self.assertEqual(args[args.index("--session-id") + 1], meta["engine_session_id"])

    def test_grok_session_is_titled_with_the_run_and_resolved(self):
        _, meta, _, rid = self.dispatch("grok")
        run = next(c for c in self.case.call_log() if c["engine"] == "opencode" and "run" in c["args"])
        self.assertEqual(run["args"][run["args"].index("--title") + 1], rid)
        self.assertEqual(run["args"][run["args"].index("--") + 1][:5], "ROLE:")
        self.assertEqual(meta["engine_session_id"], "ses_fake1")
        self.assertIsNone(meta["requested"]["variant"])

    def test_instruction_hashes_match_when_unchanged(self):
        result, meta, _, _ = self.dispatch("codex", FSA_FAKE_MODE="touch", FSA_FAKE_TOUCH="app.py")
        self.assertFalse(meta["instructions_changed"])
        self.assertIn("STATUS=OK", result.stdout)

    def test_instruction_change_during_the_run_is_flagged_not_accepted(self):
        self.case = DispatchCase("codex")
        self.addCleanup(self.case.cleanup)
        (self.case.root / "AGENTS.md").write_text("rule one\n")
        result = self.case.dispatch(env={"FSA_FAKE_MODE": "touch", "FSA_FAKE_TOUCH": str(self.case.root / "AGENTS.md")})
        rid = self.case.manifest(result)["run"]
        meta = json.loads((Path(self.case.manifest(result)["log"]).parent / f"{rid}.meta.json").read_text())
        self.assertTrue(meta["instructions_changed"])
        self.assertEqual([i["path"] for i in meta["instructions_at_dispatch"]], ["AGENTS.md"])
        self.assertIn("STATUS=INSTRUCTIONS_CHANGED", result.stdout)
        self.assertNotIn("STATUS=OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
