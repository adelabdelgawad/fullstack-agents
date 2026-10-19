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


def run(hook, case, extra_env=None, source="startup", agent_type=None):
    env = {**case.env, "CLAUDE_CONFIG_DIR": str(case.base / "cfg"), "FSA_STATE_HOME": str(case.base / "state"),
           "TMPDIR": str(case.base), **(extra_env or {})}
    payload = {"session_id": "s1", "source": source, **({"agent_type": agent_type} if agent_type else {})}
    proc = subprocess.run(["bash", str(PLUGIN / "hooks" / hook)], input=json.dumps(payload),
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


class RuleHomeTests(unittest.TestCase):
    """P2: each always-loaded rule has one home, and the doctrine never doubles the lead prompt."""
    LEAD = (PLUGIN / "agents/lead/fullstack-agent.md").read_text()
    DOCTRINE = (PLUGIN / "hooks/session-doctrine.md").read_text()
    POLICY = (PLUGIN / "policies/engineering-conventions.md").read_text()
    FLOW = (PLUGIN / "skills/task-flow/SKILL.md").read_text()

    def setUp(self):
        self.case = DispatchCase("codex")
        self.addCleanup(self.case.cleanup)
        write(self.case.root / "Cargo.toml", "[workspace]\n")

    def test_lead_session_gets_detection_without_the_doctrine(self):
        core = run("session-start", self.case, agent_type="fullstack-agents:fullstack-agent")
        self.assertIn("**Project Detection:**", core)
        self.assertNotIn("You have fullstack-agents", core)

    def test_other_main_agents_still_get_the_doctrine(self):
        for agent in (None, "general-purpose"):
            with self.subTest(agent=agent):
                self.assertIn("You have fullstack-agents", run("session-start", self.case, agent_type=agent))

    def test_worktree_rules_are_conditional_on_the_development_mode(self):
        for name, text in (("lead", self.LEAD), ("doctrine", self.DOCTRINE), ("policy", self.POLICY)):
            flat = " ".join(text.split())
            for sentence in flat.split(". "):
                if "own worktree" in sentence:
                    with self.subTest(source=name, sentence=sentence[:80]):
                        self.assertRegex(sentence, r"development mode|Default mode|[Bb]are-metal")

    def test_retry_limit_lives_only_in_task_flow(self):
        self.assertIn("Two retries maximum", self.FLOW)
        for text in (self.LEAD, self.DOCTRINE, self.POLICY):
            self.assertNotIn("Two retries", text)

    def test_lead_prompt_states_the_precedence_order(self):
        flat = " ".join(self.LEAD.split())
        order = ["the user's explicit instruction", "`CLAUDE.md`", "this prompt", "the `task-flow` skill", "the policy profile"]
        positions = [flat.index(item, flat.index("Precedence")) for item in order]
        self.assertEqual(positions, sorted(positions))


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

    def test_spill_file_is_owner_only_and_an_unwritable_home_still_delivers_the_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = self.emit("HEAD\n" + "y" * 5000, tmp, limit="1000", keep="5")["hookSpecificOutput"]["additionalContext"]
            path = Path(ctx.rsplit("Read tool: ", 1)[1].strip())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            blocked = Path(tmp) / "ro"
            blocked.mkdir(mode=0o500)
            try:
                ctx = self.emit("HEAD\n" + "y" * 5000, str(blocked / "home"), limit="1000", keep="5")
            finally:
                blocked.chmod(0o700)
            text = ctx["hookSpecificOutput"]["additionalContext"]
            self.assertTrue(text.startswith("HEAD\n"))
            self.assertIn("could not be saved", text)

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
