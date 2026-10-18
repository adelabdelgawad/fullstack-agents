"""SessionStart delivery: every block stays under Claude Code's per-hook limit, oversize text is never silently cut,
the policy profile is its own block, and the doctrine defers branch/worktree rules to the project's development mode."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from dispatch_support import SCRIPTS, DispatchCase, write

PLUGIN = SCRIPTS.parent
HOOKS = json.loads((PLUGIN / "hooks/hooks.json").read_text())["hooks"]
CAP = 10_000


def run(hook, case, extra_env=None, source="startup"):
    env = {**case.env, "CLAUDE_CONFIG_DIR": str(case.base / "cfg"), "FSA_STATE_HOME": str(case.base / "state"),
           "TMPDIR": str(case.base), **(extra_env or {})}
    proc = subprocess.run(["bash", str(PLUGIN / "hooks" / hook)], input=json.dumps({"session_id": "s1", "source": source}),
                          capture_output=True, text=True, cwd=case.root, env=env)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"] if proc.stdout.strip() else ""


class SessionStartDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.case = DispatchCase("codex")
        self.addCleanup(self.case.cleanup)
        write(self.case.root / "Cargo.toml", "[workspace]\n")  # a governed project gets the doctrine

    def test_both_hooks_are_wired_synchronously_for_every_session_source(self):
        group = HOOKS["SessionStart"][0]
        self.assertEqual(group["matcher"], "startup|resume|clear|compact")
        commands = [h["command"] for h in group["hooks"] if not h.get("async")]
        self.assertTrue(any(c.endswith(" session-start") for c in commands))
        self.assertTrue(any(c.endswith(" session-policy") for c in commands))

    def test_each_block_fits_the_hook_limit_with_the_profile_and_a_full_board(self):
        self.case.binding(policy_profile="engineering-conventions")
        core = run("session-start", self.case)
        policy = run("session-policy", self.case)
        self.assertLess(len(core), 4500)
        self.assertLessEqual(len(policy), 9000)
        self.assertIn("**Policy profile engineering-conventions:**", policy)
        self.assertNotIn("Policy profile engineering-conventions:", core)
        self.assertIn("You are the session lead", core)

    def test_oversize_text_points_to_a_readable_file_with_the_complete_content(self):
        env = {"FSA_HOOK_CONTEXT_MAX": "1500"}
        core = run("session-start", self.case, env)
        self.assertLessEqual(len(core), 1500)
        self.assertIn("CONTEXT INCOMPLETE", core)
        path = Path(core.rsplit("Read tool: ", 1)[1].strip())
        self.assertTrue(path.is_file() and os.access(path, os.R_OK))
        full = path.read_text()
        self.assertIn("**Plugin scripts:**", full)
        self.assertTrue(full.startswith(core.split("\n\n[fullstack-agents] CONTEXT INCOMPLETE")[0]))

    def test_essential_rules_survive_a_board_at_its_cap(self):
        fake = self.case.base / "plugin"
        subprocess.run(["cp", "-r", str(PLUGIN), str(fake)], check=True)
        write(fake / "scripts" / "team-board", "#!/bin/sh\npython3 -c \"print('note ' * 3000)\"\n", 0o755)
        env = {**self.case.env, "CLAUDE_CONFIG_DIR": str(self.case.base / "cfg"), "TMPDIR": str(self.case.base),
               "FSA_STATE_HOME": str(self.case.base / "state")}
        proc = subprocess.run(["bash", str(fake / "hooks/session-start")], input='{"session_id":"s1","source":"startup"}',
                              capture_output=True, text=True, cwd=self.case.root, env=env)
        core = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertLess(len(core), 4500)
        self.assertIn("You are the session lead", core)
        self.assertIn("board truncated", core)
        self.assertNotIn("CONTEXT INCOMPLETE", core)

    def test_policy_hook_silent_without_profile_and_warns_on_invalid(self):
        self.assertEqual(run("session-policy", self.case), "")
        self.case.binding(policy_profile="no-such-profile")
        self.assertIn("no-such-profile", run("session-policy", self.case))

    def test_doctrine_defers_worktrees_to_the_project_development_mode(self):
        core = run("session-start", self.case)
        self.assertNotIn("Work in your own\nworktree", core)
        self.assertNotIn("Work in your own worktree", core)
        self.assertIn("project's development mode", core)


class HookContextHelperTests(unittest.TestCase):
    HELPER = SCRIPTS / "lib" / "hook_context.py"

    def emit(self, text, tmp, limit="9000", keep="100"):
        proc = subprocess.run([sys.executable, "-I", str(self.HELPER), "emit", "--event", "SessionStart",
                               "--name", "x", "--session", "s/../1", "--keep", keep], input=text,
                              capture_output=True, text=True,
                              env={**os.environ, "FSA_STATE_HOME": tmp, "FSA_HOOK_CONTEXT_MAX": limit})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout) if proc.stdout.strip() else None

    def test_short_text_passes_unchanged_in_both_shapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.emit("héllo \"q\"\n", tmp)
            self.assertEqual(out["hookSpecificOutput"]["additionalContext"], "héllo \"q\"\n")
            self.assertEqual(out["additional_context"], "héllo \"q\"\n")

    def test_empty_text_emits_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(self.emit("  \n", tmp))

    def test_spill_keeps_the_head_and_names_a_file_inside_the_state_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = "ESSENTIAL\n" + "x" * 20000
            ctx = self.emit(text, tmp, limit="1000", keep="10")["hookSpecificOutput"]["additionalContext"]
            self.assertLessEqual(len(ctx), 1000)
            self.assertTrue(ctx.startswith("ESSENTIAL\n"))
            path = Path(ctx.rsplit("Read tool: ", 1)[1].strip())
            self.assertEqual(path.parent, Path(tmp) / "context")
            self.assertEqual(path.read_text(), text)


if __name__ == "__main__":
    unittest.main()
