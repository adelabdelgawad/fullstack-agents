"""Optional policy profile: delivery in prompt.md and session-start, meta record, codex_add_dirs."""
import hashlib
import json
import subprocess
import unittest
from pathlib import Path

from dispatch_support import REPO, SCRIPTS, DispatchCase

PLUGIN = SCRIPTS.parent
PROFILE = PLUGIN / "policies/engineering-conventions.md"
HOOK = PLUGIN / "hooks/session-start"
POLICY_HOOK = PLUGIN / "hooks/session-policy"


class PromptDeliveryTests(unittest.TestCase):
    def dispatch(self, engine, **binding):
        case = DispatchCase(engine)
        self.addCleanup(case.cleanup)
        if binding:
            case.binding(**binding)
        result = case.dispatch(env={"FSA_FAKE_MODE": "touch", "FSA_FAKE_TOUCH": "app.py"})
        m = case.manifest(result)
        runs = Path(m["log"]).parent if "log" in m else None
        return case, result, m, runs

    def test_profile_follows_the_contract_for_every_engine(self):
        contract = (PLUGIN / "scripts/lib/roles/implementer.md").read_text()
        for engine in ("claude", "codex", "grok"):
            with self.subTest(engine=engine):
                case, result, m, runs = self.dispatch(engine, policy_profile="engineering-conventions")
                self.assertEqual(result.returncode, 0, result.stderr)
                prompt = (runs / f"{m['run']}.prompt.md").read_text()
                self.assertTrue(prompt.startswith(contract))
                self.assertIn("## Every agent", prompt)
                self.assertIn("Repro before hypothesis", prompt)
                self.assertLess(prompt.index("## Every agent"), prompt.index("GOAL: x"))
                meta = json.loads((runs / f"{m['run']}.meta.json").read_text())
                self.assertEqual(meta["policy_profile"]["name"], "engineering-conventions")
                self.assertEqual(meta["policy_profile"]["sha256"],
                                  hashlib.sha256(PROFILE.read_bytes()).hexdigest())

    def test_profile_absent_when_policy_profile_unset(self):
        case, result, m, runs = self.dispatch("codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        prompt = (runs / f"{m['run']}.prompt.md").read_text()
        self.assertNotIn("## Every agent", prompt)
        meta = json.loads((runs / f"{m['run']}.meta.json").read_text())
        self.assertIsNone(meta["policy_profile"])

    def test_unknown_profile_refuses_before_any_engine_call(self):
        case = DispatchCase("codex")
        self.addCleanup(case.cleanup)
        case.binding(policy_profile="no-such-profile")
        result = case.dispatch()
        self.assertEqual(result.returncode, 2)
        self.assertIn("policy_profile", result.stderr)
        self.assertEqual(case.call_log(), [])


class CodexAddDirsTests(unittest.TestCase):
    def setUp(self):
        self.case = DispatchCase("codex")
        self.addCleanup(self.case.cleanup)

    def add_dir_paths(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        call = next(c for c in self.case.call_log() if c["engine"] == "codex")
        args = call["args"]
        return [args[i + 1] for i, v in enumerate(args) if v == "--add-dir"]

    def test_codex_add_dirs_from_conf_reaches_add_dir(self):
        cache = self.case.base / "cache dir"
        self.case.binding(codex_add_dirs=str(cache))
        result = self.case.dispatch()
        self.assertEqual(self.add_dir_paths(result), [str(cache)])
        self.assertTrue(cache.is_dir())

    def test_env_codex_add_dirs_wins_over_conf(self):
        conf_dir = self.case.base / "conf-dir"
        env_dir = self.case.base / "env-dir"
        self.case.binding(codex_add_dirs=str(conf_dir))
        result = self.case.dispatch(env={"FSA_CODEX_ADD_DIRS": str(env_dir)})
        self.assertEqual(self.add_dir_paths(result), [str(env_dir)])
        self.assertFalse(conf_dir.exists())


class SessionStartProfileTests(unittest.TestCase):
    def setUp(self):
        self.case = DispatchCase("codex")
        self.addCleanup(self.case.cleanup)

    def context(self):
        """Every SessionStart block the model receives: session-start plus the separate session-policy hook."""
        blocks = []
        for hook_path in (HOOK, POLICY_HOOK):
            hook = subprocess.run(["bash", str(hook_path)], input=json.dumps({"session_id": "s", "source": "startup"}),
                                  capture_output=True, text=True, cwd=self.case.root,
                                  env={**self.case.env, "CLAUDE_CONFIG_DIR": str(self.case.base / "cfg")})
            self.assertEqual(hook.returncode, 0, hook.stderr)
            if hook.stdout.strip():
                block = json.loads(hook.stdout)["hookSpecificOutput"]["additionalContext"]
                self.assertLessEqual(len(block), 9000)
                blocks.append(block)
        return "\n".join(blocks)

    def test_session_start_includes_the_profile_when_set(self):
        self.case.binding(policy_profile="engineering-conventions")
        ctx = self.context()
        self.assertIn("**Policy profile engineering-conventions:**", ctx)
        self.assertIn("## Lead", ctx)

    def test_session_start_omits_the_profile_when_unset(self):
        ctx = self.context()
        self.assertNotIn("Policy profile", ctx)

    def test_session_start_warns_on_an_unknown_profile(self):
        self.case.binding(policy_profile="no-such-profile")
        ctx = self.context()
        self.assertIn("no-such-profile", ctx)
        self.assertNotIn("Policy profile no-such-profile:", ctx)


if __name__ == "__main__":
    unittest.main()
