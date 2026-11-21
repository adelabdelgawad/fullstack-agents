"""Slash command discovery for the dashboard chat box: built-ins, user, project and enabled plugin commands/skills."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "plugins/fullstack-agents/scripts/lib"))
import slash_commands


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class SlashCommandTests(unittest.TestCase):
    def test_discovers_every_source_with_descriptions_and_skips_disabled_plugins(self):
        with tempfile.TemporaryDirectory() as scratch:
            home, project = Path(scratch) / "home", Path(scratch) / "project"
            write(home / "commands/git/pr.md", "---\ndescription: Open a PR\n---\nbody")
            write(home / "skills/notes/SKILL.md", "---\nname: notes\ndescription: Keep notes\n---\n")
            write(project / ".claude/commands/deploy.md", "---\ndescription: Deploy the app\n---\n")
            on, off = Path(scratch) / "plugin-on", Path(scratch) / "plugin-off"
            write(on / "skills/debug/SKILL.md", "---\nname: debug\ndescription: Find the root cause\n---\n")
            write(on / "commands/dashboard.md", "---\ndescription: Open the dashboard\n---\n")
            write(off / "skills/hidden/SKILL.md", "---\nname: hidden\n---\n")
            write(home / "plugins/installed_plugins.json", json.dumps({"plugins": {
                "tools@market": [{"installPath": str(on)}], "other@market": [{"installPath": str(off)}]}}))
            write(home / "settings.json", json.dumps({"enabledPlugins": {"tools@market": True, "other@market": False}}))
            found = {item["name"]: item["description"] for item in slash_commands.discover(str(project), home)}
        self.assertEqual(found["git:pr"], "Open a PR")
        self.assertEqual(found["notes"], "Keep notes")
        self.assertEqual(found["deploy"], "Deploy the app")
        self.assertEqual(found["tools:debug"], "Find the root cause")
        self.assertEqual(found["tools:dashboard"], "Open the dashboard")
        self.assertIn("compact", found)
        self.assertNotIn("other:hidden", found)


if __name__ == "__main__":
    unittest.main()
