"""Behavioral checks with local fake CLIs; never call an authenticated model."""
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "integrations/codex/scripts"
sys.path.insert(0, str(SCRIPTS))
from build import SOURCE, frontmatter, render
from install import install


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def run(command, **kwargs):
    return subprocess.run(command, capture_output=True, text=True, **kwargs)


class BundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = tempfile.TemporaryDirectory(prefix="fsa-codex-tests-")
        cls.bundle = Path(cls.scratch.name) / "bundle"
        cls.inventory = render(cls.bundle)

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    def test_every_source_skill_and_resource_is_available(self):
        for source in (SOURCE / "skills").iterdir():
            if not source.is_dir():
                continue
            target = self.bundle / "skills" / ("fullstack-agents-" + source.name)
            self.assertTrue((target / "SKILL.md").is_file())
            for resource in source.rglob("*"):
                if resource.is_file() and resource.name != "SKILL.md":
                    self.assertTrue((target / resource.relative_to(source)).is_file())
        for name in self.inventory["skills"]:
            metadata, _ = frontmatter((self.bundle / "skills" / name / "SKILL.md").read_text())
            self.assertEqual(metadata["name"], name)
            self.assertTrue(metadata["description"])
            self.assertLessEqual(len(name), 64)

    def test_native_roles_have_valid_toml_and_inherit_models(self):
        for record in self.inventory["agents"]:
            role = tomllib.loads((self.bundle / "roles" / (record["name"] + ".toml")).read_text())
            self.assertEqual(role["name"], record["name"])
            self.assertTrue(role["developer_instructions"])
            self.assertNotIn("model", role)
            if record["read_only"]:
                self.assertEqual(role["sandbox_mode"], "read-only")

    def test_build_leaves_claude_sources_unchanged(self):
        for name, expected in self.inventory["source_hashes"].items():
            self.assertEqual(hashlib.sha256((SOURCE / name).read_bytes()).hexdigest(), expected)

    def test_build_refuses_nonempty_output(self):
        with self.assertRaises(ValueError):
            render(self.bundle)

    def test_no_dashboard_or_claude_dispatcher_is_packaged(self):
        self.assertFalse((self.bundle / "commands/dashboard.md").exists())
        self.assertFalse((self.bundle / "scripts/codex-task.sh").exists())
        self.assertTrue((self.bundle / "scripts/handoff.py").exists())
        self.assertTrue((self.bundle / "scripts/phase.py").exists())

    def test_rendered_workflow_resolves_bare_metal_binding_before_worktrees(self):
        agents = (self.bundle / "AGENTS.md").read_text()
        task_flow = (self.bundle / "skills/fullstack-agents-task-flow/SKILL.md").read_text()
        coordination = (self.bundle / "skills/fullstack-agents-team-coordination/SKILL.md").read_text()
        for text in (agents, task_flow, coordination):
            self.assertIn("resolve", text.lower())
            self.assertIn("existing", text.lower())
            self.assertIn("do not create another worktree", text.lower())
        self.assertLess(task_flow.index("resolve the project\n   execution binding"),
                        task_flow.index("Check `git status --short`"))

    def test_bare_metal_no_deploy_keeps_authorized_dev_completion_steps(self):
        agents = (self.bundle / "AGENTS.md").read_text()
        self.assertIn("committed to the bound development branch", agents)
        self.assertIn("authorized native development reload", agents)
        self.assertIn("development database migration", agents)
        self.assertIn("Do not merge to main", agents)
        self.assertIn("Docker production app images", agents)

    def test_phase_journal_root_stays_at_original_session_cwd(self):
        for path in (self.bundle / "AGENTS.md",
                     self.bundle / "skills/fullstack-agents-task-flow/SKILL.md"):
            text = path.read_text()
            self.assertIn("original session working directory", text)
            self.assertIn("phase journal root", text)

    def test_native_plugin_manifest_and_hooks_reference_bundled_resources(self):
        manifest = json.loads((self.bundle / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(manifest["name"], "fullstack-agents-codex")
        self.assertTrue((self.bundle / manifest["skills"]).is_dir())
        hooks = json.loads((self.bundle / manifest["hooks"]).read_text())["hooks"]
        self.assertEqual(set(hooks), {"SessionStart", "UserPromptSubmit", "PostToolUse"})
        for groups in hooks.values():
            self.assertIn('${PLUGIN_ROOT}', groups[0]["hooks"][0]["command"])
            self.assertIn('runpy.run_path', groups[0]["hooks"][0]["command"])
        self.assertTrue((self.bundle / "scripts/hook.py").is_file())

    def test_hook_survives_evicted_version_and_selects_latest_semantic_version(self):
        hooks = json.loads((self.bundle / "hooks/hooks.json").read_text())["hooks"]
        with tempfile.TemporaryDirectory(prefix="fsa hook cache ") as directory:
            cache = Path(directory)
            old = cache / "3.58.6"
            old.mkdir()
            for version in ("3.9.0", "3.59.0", "3.100.0", "not-a-version"):
                write(cache / version / "scripts/hook.py",
                      "import json,sys; print(json.dumps({'version':" + repr(version) +
                      ", 'mode':sys.argv[1], 'payload':json.load(sys.stdin)}))")
            env = dict(os.environ, PLUGIN_ROOT=str(old))
            old.rmdir()  # Reproduce cache eviction while the session retains its hook command.
            for event, mode in (("SessionStart", "start"), ("UserPromptSubmit", "prompt"), ("PostToolUse", "post")):
                command = hooks[event][0]["hooks"][0]["command"]
                result = run(["bash", "-c", command], env=env, input='{"cwd":"/fixture"}')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {"version":"3.100.0", "mode":mode, "payload":{"cwd":"/fixture"}})
            write(old / "scripts/hook.py", "print('current-root')")
            result = run(["bash", "-c", hooks["SessionStart"][0]["hooks"][0]["command"]], env=env, input="{}")
            self.assertEqual(result.stdout.strip(), "current-root")

    def test_hook_isolates_workspace_imports_and_retains_hook_sibling_imports(self):
        hooks = json.loads((self.bundle / "hooks/hooks.json").read_text())["hooks"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            workspace.mkdir()
            for module in ("re", "pathlib"):
                write(workspace / (module + ".py"), "raise RuntimeError('workspace module must not load')")
            script = root / "cache/3.59.1/scripts/hook.py"
            write(script, "import hook_helper; print(hook_helper.VALUE)")
            write(script.parent / "hook_helper.py", "VALUE='sibling-import-ok'")
            env = dict(os.environ, PLUGIN_ROOT=str(root / "cache/3.58.6"), PYTHONPATH=str(workspace))
            result = run(["bash", "-c", hooks["SessionStart"][0]["hooks"][0]["command"]], cwd=workspace, env=env, input="{}")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "sibling-import-ok")

    def test_hook_missing_entire_cache_reports_actionable_failure(self):
        hooks = json.loads((self.bundle / "hooks/hooks.json").read_text())["hooks"]
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, PLUGIN_ROOT=str(Path(directory) / "missing" / "3.58.6"))
            result = run(["bash", "-c", hooks["SessionStart"][0]["hooks"][0]["command"]], env=env, input="{}")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("reinstall the plugin", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_large_skills_have_short_indexes_and_working_reference_links(self):
        entry = self.bundle / "skills/fullstack-agents-nextjs/SKILL.md"
        self.assertLess(len(entry.read_text()), 6000)
        self.assertGreater(len((entry.parent / "references/skill-guide.md").read_text()), len(entry.read_text()))
        for name in ("fullstack-agents-nextjs", "fullstack-agents-data-table"):
            guide = self.bundle / "skills" / name / "references/skill-guide.md"
            import re
            for raw in re.findall(r"\]\(([^\s)]+)\)", guide.read_text()):
                target = raw.split("#", 1)[0]
                if target and not target.startswith(("https:", "http:")):
                    self.assertTrue((guide.parent / target).exists(), f"broken link: {name}: {raw}")


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-codex-project-")
        self.root = Path(self.scratch.name) / "project with spaces"
        self.root.mkdir()
        for name, value in {".claude/settings.local.json": '{"agent":"existing"}',
                            "CLAUDE.md": "Existing Claude instructions\n",
                            "AGENTS.md": "Existing shared instructions\n",
                            ".codex/config.toml": 'model = "existing-model"\n',
                            ".codex/hooks.json": json.dumps({"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo existing"}]}]}}),
                            ".codex/agents/my-agent.toml": 'name = "my-agent"\n'}.items():
            write(self.root / name, value)
        self.originals = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def tearDown(self):
        self.scratch.cleanup()

    def install(self, dry=False):
        with contextlib.redirect_stdout(io.StringIO()):
            install(self.root, dry)

    def test_install_preserves_claude_shared_instructions_and_codex_settings(self):
        self.install()
        for name, value in self.originals.items():
            if name != ".codex/hooks.json":
                self.assertEqual((self.root / name).read_bytes(), value)
        hooks = json.loads((self.root / ".codex/hooks.json").read_text())["hooks"]
        self.assertEqual(hooks["SessionStart"][0]["hooks"][0]["command"], "echo existing")
        inventory = json.loads((self.root / ".codex/fullstack-agents/inventory.json").read_text())
        for name in inventory["skills"]:
            self.assertTrue((self.root / ".agents/skills" / name / "SKILL.md").is_file())
        # Absolute, quoted hook commands work when installed in a path with spaces.
        command = hooks["SessionStart"][1]["hooks"][0]["command"]
        result = run(command, shell=True, input='{"cwd":"' + str(self.root) + '"}', cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["hookEventName"], "SessionStart")

    def test_reinstall_is_idempotent_and_does_not_duplicate_hooks(self):
        self.install()
        first = (self.root / ".codex/hooks.json").read_bytes()
        self.install()
        self.assertEqual((self.root / ".codex/hooks.json").read_bytes(), first)
        self.assertEqual((self.root / ".codex/config.toml").read_bytes(), self.originals[".codex/config.toml"])

    def test_created_config_survives_reinstall(self):
        (self.root / ".codex/config.toml").unlink()
        self.install()
        config = self.root / ".codex/config.toml"
        config.write_text('model = "user-selected-after-install"\n')
        self.install()
        self.assertEqual(config.read_text(), 'model = "user-selected-after-install"\n')

    def test_dry_run_does_not_write_anything(self):
        self.install(dry=True)
        current = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(current, self.originals)

    def test_unowned_collision_fails_before_writing(self):
        conflict = self.root / ".codex/agents/fullstack-agents-review-security.toml"
        write(conflict, "custom role\n")
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(conflict.read_text(), "custom role\n")
        self.assertFalse((self.root / ".codex/fullstack-agents").exists())

    def test_modified_owned_file_is_not_overwritten(self):
        self.install()
        path = self.root / ".codex/fullstack-agents/AGENTS.md"
        path.write_text("local customization\n")
        hooks = (self.root / ".codex/hooks.json").read_bytes()
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(path.read_text(), "local customization\n")
        self.assertEqual((self.root / ".codex/hooks.json").read_bytes(), hooks)

    def test_symlinked_parent_is_refused(self):
        outside = Path(self.scratch.name) / "outside"
        outside.mkdir()
        (self.root / ".agents").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual(list(outside.iterdir()), [])


FAKE_CLAUDE = '''import json, os, sys
from pathlib import Path
Path(os.environ["FSA_TEST_CALL"]).write_text(json.dumps({"args": sys.argv[1:], "input": sys.stdin.read()}))
for name, value in json.loads(os.environ.get("FSA_TEST_WRITES", "{}")).items():
    Path(name).write_text(value)
if os.environ.get("FSA_TEST_EXIT"):
    sys.exit(int(os.environ["FSA_TEST_EXIT"]))
print(os.environ["FSA_TEST_RESPONSE"])
'''
FAKE_CODEX = '''import json, os, sys
from pathlib import Path
Path(os.environ["FSA_TEST_CALL"]).write_text(json.dumps({"args": sys.argv[1:], "input": sys.stdin.read()}))
for name, value in json.loads(os.environ.get("FSA_TEST_WRITES", "{}")).items():
    path = Path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)
output = Path(sys.argv[sys.argv.index("--output-last-message") + 1])
output.write_text(os.environ["FSA_TEST_RESPONSE"])
print('{"type":"thread.started","thread_id":"worker-child"}')
print('{"type":"thread.completed"}')
sys.exit(int(os.environ.get("FSA_TEST_EXIT", "0")))
'''


class CLITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle_tmp = tempfile.TemporaryDirectory(prefix="fsa-codex-cli-bundle-")
        cls.bundle = Path(cls.bundle_tmp.name) / "bundle"
        render(cls.bundle)

    @classmethod
    def tearDownClass(cls):
        cls.bundle_tmp.cleanup()

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-codex-cli-")
        self.root = Path(self.scratch.name) / "repo"
        self.root.mkdir()
        for args in (("init", "-q"), ("config", "user.email", "tests@example.invalid"), ("config", "user.name", "Tests")):
            subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)
        write(self.root / "app.py", "value = 1\n")
        write(self.root / "other.py", "other = 1\n")
        subprocess.run(["git", "-C", str(self.root), "add", "app.py", "other.py"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "baseline"], check=True)
        write(self.root / "app.py", "value = 2\n")
        self.plan = Path(self.scratch.name) / "plan.md"
        self.plan.write_text("Outcome: change value to 2\nFiles: app.py\nAcceptance: value equals 2\nChecks: fixture check passes\n")
        self.bin = Path(self.scratch.name) / "bin"
        self.bin.mkdir()
        for name, code in (("claude", FAKE_CLAUDE), ("codex", FAKE_CODEX)):
            path = self.bin / name
            path.write_text("#!" + sys.executable + "\n" + code)
            path.chmod(0o755)
        self.call = Path(self.scratch.name) / "call.json"
        self.env = {**os.environ, "PATH": str(self.bin) + os.pathsep + os.environ["PATH"], "FSA_TEST_CALL": str(self.call),
                    "CODEX_HOME": str(Path(self.scratch.name) / "codex-home"), "CODEX_THREAD_ID": "test-lead"}
        self.runs = Path(self.scratch.name) / "runs"
        self.runs.mkdir()

    def tearDown(self):
        self.scratch.cleanup()

    def audit(self, response=None, extra=()):
        self.env["FSA_TEST_RESPONSE"] = json.dumps(response or {"structured_output": {"verdict": "PASS", "summary": "No issues", "findings": []}})
        return run([sys.executable, str(self.bundle / "scripts/handoff.py"), "--root", str(self.root),
                    "--plan", str(self.plan), "--files", "app.py", "--runs-dir", str(self.runs), *extra], env=self.env)

    def issue(self, **changes):
        finding = {"file": "app.py", "line": 1, "severity": "medium", "issue": "Fixture finding",
                   "evidence": "value = 2", "repair_scope": ["app.py"]}
        finding.update(changes)
        return {"structured_output": {"verdict": "CHANGES", "summary": "Repair required", "findings": [finding]}}

    def test_audit_pass_uses_tool_free_claude_and_saves_evidence(self):
        result = self.audit()
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(result.stdout)
        self.assertEqual(manifest["verdict"], "PASS")
        handoff = json.loads(Path(manifest["handoff"]).read_text())
        self.assertFalse(handoff["claims_verified_by_lead"])
        self.assertEqual(handoff["source_hashes"]["app.py"], hashlib.sha256((self.root / "app.py").read_bytes()).hexdigest())
        call = json.loads(self.call.read_text())
        self.assertEqual(call["args"][call["args"].index("--tools") + 1], "")
        self.assertEqual(call["args"][call["args"].index("--setting-sources") + 1], "")
        self.assertIn("--disable-slash-commands", call["args"])
        self.assertNotIn("--dangerously-skip-permissions", call["args"])
        self.assertIn("-value = 1", call["input"])
        self.assertIn("+value = 2", call["input"])
        self.assertEqual((self.root / "app.py").read_text(), "value = 2\n")

    def test_identical_prior_pass_skips_model_and_changes_invalidate_reuse(self):
        first = self.audit()
        self.assertEqual(first.returncode, 0, first.stderr)
        prior = json.loads(first.stdout)["handoff"]
        self.call.unlink()
        reused = self.audit(extra=("--previous", prior))
        self.assertEqual(reused.returncode, 0, reused.stderr)
        self.assertTrue(json.loads(reused.stdout)["reused"])
        self.assertFalse(self.call.exists())
        write(self.root / "app.py", "value = 3\n")
        changed = self.audit(extra=("--previous", prior))
        self.assertEqual(changed.returncode, 0, changed.stderr)
        self.assertNotIn("reused", json.loads(changed.stdout))
        self.assertTrue(self.call.exists())

    def test_prior_pass_reuse_requires_same_plan_context_and_model(self):
        first = self.audit()
        prior = json.loads(first.stdout)["handoff"]
        for extra in [("--model", "other-auditor"), ("--context", "other.py:1:1")]:
            self.call.unlink()
            result = self.audit(extra=("--previous", prior, *extra))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(self.call.exists())
            self.assertNotIn("reused", json.loads(result.stdout))
        self.plan.write_text(self.plan.read_text()+"Changed acceptance.\n")
        self.call.unlink()
        result = self.audit(extra=("--previous", prior))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.call.exists())

    def test_audit_defaults_to_opus_and_preserves_overrides(self):
        self.env.pop("FSA_CLAUDE_AUDIT_MODEL", None)
        for env_model, extra, expected in (
            (None, (), "opus"),
            ("configured-auditor", (), "configured-auditor"),
            ("configured-auditor", ("--model", "explicit-auditor"), "explicit-auditor"),
        ):
            with self.subTest(expected=expected):
                if env_model:
                    self.env["FSA_CLAUDE_AUDIT_MODEL"] = env_model
                result = self.audit(extra=extra)
                self.assertEqual(result.returncode, 0, result.stderr)
                args = json.loads(self.call.read_text())["args"]
                self.assertEqual(args[args.index("--model") + 1], expected)

    def test_phase_cli_records_complete_flow_without_calling_a_model(self):
        state = Path(self.scratch.name) / "flow-state"
        env = {**self.env, "CODEX_THREAD_ID": "lead-session"}
        for phase in ("investigate", "plan", "implement", "validate", "audit", "complete"):
            result = run([sys.executable, str(self.bundle / "scripts/phase.py"),
                          "--root", str(self.root), "--phase", phase, "--state-dir", str(state)], env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((state / "lead-session.json").read_text())
        self.assertEqual((record["lead"], record["auditor"], record["phase"]), ("codex", "opus", "complete"))
        self.assertEqual([e["phase"] for e in record["history"]],
                         ["investigate", "plan", "implement", "validate", "audit", "complete"])
        self.assertFalse(self.call.exists())

    def test_task_tracking_reference_is_bundled_and_its_skill_link_resolves(self):
        skill = self.bundle / "skills/fullstack-agents-task-flow/SKILL.md"
        target = skill.parent / "references/task-tracking.md"
        self.assertTrue(target.is_file())
        self.assertIn("(references/task-tracking.md)", skill.read_text())
        self.assertIn("scripts/tasks.py", target.read_text())
        self.assertTrue((self.bundle / "scripts/task_tracking.py").is_file())
        self.assertTrue((self.bundle / "scripts/tasks.py").is_file())

    def test_phase_flow_links_tasks_and_refuses_premature_completion(self):
        env = {**self.env, "CODEX_THREAD_ID": "tracked-lead", "FSA_TASKS_DIR": str(Path(self.scratch.name) / "task-registry")}
        tasks = self.bundle / "scripts/tasks.py"
        result = run([sys.executable, str(tasks), "init", "--root", str(self.root), "--file", "docs/tasks/work.md", "--title", "Work", "--task", "T01|running|Implement|Audit pending"], env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        state = Path(self.scratch.name) / "task-flow-state"
        cmd = [sys.executable, str(self.bundle / "scripts/phase.py"), "--root", str(self.root), "--state-dir", str(state)]
        result = run([*cmd, "--phase", "implement"], env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((state / "tracked-lead.json").read_text())
        self.assertEqual(record["task_tracking"]["counts"]["in_progress"], 1)
        self.assertNotIn("running", record["task_tracking"]["counts"])
        result = run([*cmd, "--phase", "complete"], env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("T01", result.stderr)
        self.assertEqual(json.loads((state / "tracked-lead.json").read_text())["phase"], "implement")
        result = run([sys.executable, str(tasks), "set", "--root", str(self.root), "--file", "docs/tasks/work.md", "--id", "T01", "--status", "done"], env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = run([*cmd, "--phase", "complete"], env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.root / "docs/tasks/work.md").unlink()
        result = run([*cmd, "--phase", "complete"], env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid task list", result.stderr)

    def test_phase_completion_guard_covers_canonical_in_progress_and_activity_metadata(self):
        env = {**self.env, "CODEX_THREAD_ID": "active-lead", "FSA_TASKS_DIR": str(Path(self.scratch.name) / "active-registry")}
        tasks = self.bundle / "scripts/tasks.py"
        result = run([sys.executable, str(tasks), "init", "--root", str(self.root), "--file", "docs/tasks/active.md", "--task", "T1|in_progress|Implement|"], env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = run([sys.executable, str(tasks), "set", "--root", str(self.root), "--file", "docs/tasks/active.md", "--id", "T1", "--status", "in_progress", "--owner", "lead", "--activity", "Run tests", "--active-for", "120"], env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        state = Path(self.scratch.name) / "active-phase"
        command = [sys.executable, str(self.bundle / "scripts/phase.py"), "--root", str(self.root), "--state-dir", str(state)]
        result = run([*command, "--phase", "implement"], env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((state / "active-lead.json").read_text())
        self.assertEqual(record["task_tracking"]["counts"]["in_progress"], 1)
        result = run([*command, "--phase", "complete"], env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unfinished", result.stderr)
        self.assertEqual(json.loads((state / "active-lead.json").read_text())["phase"], "implement")
        result = run([sys.executable, str(tasks), "set", "--root", str(self.root), "--file", "docs/tasks/active.md", "--id", "T1", "--status", "done"], env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = run([*command, "--phase", "complete"], env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((state / "active-lead.json").read_text())
        self.assertEqual((record["phase"], record["task_tracking"]["completed"]), ("complete", 1))

    def test_phase_cli_preserves_evidence_and_clears_it_for_new_task(self):
        state = Path(self.scratch.name) / "evidence-state"
        env = {**self.env, "FSA_CLAUDE_AUDIT_MODEL": "sonnet"}
        command = [sys.executable, str(self.bundle / "scripts/phase.py"),
                   "--root", str(self.root), "--session", "lead", "--state-dir", str(state)]
        def report(phase, *extra):
            result = run([*command, "--phase", phase, *extra], env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads((state / "lead.json").read_text())
        record = report("validate", "--check", "unit checks passed", "--check", "diff clean",
                        "--summary", "Finished", "--auditor-model", "custom-auditor")
        self.assertEqual(record["auditor"], "custom-auditor")
        record = report("complete")
        self.assertEqual(record["checks"], ["unit checks passed", "diff clean"])
        self.assertEqual(record["summary"], "Finished")
        self.assertEqual(record["auditor"], "sonnet")
        record = report("validate", "--check", "replacement")
        self.assertEqual(record["checks"], ["replacement"])
        record = report("investigate")
        self.assertEqual((record["checks"], record["summary"]), ([], ""))
        record = report("plan")
        self.assertEqual((record["checks"], record["summary"]), ([], ""))

    def test_phase_cli_rejects_unsafe_session_and_recovers_malformed_history(self):
        state = Path(self.scratch.name) / "flow-state"
        command = [sys.executable, str(self.bundle / "scripts/phase.py"), "--root", str(self.root),
                   "--phase", "plan", "--state-dir", str(state)]
        for session in ("../escape", "", "/absolute"):
            result = run([*command, "--session", session], env=self.env)
            self.assertNotEqual(result.returncode, 0)
        write(state / "lead-session.json", "{broken")
        result = run([*command, "--session", "lead-session"], env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads((state / "lead-session.json").read_text())["history"]), 1)

    def test_audit_changes_returns_issue_and_bounded_repair_brief(self):
        result = self.audit(self.issue())
        self.assertEqual(result.returncode, 3, result.stderr)
        manifest = json.loads(result.stdout)
        self.assertEqual(manifest["repair_scope"], ["app.py"])
        brief = Path(manifest["brief"]).read_text()
        self.assertIn("ALLOWED_PATHS:\n- app.py\n", brief)
        self.assertIn("app.py:1", brief)

    def test_untracked_submitted_file_is_included(self):
        write(self.root / "new.py", "new_value = 3\n")
        result = self.audit(extra=("--files", "new.py"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("+new_value = 3", json.loads(self.call.read_text())["input"])

    def test_invalid_audit_never_passes(self):
        values = [{"structured_output": {"verdict": "PASS", "summary": "bad", "findings": [self.issue()["structured_output"]["findings"][0]]}},
                  self.issue(file="other.py"), self.issue(repair_scope=["../escape.py"]),
                  {"is_error": True}, {"result": "PASS"}]
        for response in values:
            with self.subTest(response=response):
                result = self.audit(response)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertNotIn('"verdict": "PASS"', result.stdout)

    def test_oversized_packet_fails_before_calling_claude(self):
        result = self.audit(extra=("--max-chars", "20"))
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.call.exists())

    def test_outside_path_and_symlink_escape_fail_before_calling_claude(self):
        outside = Path(self.scratch.name) / "outside.py"
        outside.write_text("outside\n")
        (self.root / "linked.py").symlink_to(outside)
        for name in ("../outside.py", "linked.py"):
            result = self.audit(extra=("--files", name))
            self.assertEqual(result.returncode, 2)
            self.assertFalse(self.call.exists())

    def test_cli_failure_is_incomplete(self):
        self.env["FSA_TEST_EXIT"] = "1"
        result = self.audit()
        self.assertEqual(result.returncode, 2)
        self.assertIn("incomplete", result.stderr)

    def test_changed_context_invalidates_audit(self):
        self.env["FSA_TEST_WRITES"] = json.dumps({"other.py": "other = 9\n"})
        result = self.audit(extra=("--context", "other.py:1:1"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("changed during", result.stderr)

    def test_change_during_packet_build_is_rejected_before_model_call(self):
        import handoff
        from types import SimpleNamespace
        from unittest.mock import patch
        original = handoff.packet
        def change_after_read(args, root, files):
            value = original(args, root, files)
            (root / "app.py").write_text("value = 99\n")
            return value
        args = SimpleNamespace(root=self.root, files=["app.py"], plan=self.plan,
                               context=[], previous=None, base="HEAD", max_chars=32000,
                               max_files=8, runs_dir=self.runs, model="sonnet", budget=1, timeout=5)
        with patch.object(handoff, "packet", side_effect=change_after_read):
            with self.assertRaisesRegex(ValueError, "while building"):
                handoff.audit(args)
        self.assertFalse(self.call.exists())

    def worker(self, writes=None, mode="implement", brief_text=None, runs_dir=None):
        self.env["FSA_TEST_RESPONSE"] = json.dumps({"summary": "unit complete", "files": ["app.py"], "tests": [], "open_risks": []})
        self.env["FSA_TEST_WRITES"] = json.dumps(writes or {})
        brief = Path(self.scratch.name) / "brief.md"
        brief.write_text(brief_text or "PLAN: none: lead planned\nALLOWED_PATHS:\n- app.py\n\nSKILLS: fastapi\nTASK: change value\n")
        return run([sys.executable, str(self.bundle / "scripts/worker.py"), mode, str(brief),
                    "--root", str(self.root), "--runs-dir", str(runs_dir or self.runs)], env=self.env)

    def test_run_records_own_worker_and_audit_results(self):
        self.env.pop("FSA_CLAUDE_AUDIT_MODEL", None)
        home = Path(self.env["CODEX_HOME"])
        write(home / "config.toml", 'model = "configured-test-model"\n')
        result = self.worker()
        self.assertEqual(result.returncode, 0, result.stderr)
        directory = home / "fsa-flow/runs/test-lead"
        record = json.loads(next(directory.glob("*.json")).read_text())
        self.assertEqual((record["state"], record["model"], record["child_session_id"]),
                         ("completed", "configured-test-model", "worker-child"))
        self.assertEqual(record["session_id"], "test-lead")
        result = self.audit()
        self.assertEqual(result.returncode, 0, result.stderr)
        auditor = next(json.loads(p.read_text()) for p in directory.glob("*.json")
                       if json.loads(p.read_text())["role"] == "auditor")
        self.assertEqual((auditor["state"], auditor["verdict"], auditor["model"]),
                         ("completed", "PASS", "opus"))
        self.env["FSA_TEST_EXIT"] = "1"
        result = self.audit()
        self.assertNotEqual(result.returncode, 0)
        auditors = [json.loads(p.read_text()) for p in directory.glob("*.json")
                    if json.loads(p.read_text())["role"] == "auditor"]
        failed = max(auditors, key=lambda r: r["started"])
        self.assertEqual((failed["state"], failed["verdict"]), ("incomplete", None))

    def test_worker_tracks_changes_to_already_dirty_file_and_inherits_model(self):
        result = self.worker({"app.py": "value = 3\n"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["touched"], ["app.py"])
        call = json.loads(self.call.read_text())
        self.assertNotIn("--model", call["args"])
        self.assertIn("agents.enabled=false", call["args"])
        self.assertIn("SKILL_FILES:", call["input"])

    def test_worker_flags_out_of_scope_without_reverting(self):
        result = self.worker({"other.py": "other = 9\n", "untracked.py": "value = 0\n"})
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(json.loads(result.stdout)["outside_scope"], ["other.py", "untracked.py"])
        self.assertEqual((self.root / "other.py").read_text(), "other = 9\n")

    def test_worker_flags_ignored_file_mutations(self):
        write(self.root / ".gitignore", ".env\n*.local\n")
        write(self.root / ".env", "EXAMPLE=before\n")
        result = self.worker({".env": "EXAMPLE=after\n", "config.local": "new ignored file\n"})
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(json.loads(result.stdout)["outside_scope"], [".env", "config.local"])

    def test_worker_flags_git_config_edits(self):
        config = self.root / ".git/config"
        result = self.worker({".git/config": config.read_text() + "\n[example]\n value = changed\n"})
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn(".git/config", json.loads(result.stdout)["outside_scope"])

    def test_symlinked_in_repo_run_directory_excludes_own_artifacts(self):
        actual = self.root / "actual-runs"
        actual.mkdir()
        alias = self.root / "linked-runs"
        alias.symlink_to(actual, target_is_directory=True)
        result = self.worker({"app.py": "value = 3\n"}, runs_dir=alias)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(result.stdout)
        self.assertEqual(manifest["touched"], ["app.py"])
        self.assertTrue(Path(manifest["run"]).is_relative_to(actual))
        self.assertTrue(Path(manifest["result"]).is_absolute())

    def test_investigation_uses_read_only_and_flags_any_mutation(self):
        brief = "FILES:\n- app.py\n\nREPORT: value and location\n"
        result = self.worker({"app.py": "value = 4\n"}, mode="investigate", brief_text=brief)
        self.assertEqual(result.returncode, 3, result.stderr)
        call = json.loads(self.call.read_text())
        self.assertEqual(call["args"][call["args"].index("--sandbox") + 1], "read-only")

    def test_worker_rejects_invalid_brief_before_model_call(self):
        result = self.worker(brief_text="PLAN: none: lead planned\nALLOWED_PATHS:\n- ../escape.py\n\n")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.call.exists())

    def test_investigation_requires_report_contract(self):
        result = self.worker(mode="investigate", brief_text="FILES:\n- app.py\n\nTASK: scan\n")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.call.exists())

    def test_empty_headers_cannot_borrow_the_next_line(self):
        for mode, brief in (("implement", "PLAN:\nALLOWED_PATHS:\n- app.py\n\nTASK: change\n"),
                            ("investigate", "FILES:\n- app.py\n\nREPORT:\nTASK: investigate\n"),
                            ("investigate", "FILES:\nREPORT: values\n"),
                            ("implement", "PLAN: none: lead\nALLOWED_PATHS:\n\nTASK: change\n")):
            with self.subTest(mode=mode, brief=brief):
                result = self.worker(mode=mode, brief_text=brief)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(self.call.exists())


class HookAndValidationTests(unittest.TestCase):
    def test_prompt_hook_skips_notifications_and_short_commands(self):
        for prompt in ("commit and push", "yes", "", "<task-notification> background task completed successfully </task-notification>",
                       "SYSTEM NOTIFICATION - NOT USER INPUT: background task completed"):
            with self.subTest(prompt=prompt):
                result = run([sys.executable, str(SCRIPTS / "hook.py"), "prompt"],
                             input=json.dumps({"prompt": prompt}))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")

    def test_prompt_hook_keeps_guidance_for_substantive_requests(self):
        result = run([sys.executable, str(SCRIPTS / "hook.py"), "prompt"],
                     input=json.dumps({"prompt": "Please investigate the slow backend request and fix it"}))
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "UserPromptSubmit")
        self.assertIn("Codex leads", output["additionalContext"])

    def test_hook_understands_patch_moves_and_does_not_fetch_missing_tool(self):
        with tempfile.TemporaryDirectory(prefix="fsa-hook-") as scratch:
            root = Path(scratch)
            write(root / "app.py", "value = 2\n")
            write(root / "src/main.rs", "fn main() {}\n")
            patch = "*** Begin Patch\n*** Update File: app.py\n*** Move to: other.py\n*** Update File: src/main.rs\n*** End Patch\n"
            payload = {"cwd": str(root), "tool_input": {"command": patch}}
            result = run([sys.executable, str(SCRIPTS / "hook.py"), "post"], input=json.dumps(payload),
                         env={**os.environ, "PATH": str(root)})
            self.assertEqual(result.returncode, 0, result.stderr)
            context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("unavailable", context)
            self.assertEqual((root / "app.py").read_text(), "value = 2\n")

    def test_frontend_validation_does_not_download_typescript(self):
        with tempfile.TemporaryDirectory(prefix="fsa-validation-") as scratch:
            result = run(["bash", str(SCRIPTS / "validate.sh"), "frontend", scratch])
            self.assertEqual(result.returncode, 2)
            self.assertIn("missing local TypeScript", result.stderr)


if __name__ == "__main__":
    unittest.main()
