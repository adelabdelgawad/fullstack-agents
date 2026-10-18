"""generated_globs: untracked generated output is excluded from scope reporting only; source changes always surface."""
import subprocess
import unittest

from dispatch_support import DispatchCase, write


class GeneratedGlobTests(unittest.TestCase):
    def setUp(self):
        self.case = DispatchCase("codex")
        self.addCleanup(self.case.cleanup)
        self.cache = [f".agent-cargo-cache/backend/debug/deps/d{i}.d" for i in range(500)]

    def dispatch(self, touched):
        return self.case.dispatch(env={"FSA_FAKE_MODE": "touch", "FSA_FAKE_TOUCH": ":".join(touched)})

    def test_without_a_binding_generated_output_is_out_of_scope_as_before(self):
        result = self.dispatch(["app.py", *self.cache[:3]])
        self.assertIn("STATUS=OUT_OF_SCOPE", result.stdout)
        self.assertIn(".agent-cargo-cache/backend/debug/deps/d0.d", result.stdout)

    def test_generated_output_is_reported_separately_and_source_still_surfaces(self):
        self.case.binding(generated_globs=".agent-cargo-cache/*")
        result = self.dispatch(["app.py", "src/stray.rs", *self.cache])
        self.assertIn("STATUS=OUT_OF_SCOPE", result.stdout)
        self.assertIn("src/stray.rs", result.stdout)
        self.assertNotIn(".agent-cargo-cache/", result.stdout.split("GENERATED:")[0])
        self.assertIn("GENERATED: 0 -> 500 untracked paths", result.stdout)

    def test_generated_only_run_is_in_scope(self):
        self.case.binding(generated_globs=".agent-cargo-cache/*")
        result = self.dispatch(["app.py", *self.cache])
        self.assertNotIn("STATUS=OUT_OF_SCOPE", result.stdout, result.stdout)

    def test_a_tracked_file_under_a_generated_glob_is_still_scope_checked(self):
        write(self.case.root / ".agent-cargo-cache/tracked.rs", "fn main() {}\n")
        git = ["git", "-C", str(self.case.root), "-c", "user.email=t@example.invalid", "-c", "user.name=T"]
        subprocess.run([*git, "add", ".agent-cargo-cache/tracked.rs"], check=True)
        subprocess.run([*git, "commit", "-qm", "tracked"], check=True)
        self.case.binding(generated_globs=".agent-cargo-cache/*")
        result = self.dispatch(["app.py", ".agent-cargo-cache/tracked.rs"])
        self.assertIn("STATUS=OUT_OF_SCOPE", result.stdout)
        self.assertIn(".agent-cargo-cache/tracked.rs", result.stdout)


if __name__ == "__main__":
    unittest.main()
