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
        self.case.binding(runs_dir="~/.codex/project-runs")
        self.assertEqual(self.run_dir_of(self.case.dispatch()), self.case.home / ".codex/project-runs")

    def test_a_refused_dispatch_leaves_no_copied_lib_dir(self):
        self.case.brief.write_text("IMPLEMENTER: codex\nPLAN: none: test\n\nGOAL: no paths\n")
        result = self.case.dispatch()
        self.assertEqual(result.returncode, 2)
        runs = self.case.home / ".codex/fsa-runs"
        self.assertEqual(list(runs.glob("dispatch-*.lib")) if runs.exists() else [], [])

    def test_env_wins_over_the_binding(self):
        self.case.binding(runs_dir="~/.codex/project-runs")
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


class RoleContractTests(unittest.TestCase):
    """One implementer contract for every engine; project rules reach each engine its own way."""

    CONTRACT = Path(__file__).resolve().parents[2] / "plugins/fullstack-agents/scripts/lib/roles/implementer.md"

    def run_engine(self, engine, docs=()):
        case = DispatchCase(engine)
        self.addCleanup(case.cleanup)
        for name in docs:
            (case.root / name).write_text(f"# {name}\n")
        result = case.dispatch(env={"FSA_FAKE_MODE": "touch", "FSA_FAKE_TOUCH": "app.py"})
        self.assertEqual(result.returncode, 0, result.stderr)
        m = case.manifest(result)
        runs = Path(m["log"]).parent
        meta = json.loads((runs / f"{m['run']}.meta.json").read_text())
        prompt = (runs / f"{m['run']}.prompt.md").read_text()
        call = next(c for c in case.call_log() if c["engine"] in ("codex", "claude") or "run" in c["args"])
        return meta, prompt, call

    def test_every_engine_gets_the_same_contract_and_role(self):
        contract = self.CONTRACT.read_text()
        hashes = set()
        for engine in ("claude", "codex", "grok"):
            with self.subTest(engine=engine):
                meta, prompt, call = self.run_engine(engine)
                self.assertTrue(prompt.startswith(contract))
                self.assertEqual(call["env"]["FSA_ROLE"], "implementer")
                hashes.add(meta["role_contract"]["sha256"])
        self.assertEqual(len(hashes), 1)

    def test_codex_scope_wording_matches_its_enforcement(self):
        _, prompt, _ = self.run_engine("codex")
        self.assertIn("reported as a scope violation after the run", prompt)
        _, prompt, _ = self.run_engine("grok")
        self.assertIn("the edit and write tools accept only", prompt)

    def test_codex_drops_plugins_and_falls_back_to_claude_md_only_without_agents_md(self):
        _, _, call = self.run_engine("codex", docs=("CLAUDE.md",))
        args = call["args"]
        self.assertEqual(args[args.index("--disable") + 1], "plugins")
        self.assertIn('project_doc_fallback_filenames=["CLAUDE.md"]', args)
        _, _, call = self.run_engine("codex", docs=("CLAUDE.md", "AGENTS.md"))
        self.assertFalse(any("project_doc_fallback_filenames" in a for a in call["args"]))

    def test_grok_config_lists_the_project_rules_file(self):
        for docs, expected in ((("CLAUDE.md",), ["CLAUDE.md"]), (("CLAUDE.md", "AGENTS.md"), ["AGENTS.md"]), ((), [])):
            with self.subTest(docs=docs):
                meta, _, call = self.run_engine("grok", docs)
                config = json.loads(Path(call["env"]["OPENCODE_CONFIG"]).read_text())
                self.assertEqual(config["instructions"], expected)
                self.assertEqual(meta["project_docs"], expected[0] if expected else None)

    def test_claude_gets_agents_md_unless_claude_md_imports_it(self):
        _, _, call = self.run_engine("claude", docs=("AGENTS.md",))
        args = call["args"]
        self.assertEqual(args[args.index("--append-system-prompt") + 1], "# AGENTS.md")
        case = DispatchCase("claude")
        self.addCleanup(case.cleanup)
        (case.root / "AGENTS.md").write_text("# AGENTS.md\n")
        (case.root / "CLAUDE.md").write_text("# CLAUDE.md\n\n@AGENTS.md\n")
        result = case.dispatch(env={"FSA_FAKE_MODE": "touch", "FSA_FAKE_TOUCH": "app.py"})
        self.assertEqual(result.returncode, 0, result.stderr)
        call = next(c for c in case.call_log() if c["engine"] == "claude")
        self.assertNotIn("--append-system-prompt", call["args"])


if __name__ == "__main__":
    unittest.main()
