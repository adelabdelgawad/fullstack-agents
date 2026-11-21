"""Office departments come from the teams file, fall back to the defaults, and drop malformed rows."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("fsa_dashboard_office_teams", str(REPO / "plugins/fullstack-agents/scripts/fsa-dashboard"))
dash = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_dashboard_office_teams", _loader))
_loader.exec_module(dash)


class OfficeTeamsTests(unittest.TestCase):
    def test_missing_file_uses_the_default_departments(self):
        with patch.dict(os.environ, {"FSA_TEAMS": "/nonexistent/teams.json"}):
            names = [team["name"] for team in dash.office_teams()]
        self.assertEqual(names[:2], ["CTO", "Testers Team"])
        self.assertIn("VOIP Engineering", names)

    def test_teams_file_wins_and_malformed_rows_are_dropped(self):
        rows = [{"name": "QA", "match": ["Test", " "]}, {"name": "", "match": ["x"]}, {"name": "Bad"}, "junk"]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(rows, handle)
        try:
            with patch.dict(os.environ, {"FSA_TEAMS": handle.name}):
                self.assertEqual(dash.office_teams(), [{"name": "QA", "match": ["test"]}])
        finally:
            os.unlink(handle.name)


if __name__ == "__main__":
    unittest.main()
