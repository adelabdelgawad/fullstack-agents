"""Behavior of the Information renderer using projected dashboard fixtures."""
import importlib.util
import json
import re
import shutil
import subprocess
import time
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

HTML = Path(__file__).resolve().parents[2] / "plugins/fullstack-agents/scripts/lib/dashboard.html"
REPO = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("fsa_dashboard", str(REPO / "plugins/fullstack-agents/scripts/fsa-dashboard"))
dash = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_dashboard", _loader))
_loader.exec_module(dash)


@unittest.skipUnless(shutil.which("node"), "node unavailable: renderer tests require Node.js")
class InformationUiTests(unittest.TestCase):
    def render(self, card, opened=(), pre=""):
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
const AGENT_NAMES = {shell: 'bg shell'};
const toolLine = s => s.action || '';
const workersSection = () => '';
const activitySection = () => '';
const fmtCost = c => c == null ? '—' : '$' + c.toFixed(2);
const fmtTokens = n => String(n || 0);
'''
        script = "const vm = require('vm'); const ctx = vm.createContext({});\n"
        script += "vm.runInContext(" + json.dumps(helpers + renderer) + ", ctx);\n"
        script += "vm.runInContext(" + json.dumps("infoOpen.set('card', new Map(" + json.dumps([[k, v] for k, v in (opened.items() if isinstance(opened, dict) else ((k, True) for k in opened))]) + "));") + ", ctx);\n"
        script += "vm.runInContext(" + json.dumps(pre) + ", ctx);\n"
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

    def test_registered_task_list_shows_counts_source_and_live_statuses(self):
        card = self.fixture()
        card["sessions"][0]["task_tracking"] = {"title": "Canvas work", "file": "/repo/docs/tasks/canvas.md", "relative_file": "docs/tasks/canvas.md", "total": 3, "completed": 1, "counts": {"done": 1, "running": 1, "pending": 1}, "items": [{"id": "T01", "status": "done", "title": "Reference", "note": "Verified pin"}, {"id": "T02", "status": "running", "title": "Canvas", "note": "Browser pending"}, {"id": "T03", "status": "pending", "title": "Engine", "note": ""}]}
        html = self.render(card)
        self.assertIn('data-info-section="task-list"><summary><h4>Tasks</h4><span class="chip">1/3 done</span>', html)
        self.assertIn('data-info-section="task-list" open', self.render(card, ['task-list']))
        tasks = html[html.index('data-info-section="task-list"'):]
        self.assertNotIn('session-task-overview', tasks)
        self.assertIn('session-task-overview', html[:html.index('data-info-section="task-list"')])
        self.assertLess(html.index('data-info-section="runs"'), html.index('data-info-section="task-list"'))
        self.assertIn('1/3 done', html)
        self.assertIn('1/3 tasks done', html)
        self.assertIn('aria-label="Task stage timeline"', html)
        self.assertLess(html.index('session-task-overview'), html.index('<h4>Summary'))
        self.assertIn('T02: Canvas — In progress', html)
        self.assertIn('0 actively executing · 1 in progress', html)
        self.assertIn('aria-label="In progress"', html)
        self.assertIn('aria-label="Pending"', html)
        self.assertIn('Browser pending', html)
        self.assertLess(html.index('<b>T02</b>'), html.index('<b>T03</b>'))
        self.assertLess(html.index('<b>T03</b>'), html.index('<b>T01</b>'))
        self.assertLess(html.index('<h4>Result'), html.index('<h4>Tasks'))
        self.assertIn('tabindex="0" aria-label="Tasks; scroll for more"', html)
        self.assertIn('/api/doc?sid=lead&amp;path=', html)
        card["sessions"][0]["task_tracking"]["items"][1]["status"] = "done"
        self.assertRegex(self.render(card), r'task-status-icon done[^>]*role="img"[^>]*aria-label="Done"')

    def test_task_icons_owners_activity_and_expiring_execution_are_separate(self):
        card = self.fixture()
        card["sessions"][0]["task_tracking"] = {"title": "Tasks", "file": "/repo/TASKS.md", "relative_file": "TASKS.md", "total": 3, "completed": 1, "counts": {"done": 1, "in_progress": 2}, "items": [
            {"id": "T1", "status": "in_progress", "title": "Waiting review", "owner": "lead", "activity": "Awaiting audit", "is_active": False},
            {"id": "T2", "status": "in_progress", "title": "Live implementation", "owner": "agent:<worker>", "activity": "Fix <script>draft</script>", "is_active": True, "active_until": "2030-01-01T00:00:00Z"},
            {"id": "T3", "status": "done", "title": "Complete"}]}
        html = self.render(card, pre="Date.now = () => Date.parse('2026-01-01T00:00:00Z');")
        self.assertIn('1 actively executing · 2 in progress', html)
        self.assertIn('aria-label="In progress — actively executing (agent-reported)"', html)
        self.assertLess(html.index('<b>T2</b>'), html.index('<b>T1</b>'))
        self.assertIn('agent:&lt;worker&gt;', html)
        self.assertIn('Fix &lt;script&gt;draft&lt;/script&gt;', html)
        self.assertNotIn('<script>draft</script>', html)
        self.assertNotRegex(html, r'>in_progress</span>|>done</span>|>pending</span>')
        expired = self.render(card, pre="Date.now = () => Date.parse('2031-01-01T00:00:00Z');")
        self.assertIn('0 actively executing · 2 in progress', expired)
        self.assertNotIn('actively executing (agent-reported)', expired)

    def test_task_rows_show_id_title_status_badge_and_status_tiles(self):
        card = self.fixture()
        card["sessions"][0]["task_tracking"] = {"title": "Plan", "file": "/r/t.md", "relative_file": "t.md", "total": 2, "completed": 0, "counts": {"blocked": 1, "pending": 1}, "items": [
            {"id": "T1", "status": "pending", "title": "Later"}, {"id": "T2", "status": "blocked", "title": "Stuck", "owner": "lead"}]}
        html = self.render(card)
        self.assertIn('<li class="tracked-task blocked"', html)
        self.assertIn('<b>T2</b><span class="tt-title">Stuck</span>', html)
        self.assertIn('<span class="tt-badge blocked">Blocked</span>', html)
        self.assertRegex(html, r'tt-tile blocked[\s\S]*?Blocked</div><div class="tt-n">1</div>')
        self.assertRegex(html, r'tt-tile done[\s\S]*?<div class="tt-n">0</div>')
        self.assertNotIn('tt-tile skipped', html)
        self.assertIn('0/2 done</b><span>0%</span>', html)

    def test_v2_progress_verifying_and_step_parent(self):
        card = self.fixture()
        card["sessions"][0]["task_tracking"] = {"format": "v2", "title": "Plan", "file": "/r/t.md",
            "relative_file": "t.md", "total": 2, "completed": 1,
            "deliverables": {"total": 2, "completed": 1}, "steps": {"total": 1, "completed": 0},
            "counts": {"done": 1, "verifying": 1, "pending": 1}, "items": [
                {"id": "T1", "status": "done", "title": "Feature"},
                {"id": "S1", "status": "verifying", "title": "Review", "parent": "T1"},
                {"id": "T2", "status": "pending", "title": "Later"}]}
        html = self.render(card)
        self.assertIn("1/2 deliverables done · steps 0/1", html)
        self.assertIn('aria-label="Verifying"', html)
        self.assertRegex(html, r'tt-tile verifying[\s\S]*?Verifying</div><div class="tt-n">1</div>')
        self.assertIn('Review <span class="s">(step of T1)</span>', html)
        self.assertIn('<span class="chip">1/2 done</span>', html)

    def test_v2_done_deliverable_shows_completion_badges_and_unrecorded_count(self):
        card = self.fixture()
        card["sessions"][0]["task_tracking"] = {"format": "v2", "title": "Plan", "file": "/r/t.md",
            "relative_file": "t.md", "total": 3, "completed": 3,
            "deliverables": {"total": 3, "completed": 3, "completion": {"evidence": 1, "evidence_with_baseline": 1, "unrecorded": 1}},
            "steps": {"total": 0, "completed": 0},
            "counts": {"done": 3}, "items": [
                {"id": "T1", "status": "done", "title": "Clean", "completion": "evidence"},
                {"id": "T2", "status": "done", "title": "Flaky", "completion": "evidence_with_baseline"},
                {"id": "T3", "status": "done", "title": "Old", "completion": "unrecorded"}]}
        html = self.render(card)
        self.assertIn('<span class="tt-badge baseline" title="Completed using an attributed baseline failure">baseline failures</span>', html)
        self.assertIn('<span class="tt-badge unrecorded" title="Marked done before evidence tracking, or upgraded from a legacy ledger">no recorded evidence</span>', html)
        t1 = html[html.index('<b>T1</b>'):html.index('<b>T2</b>')]
        self.assertNotIn('tt-badge baseline', t1)
        self.assertNotIn('tt-badge unrecorded', t1)
        self.assertIn('3/3 deliverables done · 1 without evidence', html)

    def test_legacy_done_items_never_show_completion_badges_or_suffix(self):
        card = self.fixture()
        card["sessions"][0]["task_tracking"] = {"title": "Canvas work", "file": "/repo/docs/tasks/canvas.md",
            "relative_file": "docs/tasks/canvas.md", "total": 1, "completed": 1, "counts": {"done": 1},
            "items": [{"id": "T01", "status": "done", "title": "Reference", "note": "Verified pin"}]}
        html = self.render(card)
        self.assertNotIn('tt-badge unrecorded', html)
        self.assertNotIn('tt-badge baseline', html)
        self.assertNotIn('without evidence', html)
        self.assertIn('1/1 tasks done', html)

    def test_task_list_escapes_untrusted_content_and_reports_bound_errors(self):
        card = self.fixture()
        card["sessions"][0]["task_tracking"] = {"error": "Missing <script>alert(1)</script>"}
        html = self.render(card)
        self.assertIn('role="alert"', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertNotIn('0/0 done', html)

    def test_unregistered_session_does_not_show_fabricated_task_progress(self):
        self.assertNotIn('data-info-section="task-list"', self.render(self.fixture()))

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
        self.assertIn('data-info-section="session"><summary>', self.render(other, ['session']))

    def test_top_sections_default_closed_live_open_and_restore_per_card(self):
        html = self.render(self.fixture())
        self.assertIn('data-info-section="live" open><summary><h4>Running now', html)
        for key in ('summary', 'progress', 'result'):
            self.assertIn(f'data-info-section="{key}"><summary><h4>', html)
        restored = self.render(self.fixture(), {'result': True, 'live': False})
        self.assertIn('data-info-section="result" open><summary><h4>Result', restored)
        self.assertIn('data-info-section="live"><summary><h4>Running now', restored)
        self.assertIn('data-info-section="summary"><summary>', restored)

    def test_overview_strip_leads_with_state_counts_and_needs(self):
        card = self.fixture()
        card["needs_you"] = ["stalled", "stalled"]
        card["runs"] = [{"id": "implement-1", "unit": "p1", "state": "running"}]
        card["sessions"][0]["task_tracking"] = {"title": "T", "file": "/r/t.md", "relative_file": "t.md", "total": 4, "completed": 1, "counts": {"done": 1}, "items": []}
        html = self.render(card)
        strip = html[html.index('class="session-overview"'):html.index('data-info-section="live"')]
        self.assertIn('<span class="pill live">working</span>', strip)
        self.assertIn('<span class="pill bad">1 needs you</span>', strip)
        self.assertIn('Tasks done</div><div class="so-v">1/4</div>', strip)
        self.assertIn('Running now</div><div class="so-v">1</div>', strip)
        self.assertIn('style="width:25%"', strip)
        self.assertLess(html.index('session-overview'), html.index('session-task-overview'))
        self.assertLess(html.index('session-task-overview'), html.index('data-info-section="live"'))
        self.assertLess(html.index('session-task-overview'), html.index('data-info-section="summary"'))
        self.assertEqual(html.count('aria-label="Task stage timeline"'), 1)

    def test_v2_session_state_shows_label_and_escaped_blockers(self):
        card = self.fixture()
        card["sessions"][0]["task_tracking"] = {"format": "v2", "title": "Plan", "file": "/r/t.md",
            "relative_file": "t.md", "total": 2, "completed": 0,
            "deliverables": {"total": 2, "completed": 0}, "steps": {"total": 0, "completed": 0},
            "counts": {"blocked": 2}, "items": [{"id": "S3", "status": "blocked", "title": "Client"},
                {"id": "S4", "status": "blocked", "title": "Server"}],
            "session_state": {"state": "waiting_user", "executable": [], "workers": [],
                "questions": [{"id": "Q1", "text": "Use REST or <b>GraphQL</b>?", "why": "blocks the client work",
                               "rows": ["S3", "S4"]}],
                "external": [{"id": "B1", "class": "capacity", "engine": "codex",
                              "until": "2026-10-21T18:00:00Z", "text": "", "rows": ["S4"]}]}}
        html = self.render(card)
        self.assertIn('<div class="task-state"><span class="pill">Waiting on you</span></div>', html)
        self.assertIn('<li>Q1: Use REST or &lt;b&gt;GraphQL&lt;/b&gt;? — blocks S3, S4: blocks the client work</li>', html)
        self.assertIn('<li>waiting for codex capacity until 2026-10-21T18:00:00Z</li>', html)
        self.assertNotIn('<b>GraphQL</b>', html)

    def test_legacy_and_sessionless_v2_ledgers_render_without_state_label(self):
        card = self.fixture()
        card["sessions"][0]["task_tracking"] = {"title": "Canvas work", "file": "/repo/docs/tasks/canvas.md",
            "relative_file": "docs/tasks/canvas.md", "total": 1, "completed": 0, "counts": {"pending": 1},
            "items": [{"id": "T01", "status": "pending", "title": "Reference"}]}
        self.assertNotIn('task-state', self.render(card))
        card2 = self.fixture()
        card2["sessions"][0]["task_tracking"] = {"format": "v2", "title": "Plan", "file": "/r/t.md",
            "relative_file": "t.md", "total": 1, "completed": 0,
            "deliverables": {"total": 1, "completed": 0}, "steps": {"total": 0, "completed": 0},
            "counts": {"pending": 1}, "items": [{"id": "T1", "status": "pending", "title": "Later"}]}
        self.assertNotIn('task-state', self.render(card2))

    def test_running_now_separates_runs_subagents_and_shells(self):
        card = self.fixture()
        card["runs"] = [{"id": "implement-1", "unit": "p1-api", "engine": "grok", "model": "grok-4", "state": "running"},
                        {"id": "implement-0", "unit": "p0-old", "engine": "grok", "state": "done"}]
        card["now"][0]["agents"] = [
            {"id": "a1", "label": "test-runner · run <tests>", "state": "running", "at": 2},
            {"id": "b1", "label": "shell · Dispatch P1 with Grok", "state": "running", "at": 3},
            {"id": "b2", "label": "shell · b2", "state": "completed", "at": 1}]
        html = self.render(card)
        live = html[html.index('data-info-section="live"'):html.index('data-info-section="summary"')]
        self.assertIn('<span class="chip">3 running</span>', live)
        self.assertIn('data-open-run="implement-1"', live)
        self.assertNotIn('implement-0', live)
        self.assertLess(live.index('<h5>Subagents'), live.index('data-agent="a1"'))
        self.assertLess(live.index('<h5>Background shells'), live.index('data-agent="b1"'))
        self.assertIn('1 running · 1 recent', live)
        self.assertIn('run &lt;tests&gt;', live)
        self.assertNotIn('<tests>', live)

    def test_run_card_absorbs_its_launcher_shell(self):
        card = self.fixture()
        card["now"][0]["name"] = "omni lead"
        card["runs"] = [{"id": "implement-20261014-125741-1", "unit": "p4-api", "engine": "grok", "model": "grok-4", "state": "running",
                         "session": "lead", "root": "/wt/p4", "mode": "implement", "started": 1, "updated": 2,
                         "touched": ["src/a.rs"], "open_risks": ["needs <db>"], "desc": "Ship the <p4> API"}]
        card["now"][0]["agents"] = [{"id": "b9", "label": "shell · Dispatch P4", "state": "completed", "at": 3, "shell": {
            "description": "Dispatch P4", "command": "cd /wt/p4 && run", "started": 1, "exit": 0, "cwd": "/wt/p4",
            "brief": "p4-api", "run": "implement-20261014-125741-1"}}]
        html = self.render(card)
        live = html[html.index('data-info-section="live"'):html.index('data-info-section="summary"')]
        for text in ('<b class="ls-title" title="Ship the &lt;p4&gt; API">Ship the &lt;p4&gt; API</b>', '<b>p4-api</b>', '<dt>Target</dt><dd>/wt/p4</dd>', '<dt>Brief</dt><dd>p4-api</dd>',
                     '<dt>Agent</dt><dd>grok · grok-4</dd>', '<dt>Launched by</dt><dd>Dispatch P4 · b9 · completed · exit 0</dd>',
                     'data-asid="lead" data-agent="implement-20261014-125741-1"', 'data-open-run="implement-20261014-125741-1">Panel', '1 file<', '1 risk<',
                     'Files touched (1)', 'needs &lt;db&gt;'):
            self.assertIn(text, live)
        self.assertNotIn('data-agent="b9"', live)
        self.assertNotIn('<dt>Session</dt>', live)
        self.assertNotIn('<db>', live)

    def test_unlinked_shell_card_names_session_target_and_console(self):
        card = self.fixture()
        card["now"][0]["name"] = "omni lead"
        card["now"][0]["agents"] = [{"id": "b7", "label": "shell · Commit", "state": "running", "at": 3, "shell": {
            "description": "Commit", "command": "git commit -m <x>", "started": 1, "exit": None, "cwd": "/wt/p7",
            "brief": "", "run": "", "moved": True}}]
        live = self.render(card)
        for text in ('<b class="ls-title" title="Commit">Commit</b>', '<dt>Target</dt><dd>/wt/p7</dd>', '<dt>Agent</dt><dd>none</dd>',
                     'started in the foreground', 'data-asid="lead" data-agent="b7"', 'git commit -m &lt;x&gt;'):
            self.assertIn(text, live)

    def test_run_card_offers_git_changes_only_with_a_worktree(self):
        card = self.fixture()
        card["runs"] = [{"id": "implement-5", "unit": "p5", "engine": "grok", "state": "running", "session": "lead", "root": "/wt/p5"},
                        {"id": "implement-6", "unit": "p6", "engine": "grok", "state": "running", "session": "lead"}]
        live = self.render(card)
        self.assertIn('data-asid="lead" data-run-changes="implement-5" aria-haspopup="dialog">Git changes', live)
        self.assertNotIn('data-run-changes="implement-6"', live)

    def dismiss_fixture(self):
        card = self.fixture()
        card["runs"] = [{"id": "implement-9", "unit": "p9", "engine": "grok", "state": "running", "session": "lead", "updated": 9e12},
                        {"id": "implement-8", "unit": "p8", "engine": "grok", "state": "done", "session": "lead", "updated": 9e12}]
        card["now"][0]["agents"] = [
            {"id": "a1", "label": "test-runner · t", "state": "completed", "at": 1},
            {"id": "b1", "label": "shell · Build", "state": "completed", "at": 2, "shell": {"description": "Build", "command": "make"}},
            {"id": "b2", "label": "shell · Watch", "state": "running", "at": 3, "shell": {"description": "Watch", "command": "tail"}}]
        return card

    def test_done_items_get_dismiss_and_running_items_do_not(self):
        live = self.render(self.dismiss_fixture())
        for done in ("implement-8", "a1", "b1"):
            self.assertIn(f'data-dismiss="{done}"', live)
        for running in ("implement-9", "b2"):
            self.assertNotIn(f'data-dismiss="{running}"', live)
        self.assertIn('data-dismiss-all="1">Dismiss all done (3)', live)

    def test_dismissed_done_items_are_hidden_but_running_ones_stay(self):
        live = self.render(self.dismiss_fixture(), pre="['implement-8', 'a1', 'b1', 'b2', 'implement-9'].forEach(id => dismissed.add(id));")
        live = live[live.index('data-info-section="live"'):live.index('data-info-section="summary"')]
        for gone in ('data-agent="implement-8"', 'data-agent="a1"', 'data-agent="b1"', 'data-dismiss-all'):
            self.assertNotIn(gone, live)
        for kept in ('data-agent="implement-9"', 'data-agent="b2"'):
            self.assertIn(kept, live)

    def test_workflow_runs_are_cards_and_hide_their_duplicate_agents(self):
        card = self.fixture()
        card["workflow_runs"] = [{"run_id": "fsa-audit-1", "role": "auditor", "engine": "claude", "model": "opus", "state": "completed",
                                  "verdict": "CHANGES", "root": "/wt/dev", "summary": "Fix the <race>", "updated": 9e12, "started": 1}]
        card["now"][0]["agents"] = [{"id": "fsa-audit-1", "label": "claude · auditor · opus", "state": "completed", "at": 2},
                                    {"id": "kid", "label": "codex · Harvey", "state": "running", "at": 3, "task": "chatbot readiness"}]
        html = self.render(card)
        live = html[html.index('data-info-section="live"'):html.index('data-info-section="summary"')]
        self.assertIn('<h5>Workflow runs', live)
        self.assertIn('title="Fix the &lt;race&gt;">Fix the &lt;race&gt;</b>', live)
        self.assertIn('<span class="pill warn">CHANGES</span>', live)
        self.assertNotIn('data-agent="fsa-audit-1"', live)
        self.assertIn('title="chatbot readiness">chatbot readiness</b>', live)
        self.assertIn('<b>Harvey</b>', live)
        self.assertNotIn('<h5>Implementer runs', live)

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
