"""web-researcher: registered, web-only tools (its scan-gate exemption depends on this), no repository access."""
import json
import re
import unittest

from dispatch_support import SCRIPTS

PLUGIN = SCRIPTS.parent
AGENT = PLUGIN / "agents/lead/web-researcher.md"


class WebResearcherTests(unittest.TestCase):
    def frontmatter(self):
        block = AGENT.read_text().split("---", 2)[1]
        return dict(re.findall(r"^([a-z_-]+):\s*(.+)$", block, re.M))

    def test_registered_in_the_plugin_manifest(self):
        manifest = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())
        self.assertIn("./agents/lead/web-researcher.md", manifest["agents"])

    def test_tools_are_web_only(self):
        tools = {t.strip() for t in self.frontmatter()["tools"].split(",")}
        self.assertEqual(tools, {"WebSearch", "WebFetch"})

    def test_repository_needs_are_handed_back(self):
        self.assertIn("NEEDS_REPO:", AGENT.read_text())

    def test_lead_routing_names_it(self):
        self.assertIn("fullstack-agents:web-researcher", (PLUGIN / "agents/lead/fullstack-agent.md").read_text())


if __name__ == "__main__":
    unittest.main()
