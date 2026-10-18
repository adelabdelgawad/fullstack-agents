"""P7: skill descriptions stay within the listing budget the plugin claims, and every skill keeps a trigger."""
import re
import unittest

from dispatch_support import SCRIPTS

PLUGIN = SCRIPTS.parent
TOTAL_MAX = 6000      # all descriptions together (Claude Code's listing budget is 1% of context, 8,000-char fallback)
EACH_MAX = 250


def descriptions():
    out = {}
    for path in sorted((PLUGIN / "skills").glob("*/SKILL.md")):
        front = path.read_text().split("---", 2)[1]
        m = re.search(r"^description:\s*(.*?)(?=^\S[\w-]*:|\Z)", front, re.S | re.M)
        out[path.parent.name] = " ".join(m.group(1).split()) if m else ""
    return out


class SkillListingTests(unittest.TestCase):
    def test_total_and_per_skill_size(self):
        found = descriptions()
        self.assertGreaterEqual(len(found), 31)
        self.assertLess(sum(map(len, found.values())), TOTAL_MAX)
        for name, text in found.items():
            with self.subTest(skill=name):
                self.assertTrue(40 <= len(text) <= EACH_MAX, len(text))

    def test_python_skills_remain_discoverable(self):
        found = descriptions()
        for name in ("fastapi", "python-clean-architecture", "celery", "tasks-management", "websocket"):
            with self.subTest(skill=name):
                self.assertRegex(found[name], r"Python|FastAPI")

    def test_descriptions_parse_as_plain_yaml_scalars(self):
        for name, text in descriptions().items():
            with self.subTest(skill=name):
                self.assertNotIn(": ", text)
                self.assertNotIn(" #", text)


if __name__ == "__main__":
    unittest.main()
