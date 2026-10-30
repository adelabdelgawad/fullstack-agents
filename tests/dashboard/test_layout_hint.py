import json
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "plugins/fullstack-agents"
sys.path.insert(0, str(PLUGIN / "scripts/lib"))

import layout_hint


class LayoutHintTests(unittest.TestCase):
    def test_arabic_layout_slash_commands_decode(self):
        self.assertEqual(layout_hint.decode("ظؤخحغ"), "/copy")
        self.assertEqual(layout_hint.decode("ظؤمثشق"), "/clear")
        self.assertEqual(layout_hint.decode("ظقثمخشي-حمعلهىس"), "/reload-plugins")

    def test_real_arabic_and_layout_words_pass_through(self):
        for prompt in ("مساء النور ايوه اه اهلا بيكِ", "ثواني", "ؤخىفهىعث", "/copy", "check the calls"):
            self.assertIsNone(layout_hint.decode(prompt), prompt)

    def test_hook_blocks_with_the_meant_command(self):
        def run(prompt):
            return subprocess.run(["bash", str(PLUGIN / "hooks/layout-hint")], input=json.dumps({"prompt": prompt}),
                                  capture_output=True, text=True, timeout=10, check=False).stdout
        out = json.loads(run("ظؤخحغ"))
        self.assertEqual(out["decision"], "block")
        self.assertIn("/copy", out["reason"])
        self.assertEqual(run("مساء النور"), "")


if __name__ == "__main__":
    unittest.main()
