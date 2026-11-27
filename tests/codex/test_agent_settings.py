"""Agent settings per session: the CTO default is copied at session start, the dispatcher and the Agent hook
read the session's own copy, and a later change to the default never reaches a running session."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from dispatch_support import SCRIPTS, DispatchCase

sys.path.insert(0, str(SCRIPTS / "lib"))
import agent_config  # noqa: E402

HOOK = SCRIPTS.parent / "hooks" / "agent-model"


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old = os.environ.get("CLAUDE_CONFIG_DIR")
        os.environ["CLAUDE_CONFIG_DIR"] = self.tmp.name
        self.addCleanup(lambda: os.environ.pop("CLAUDE_CONFIG_DIR") if self.old is None
                        else os.environ.__setitem__("CLAUDE_CONFIG_DIR", self.old))

    def test_snapshot_copies_the_default_once_and_later_default_changes_do_not_reach_it(self):
        agent_config.save(None, {"implementer": "codex", "subagents": {"test-runner": "haiku"}})
        self.assertEqual(agent_config.snapshot("s1")["implementer"], "codex")
        agent_config.save(None, {"implementer": "grok"})
        self.assertEqual(agent_config.snapshot("s1")["implementer"], "codex")
        self.assertEqual(agent_config.snapshot("s2"), {"implementer": "grok"})

    def test_inherit_copies_the_old_session_over_the_new_one(self):
        agent_config.save("old", {"implementer": "codex"})
        agent_config.save("new", {})
        self.assertEqual(agent_config.inherit("new", "old"), {"implementer": "codex"})
        self.assertEqual(agent_config.load("new"), {"implementer": "codex"})
        self.assertIsNone(agent_config.inherit("new", "never-had-settings"))
        self.assertEqual(agent_config.load("new"), {"implementer": "codex"})

    def test_a_session_without_a_file_has_no_settings(self):
        agent_config.save(None, {"implementer": "codex"})
        self.assertIsNone(agent_config.load("old-session"))

    def test_validation_drops_empty_values_and_refuses_bad_ones(self):
        self.assertEqual(agent_config.validate({"implementer": "", "models": {"codex_plan": ""}, "subagents": {}}), {})
        for bad in ({"implementer": "gpt"}, {"models": {"codex_plan": "x; rm -rf /"}}, {"models": {"nope": "m"}},
                    {"subagents": {"test-runner": "gpt-5"}}, {"subagents": {"evil": "haiku"}}, []):
            with self.assertRaises(ValueError):
                agent_config.validate(bad)
        with self.assertRaises(ValueError):
            agent_config.path_of("../escape")

    def test_env_lines_name_only_what_the_session_sets(self):
        cfg = {"implementer": "grok", "models": {"grok_implement": "xai/grok-5"}, "grok_scan": True}
        self.assertEqual(agent_config.env_lines(cfg),
                         ["FSA_IMPLEMENTER=grok", "FSA_GROK_MODEL_IMPLEMENT=xai/grok-5", "FSA_GROK_INVESTIGATE=1"])

    def test_set_implementer_switches_engine_and_its_implement_model_and_keeps_the_rest(self):
        agent_config.save("s1", {"implementer": "grok", "models": {"codex_plan": "gpt-x"}, "grok_scan": True})
        self.assertEqual(agent_config.set_implementer("s1", "codex"),
                         {"implementer": "codex", "models": {"codex_plan": "gpt-x", "codex_implement": "gpt-6.1-sol"},
                          "grok_scan": True})
        cfg = agent_config.set_implementer("s1", "claude")
        self.assertEqual((cfg["implementer"], cfg["models"]["claude_implement"]), ("claude", "claude-sonnet-5-5"))
        self.assertEqual(agent_config.load("s1"), cfg)
        self.assertEqual(agent_config.set_implementer("fresh", "codex")["implementer"], "codex")
        for bad in ("grok", "gpt", "", None, ["codex"]):
            with self.assertRaises(ValueError):
                agent_config.set_implementer("s1", bad)
        self.assertIn("gpt-6.1-sol", agent_config.model_choices()["codex"])

    def test_current_session_prefers_the_dispatcher_pin(self):
        self.assertEqual(agent_config.current_session(
            {"FSA_SESSION_PIN": "/x/pins/session-abc.json", "CLAUDE_CODE_SESSION_ID": "other"}), "abc")
        self.assertEqual(agent_config.current_session({"CLAUDE_CODE_SESSION_ID": "cc"}), "cc")
        self.assertIsNone(agent_config.current_session({}))

    def test_implementer_cli_shows_and_switches_the_current_session(self):
        script = SCRIPTS / "lib" / "agent_config.py"
        env = {**os.environ, "FSA_SESSION_PIN": "", "CLAUDE_CODE_SESSION_ID": "s9"}

        def cli(*args):
            return subprocess.run([sys.executable, "-I", str(script), "implementer", *args], capture_output=True,
                                  text=True, env=env, timeout=30)

        shown = cli()
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertIn("implementer: claude", shown.stdout)
        self.assertFalse(agent_config.path_of("s9").exists())
        run = cli("Codex")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.splitlines(), ["session: s9", "implementer: codex", "implement model: gpt-6.1-sol"])
        self.assertEqual(agent_config.load("s9")["models"]["codex_implement"], "gpt-6.1-sol")
        self.assertEqual(cli("--session", "s8", "claude").stdout.splitlines()[1:],
                         ["implementer: claude", "implement model: claude-sonnet-5-5"])
        self.assertEqual(cli("grok").returncode, 1)
        env["CLAUDE_CODE_SESSION_ID"] = ""
        self.assertEqual(cli("codex").returncode, 2)

    def test_hook_sets_the_configured_subagent_model(self):
        agent_config.save("s1", {"subagents": {"bounded-extractor": "sonnet"}})
        event = {"session_id": "s1", "tool_input": {"subagent_type": "fullstack-agents:bounded-extractor", "prompt": "p"}}
        run = subprocess.run(["bash", str(HOOK)], input=json.dumps(event), capture_output=True, text=True,
                             env={**os.environ}, timeout=30)
        out = json.loads(run.stdout)["hookSpecificOutput"]
        self.assertEqual(out["updatedInput"], {**event["tool_input"], "model": "sonnet"})
        other = {"session_id": "s1", "tool_input": {"subagent_type": "Explore", "prompt": "p"}}
        run = subprocess.run(["bash", str(HOOK)], input=json.dumps(other), capture_output=True, text=True,
                             env={**os.environ}, timeout=30)
        self.assertEqual(run.stdout.strip(), "")


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.case = DispatchCase("codex")
        self.addCleanup(self.case.cleanup)
        self.config = self.case.base / "claude-config"
        self.case.brief.write_text("PLAN: none: test\nALLOWED_PATHS:\napp.py\n\nGOAL: x\n")

    def dispatch(self, cfg, **env):
        sessions = self.config / "fullstack-agents" / "agents"
        sessions.mkdir(parents=True, exist_ok=True)
        (sessions / "session-s1.json").write_text(json.dumps(cfg))
        pin = str(self.config / "fullstack-agents" / "pins" / "session-s1.json")
        result = self.case.dispatch(env={"CLAUDE_CONFIG_DIR": str(self.config), "FSA_SESSION_PIN": pin, **env})
        self.assertEqual(result.returncode, 0, result.stderr)
        runs = Path(self.case.manifest(result)["log"]).parent
        return json.loads((runs / f"{self.case.manifest(result)['run']}.meta.json").read_text())

    def test_session_settings_win_over_the_environment(self):
        meta = self.dispatch({"implementer": "codex", "models": {"codex_implement": "gpt-test-1"}},
                             FSA_IMPLEMENTER="claude", FSA_CODEX_MODEL_IMPLEMENT="gpt-env")
        self.assertEqual((meta["engine"], meta["model"], meta["requested"]["engine_source"]),
                         ("codex", "gpt-test-1", "session"))

    def test_without_session_settings_the_environment_still_applies(self):
        meta = self.dispatch({}, FSA_IMPLEMENTER="codex")
        self.assertEqual((meta["engine"], meta["requested"]["engine_source"]), ("codex", "env"))


if __name__ == "__main__":
    unittest.main()
