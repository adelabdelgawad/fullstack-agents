"""Behavior of the Information renderer using projected dashboard fixtures."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

HTML = Path(__file__).resolve().parents[2] / "plugins/fullstack-agents/scripts/lib/dashboard.html"


@unittest.skipUnless(shutil.which("node"), "node unavailable: renderer tests require Node.js")
class InformationUiTests(unittest.TestCase):
    def render(self, card, opened=()):
        source = HTML.read_text()
        renderer = re.search(r"const infoOpen = new Map\(\);[\s\S]*?(?=\nasync function pollLog)", source).group()
        helpers = r'''
const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const STATE_TEXT = {idle: 'just finished a turn', waiting: 'waiting on you'};
const FLAG_TEXT = {};
const COPY_ICON = 'copy';
const state = {session_panes: {lead: 'pane-1'}};
const openRun = null;
const LIVE = r => r.state === 'running';
const stateChip = r => esc(r.state);
const dur = () => '2s';
const ago = () => '1m';
const detailHtml = () => '';
const lastPara = t => t.trim().split(/\n\s*\n/).pop();
const saidHtml = s => '<pre>' + esc(s.said_full || s.said) + '</pre>';
const resumeHtml = s => '<div>' + esc(s.id) + ' codex resume ' + esc(s.id) + '</div>';
const stepsHtml = c => c.steps.map(s => esc(s.text)).join('');
'''
        script = "const vm = require('vm'); const ctx = vm.createContext({});\n"
        script += "vm.runInContext(" + json.dumps(helpers + renderer) + ", ctx);\n"
        script += "vm.runInContext(" + json.dumps("infoOpen.set('card', new Set(" + json.dumps(list(opened)) + "));") + ", ctx);\n"
        script += "process.stdout.write(vm.runInContext(" + json.dumps("infoHtml(" + json.dumps(card) + ")") + ", ctx));"
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        return result.stdout

    def fixture(self):
        return {"key": "card", "title": "Implement search", "phase": "review", "runs": [], "steps": [],
                "needs_you": [], "sessions": [{"id": "lead", "name": "Implement search", "engine": "codex",
                "model": "configured-codex", "state": "working", "updated": 1700000100,
                "workflow_phase": "audit", "workflow_history": [{"phase": "implement", "timestamp": 1700000000},
                {"phase": "audit", "timestamp": 1700000100}]}], "now": [{"id": "lead", "engine": "codex",
                "updated": 1700000100, "said_at": 1700000090, "said": "Search now works.",
                "action": "Inspect diff", "action_running": True}], "workflow_runs": []}

    def test_lead_and_real_auditor_are_distinct(self):
        card = self.fixture()
        card["workflow_runs"] = [{"role": "auditor", "engine": "claude", "model": "opus", "state": "completed",
                                  "verdict": "CHANGES", "run_id": "audit-1", "updated": 1700000200, "summary": "Fix escaping"}]
        html = self.render(card)
        self.assertIn('Codex · configured-codex', html)
        self.assertIn('Claude · opus', html)
        self.assertIn('completed · CHANGES', html)
        self.assertIn('<dd>working</dd>', html)
        self.assertNotIn('<dd>done</dd>', html)

    def test_progress_and_neutral_absence_of_runs(self):
        html = self.render(self.fixture())
        self.assertIn('No run records available.', html)
        self.assertNotIn('no code has been handed', html)
        self.assertIn('<dd>audit</dd>', html)
        self.assertRegex(html, r'<b>implement</b> <time>[^<]+</time>')
        self.assertIn('Running now</b> Inspect diff', html)
        self.assertLess(html.index('<h4>Summary'), html.index('<h4>Progress'))
        self.assertLess(html.index('<h4>Progress'), html.index('<h4>Result'))

    def test_disclosures_default_closed_and_restore_per_card(self):
        html = self.render(self.fixture())
        for key in ('session', 'runs', 'message'):
            self.assertIn(f'data-info-section="{key}"><summary>', html)
        restored = self.render(self.fixture(), ['session'])
        self.assertIn('data-info-section="session" open>', restored)
        self.assertIn('data-info-section="runs"><summary>', restored)
        other = self.fixture()
        other['key'] = 'other'
        self.assertNotIn(' open>', self.render(other, ['session']))

    def test_agent_text_and_title_are_escaped(self):
        card = self.fixture()
        card['title'] = '<img src=x onerror=alert(1)>'
        card['now'][0]['said'] = '<script>alert("x")</script>'
        html = self.render(card)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('&lt;img', html)
        self.assertIn('Full message from Codex', html)

    def test_historical_claude_and_recorded_checks(self):
        card = self.fixture()
        card['sessions'][0]['engine'] = 'claude'
        card['sessions'][0]['model'] = None
        card['now'][0]['engine'] = 'claude'
        card['chips'] = [{'kind': 'tests', 'verdict': 'PASS', 'label': 'unit checks'}]
        html = self.render(card)
        self.assertIn('<dd>Claude</dd>', html)
        self.assertIn('Full message from Claude', html)
        self.assertIn('Worker-reported checks</b> PASS · unit checks', html)
        self.assertIn('No registered audit result.', html)
        self.assertNotIn('opus', html)

    def test_lead_evidence_is_escaped_and_preferred(self):
        card = self.fixture()
        card['sessions'][0].update(workflow_checks=['<script>check</script>'],
                                   workflow_summary='<img>Result', workflow_auditor='sonnet')
        card['chips'] = [{'kind': 'tests', 'verdict': 'PASS'}]
        html = self.render(card)
        self.assertIn('Lead-reported checks', html)
        self.assertIn('Worker-reported checks', html)
        self.assertIn('&lt;script&gt;check&lt;/script&gt;', html)
        self.assertIn('&lt;img&gt;Result', html)
        self.assertNotIn('Search now works.', html)
        self.assertIn('sonnet (selected; no audit recorded)', html)
        self.assertNotIn('opus', html)
        self.assertNotIn('configured; no audit', self.render(self.fixture()))
        self.assertIn('No audit recorded', self.render(self.fixture()))

    def test_old_events_are_collapsed_and_disclosure_is_restored(self):
        card = self.fixture()
        card['sessions'][0]['workflow_history'] = [
            {'phase': 'event-' + str(i), 'timestamp': 1700000000 + i} for i in range(12)]
        html = self.render(card)
        self.assertIn('data-info-section="history"><summary>', html)
        self.assertEqual(html.count('<li><b>event-'), 12)
        recent, older = html.split('data-info-section="history"', 1)
        self.assertNotIn('<b>event-0</b>', recent)
        self.assertIn('<b>event-4</b>', recent)
        self.assertIn('<b>event-0</b>', older)
        self.assertIn('data-info-section="history" open>', self.render(card, ['history']))

    def test_blocked_and_incomplete_audit_do_not_claim_pass(self):
        card = self.fixture()
        card['sessions'][0]['state'] = 'waiting'
        card['now'][0]['need'] = 'Choose a search scope'
        card['workflow_runs'] = [{'role': 'auditor', 'engine': 'claude', 'model': 'opus',
                                 'state': 'incomplete', 'run_id': 'a1', 'updated': 1700000200}]
        html = self.render(card)
        self.assertIn('<dd>blocked</dd>', html)
        self.assertIn('incomplete · no verdict recorded', html)
        self.assertIn('Choose a search scope', html)
        self.assertNotIn('PASS', html)


if __name__ == '__main__':
    unittest.main()
