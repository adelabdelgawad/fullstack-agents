"""team_conf: the one parser for <repo>/.claude/fsa-team.conf, never evaluated as shell."""
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from dispatch_support import SCRIPTS

sys.path.insert(0, str(SCRIPTS / "lib"))
import team_conf  # noqa: E402


class TeamConfTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        (self.repo / ".claude").mkdir(parents=True)
        self.conf = self.repo / ".claude" / "fsa-team.conf"

    def write(self, text):
        self.conf.write_text(text)

    def test_missing_file_has_no_bindings(self):
        self.assertEqual(team_conf.load(self.repo), {})
        self.assertIsNone(team_conf.get(self.repo, "runs_dir"))

    def test_comments_and_blank_lines_are_ignored(self):
        self.write("# a comment\n\nruns_dir=/x\n   \n# another\n")
        self.assertEqual(team_conf.get(self.repo, "runs_dir"), "/x")

    def test_spaces_in_a_path_are_kept_verbatim(self):
        self.write("runs_dir=/a path/with spaces\n")
        self.assertEqual(team_conf.get(self.repo, "runs_dir"), "/a path/with spaces")

    def test_path_list_splits_on_colon(self):
        self.write("legacy_runs_dirs=/a:/b c:/d\n")
        self.assertEqual(team_conf.get(self.repo, "legacy_runs_dirs"), ["/a", "/b c", "/d"])

    def test_path_list_empty_value_is_empty_list(self):
        self.write("legacy_runs_dirs=\n")
        self.assertEqual(team_conf.get(self.repo, "legacy_runs_dirs"), [])

    def test_tilde_expands_to_home(self, home="/home/unit"):
        with unittest.mock.patch.dict("os.environ", {"HOME": home}):
            self.write("runs_dir=~\ncodex_add_dirs=~/sub:~/other\n")
            self.assertEqual(team_conf.get(self.repo, "runs_dir"), home)
            self.assertEqual(team_conf.get(self.repo, "codex_add_dirs"), [f"{home}/sub", f"{home}/other"])

    def test_invalid_int_raises_conf_error_naming_the_key(self):
        self.write("edit_budget=abc\n")
        with self.assertRaises(team_conf.ConfError) as ctx:
            team_conf.get(self.repo, "edit_budget")
        self.assertEqual(ctx.exception.key, "edit_budget")

    def test_zero_or_negative_int_is_invalid(self):
        self.write("read_range_max=0\n")
        with self.assertRaises(team_conf.ConfError):
            team_conf.get(self.repo, "read_range_max")

    def test_valid_int_is_an_int(self):
        self.write("edit_budget=5\n")
        self.assertEqual(team_conf.get(self.repo, "edit_budget"), 5)

    def test_invalid_onoff_raises(self):
        self.write("scan_gate=maybe\n")
        with self.assertRaises(team_conf.ConfError):
            team_conf.get(self.repo, "scan_gate")

    def test_onoff_values(self):
        self.write("scan_gate=on\n")
        self.assertIs(team_conf.get(self.repo, "scan_gate"), True)
        self.write("scan_gate=off\n")
        self.assertIs(team_conf.get(self.repo, "scan_gate"), False)

    def test_space_separated_lists(self):
        self.write("gated_extensions=.py .ts\ncarve_outs=docs/ tests/\n")
        self.assertEqual(team_conf.get(self.repo, "gated_extensions"), [".py", ".ts"])
        self.assertEqual(team_conf.get(self.repo, "carve_outs"), ["docs/", "tests/"])

    def test_policy_profile_must_be_a_slug(self):
        self.write("policy_profile=Engineering_Conventions\n")
        with self.assertRaises(team_conf.ConfError):
            team_conf.get(self.repo, "policy_profile")
        self.write("policy_profile=engineering-conventions\n")
        self.assertEqual(team_conf.get(self.repo, "policy_profile"), "engineering-conventions")

    def test_nonempty_string_keys_reject_empty_value(self):
        self.write("monitor_model=\n")
        with self.assertRaises(team_conf.ConfError):
            team_conf.get(self.repo, "monitor_model")
        self.write("deploy_regex=^deploy\n")
        self.assertEqual(team_conf.get(self.repo, "deploy_regex"), "^deploy")

    def test_unknown_key_warns_once_but_is_not_fatal(self):
        self.write("made_up_key=1\nruns_dir=/x\n")
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPTS / "lib/team_conf.py"), "get", str(self.repo), "runs_dir"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "/x")
        self.assertEqual(result.stderr.count("made_up_key"), 1)

    def test_last_occurrence_wins(self):
        self.write("runs_dir=/first\nruns_dir=/second\n")
        self.assertEqual(team_conf.get(self.repo, "runs_dir"), "/second")

    def test_cli_get_absent_key_prints_nothing_and_exits_zero(self):
        self.write("runs_dir=/x\n")
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPTS / "lib/team_conf.py"), "get", str(self.repo), "edit_budget"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_cli_get_list_prints_one_item_per_line(self):
        self.write("legacy_runs_dirs=/a:/b\n")
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPTS / "lib/team_conf.py"), "get", str(self.repo), "legacy_runs_dirs"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), ["/a", "/b"])

    def test_cli_get_invalid_value_exits_3_naming_the_key(self):
        self.write("edit_budget=abc\n")
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPTS / "lib/team_conf.py"), "get", str(self.repo), "edit_budget"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stderr.strip(), "invalid fsa-team.conf: edit_budget: must be a positive integer")

    def test_cli_check_reports_all_problems_and_exits_3(self):
        self.write("edit_budget=abc\nscan_gate=maybe\nruns_dir=/x\n")
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPTS / "lib/team_conf.py"), "check", str(self.repo)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 3)
        self.assertIn("edit_budget", result.stdout)
        self.assertIn("scan_gate", result.stdout)

    def test_cli_check_exits_zero_when_all_valid(self):
        self.write("runs_dir=/x\nedit_budget=5\n")
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPTS / "lib/team_conf.py"), "check", str(self.repo)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
