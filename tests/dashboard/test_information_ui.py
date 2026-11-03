"""Session-state behavior projected into dashboard cards."""
import importlib.util
import time
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("fsa_dashboard", str(REPO / "plugins/fullstack-agents/scripts/fsa-dashboard"))
dash = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_dashboard", _loader))
_loader.exec_module(dash)


class SessionStateDashboardTests(unittest.TestCase):
    """U5 DO 1/2: ledger-derived waiting text and ledger-aware phase (docs/TASK_LIFECYCLE_DESIGN.md §13.4)."""

    def test_need_text_from_two_user_questions(self):
        state = {"state": "waiting_user", "executable": [], "workers": [], "external": [], "questions": [
            {"id": "Q1", "text": "Use REST or GraphQL?", "why": "blocks the client work", "rows": ["S3", "S4"]},
            {"id": "Q2", "text": "Which auth provider?", "why": "blocks login", "rows": ["S5"]}]}
        self.assertEqual(dash.session_state_need(state),
                          "Q1: Use REST or GraphQL? — blocks S3, S4: blocks the client work; "
                          "Q2: Which auth provider? — blocks S5: blocks login")

    def test_need_text_for_capacity_wait(self):
        state = {"state": "waiting_external", "executable": [], "workers": [], "questions": [], "external": [
            {"id": "B1", "class": "capacity", "engine": "codex", "until": "2026-10-21T18:00:00Z",
             "text": "", "rows": ["S4"]}]}
        self.assertEqual(dash.session_state_need(state), "waiting for codex capacity until 2026-10-21T18:00:00Z")

    def test_need_is_empty_without_a_ledger_or_without_a_waiting_state(self):
        self.assertEqual(dash.session_state_need(None), "")
        self.assertEqual(dash.session_state_need({"state": "executable", "executable": ["S1"], "questions": [],
                                                   "workers": [], "external": []}), "")

    def test_declared_complete_with_open_v2_ledger_shows_review(self):
        now = time.time()
        card = {"declared": {"phase": "complete", "at": now}}
        session = {"id": "s-claude", "state": "idle", "turn_at": now - 60, "task_tracking": {"file": "/r/t.md",
                   "session_state": {"state": "waiting_user", "executable": [], "workers": [], "external": [],
                                      "questions": [{"id": "Q1", "text": "t", "why": "w", "rows": ["S1"]}]}}}
        self.assertEqual(dash.phase_of(card, [], [session]), "review")
        self.assertEqual(card["declared"]["note"], "ledger has open work")

    def test_declared_complete_with_open_legacy_ledger_shows_review(self):
        now = time.time()
        card = {"declared": {"phase": "complete", "at": now}}
        session = {"id": "s-claude", "state": "idle", "turn_at": now - 60,
                   "task_tracking": {"file": "/r/t.md", "total": 3, "completed": 1,
                                      "counts": {"pending": 2, "in_progress": 0, "blocked": 0, "done": 1,
                                                 "skipped": 0, "canceled": 0}}}
        self.assertEqual(dash.phase_of(card, [], [session]), "review")
        self.assertEqual(card["declared"]["note"], "ledger has open work")

    def test_declared_complete_with_done_and_canceled_legacy_ledger_stays_complete(self):
        now = time.time()
        card = {"declared": {"phase": "complete", "at": now}}
        session = {"id": "s-claude", "state": "idle", "turn_at": now - 60,
                   "task_tracking": {"file": "/r/t.md", "total": 2, "completed": 1,
                                      "counts": {"pending": 0, "in_progress": 0, "blocked": 0, "done": 1,
                                                 "skipped": 0, "canceled": 1}}}
        self.assertEqual(dash.phase_of(card, [], [session]), "complete")
        self.assertNotIn("note", card["declared"])

    def test_declared_complete_with_done_ledger_stays_complete(self):
        now = time.time()
        card = {"declared": {"phase": "complete", "at": now}}
        session = {"id": "s-claude", "state": "idle", "turn_at": now - 60, "task_tracking": {"file": "/r/t.md",
                   "session_state": {"state": "done", "executable": [], "questions": [], "workers": [],
                                      "external": []}}}
        self.assertEqual(dash.phase_of(card, [], [session]), "complete")
        self.assertNotIn("note", card["declared"])

    def test_declared_dict_from_board_phases_is_not_mutated(self):
        now = time.time()
        declared = {"phase": "complete", "at": now}
        card = {"declared": declared}
        session = {"id": "s-claude", "state": "idle", "turn_at": now - 60, "task_tracking": {"file": "/r/t.md",
                   "session_state": {"state": "waiting_user", "executable": [], "workers": [], "external": [],
                                      "questions": [{"id": "Q1", "text": "t", "why": "w", "rows": ["S1"]}]}}}
        self.assertEqual(dash.phase_of(card, [], [session]), "review")
        self.assertNotIn("note", declared)
        self.assertIsNot(card["declared"], declared)

    def test_working_session_with_waiting_user_ledger_stays_working(self):
        session = {"id": "s-claude", "state": "working", "need": "", "task_tracking": {"file": "/r/t.md",
                   "session_state": {"state": "waiting_user", "executable": [], "workers": [], "external": [],
                                      "questions": [{"id": "Q1", "text": "Use REST or GraphQL?", "why": "w",
                                                     "rows": ["S1"]}]}}}
        dash.apply_session_state_need(session)
        self.assertEqual(session["state"], "working")
        self.assertEqual(session["need"], "")

    def test_idle_session_with_waiting_user_ledger_becomes_waiting(self):
        session = {"id": "s-claude", "state": "idle", "need": "", "task_tracking": {"file": "/r/t.md",
                   "session_state": {"state": "waiting_user", "executable": [], "workers": [], "external": [],
                                      "questions": [{"id": "Q1", "text": "Use REST or GraphQL?", "why": "w",
                                                     "rows": ["S1"]}]}}}
        dash.apply_session_state_need(session)
        self.assertEqual(session["state"], "waiting")
        self.assertIn("Use REST or GraphQL?", session["need"])


if __name__ == '__main__':
    unittest.main()
