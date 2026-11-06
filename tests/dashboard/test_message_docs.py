"""Existing .log, .sql, .text, .txt and .md files named in an agent message are listed for copying."""
import importlib.util
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("fsa_dashboard_docs", str(REPO / "plugins/fullstack-agents/scripts/fsa-dashboard"))
dash = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_dashboard_docs", _loader))
_loader.exec_module(dash)


class MessageDocsTests(unittest.TestCase):
    def test_lists_existing_text_files_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("notes.md", "run.log", "out.txt", "q.sql", "n.text", "a.tar.gz", "app.js"):
                (root / name).write_text("x")
            text = (f"See notes.md, {root}/run.log and `out.txt`; q.sql, n.text, a.tar.gz, app.js. "
                    "Release 3.81.1, missing.log, https://example.com/run.log.")
            names = [d["name"] for d in dash.message_docs(text, str(root))]
        self.assertEqual(names, ["notes.md", "run.log", "out.txt", "q.sql", "n.text"])


if __name__ == "__main__":
    unittest.main()
