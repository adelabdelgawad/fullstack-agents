"""Orchestrator wall and fleet renderers: cards, sidebar, worker squares, filters and sort, run in Node."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[2] / "plugins/fullstack-agents/scripts/lib"
STUBS = r'''
const document = {documentElement: {dataset: {}, classList: {add() {}, toggle() {}, contains() { return false; }}}, addEventListener() {}, querySelectorAll() { return []; }, getElementById() { return null; }};
const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const lead = x => x.group ? x.primary : x;
const rank = c => c.rank || 0;
const needsHuman = c => !!c.human;
const cardAgents = c => (c.now || []).flatMap(s => (s.agents || []).map(a => ({...a, sid: s.id})));
const STAGE_LABEL = c => c.phase || 'Investigate';
const FLAG_TEXT = {failed: 'run failed'};
const taskIsActive = x => x.status === 'in_progress';
const activeStep = c => c.steps.find(x => x.state === 'active');
const stepsDone = c => c.steps.filter(x => x.state === 'done').length;
const gitBadge = c => c.tree ? c.tree.dirty : 0;
const questionLine = () => '';
const cardNow = () => '';
const ago = () => '1m';
'''


def card(**kw):
    base = {"key": "k", "title": "Search", "label": "", "tree": None, "updated": 100, "runs": [], "now": [],
            "sessions": [{"id": "s1", "name": "lead", "state": "idle", "branch": "main"}], "usage": None,
            "needs_you": [], "phase": "implement", "steps": [], "rounds": [], "repo": "/home/u/repo", "worktree": ""}
    return {**base, **kw}


@unittest.skipUnless(shutil.which("node"), "node unavailable: renderer tests require Node.js")
class FleetUiTests(unittest.TestCase):
    def run_js(self, expr, setup=""):
        script = "const vm = require('vm'); const ctx = vm.createContext({});\n"
        script += "vm.runInContext(" + json.dumps(STUBS + (LIB / "fleet.js").read_text() + (LIB / "orchestrators.js").read_text() + setup) + ", ctx);\n"
        script += "process.stdout.write(JSON.stringify(vm.runInContext(" + json.dumps(expr) + ", ctx)));"
        return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)

    def test_orchestrator_card_shows_context_compactions_cost_and_git(self):
        u = {"fill": 0.93, "context": 930_000, "window": 1_000_000, "model": "claude-opus-5-5", "compactions": 2,
             "cost": 12.5, "tokens": 3_000_000, "blowout": True}
        c = card(usage=u, tree={"branch": "feat/search", "dirty": 4}, worktree="/home/u/wt", phase="Build")
        html = self.run_js(f"orcCard({json.dumps(c)})")
        self.assertIn("orc st-idle blowout", html)
        self.assertIn('<span class="bad">93%</span>', html)
        self.assertIn(">2×<", html)
        self.assertIn("$12.50", html)
        self.assertIn("feat/search", html)
        self.assertIn("4 modified", html)
        self.assertIn(">worktree<", html)
        self.assertIn("orchestrator · claude", html)

    def test_waiting_orchestrator_offers_respond(self):
        html = self.run_js(f"orcCard({json.dumps(card(human=True))})")
        self.assertIn("Waiting · needs you", html)
        self.assertIn('data-respond="k"', html)

    def test_unknown_price_renders_dash_not_zero(self):
        u = {"fill": 0.1, "context": 1, "window": 10, "model": "gpt-x", "compactions": 0, "cost": None, "tokens": 5}
        html = self.run_js(f"orcCard({json.dumps(card(usage=u))})")
        self.assertIn("<b>—</b>", html)
        self.assertNotIn("$0", html)

    def test_plan_progress_comes_from_task_file(self):
        t = {"title": "Ship search", "completed": 2, "total": 5, "items": [{"status": "in_progress", "title": "Index"}]}
        c = card(sessions=[{"id": "s1", "name": "lead", "state": "working", "task_tracking": t}])
        html = self.run_js(f"orcCard({json.dumps(c)})")
        self.assertIn("Ship search · Index", html)
        self.assertIn("<b>2/5</b>", html)

    def test_sidebar_counts_and_selection(self):
        cards = json.dumps([card(key="a", human=True), card(key="b")])
        html = self.run_js(f"orcSidebar({cards})", "\nvar openKey = 'b';")
        self.assertIn("0 running · 1 waiting · 0 stale", html)
        self.assertIn('class="orc-row sel st-idle" data-orc="b"', html)

    def test_squares_colour_by_model_and_mark_failures(self):
        runs = [{"id": f"implement-{i}", "mode": "implement", "unit": f"u{i}", "state": s, "model": "gpt-5.6-sol",
                 "cause": "error: x" if s == "failed" else ""} for i, s in enumerate(["done", "failed", "running"])]
        now = [{"id": "s1", "agents": [{"id": "a1", "state": "running", "model": "claude-sonnet-5-5", "label": "reviewer"}]}]
        html = self.run_js(f"squaresHtml({json.dumps(card(runs=runs, now=now))})")
        self.assertEqual(html.count('class="sq '), 4)
        self.assertIn("sq m-gpt failed", html)
        self.assertIn("sq m-sonnet running", html)
        self.assertIn("error: x", html)

    def test_plan_tile_shows_each_window_and_warns_when_high(self):
        p = {"plan": "team", "windows": [{"name": "5 h", "pct": 14, "resets_at": ""}, {"name": "week", "pct": 92, "resets_at": ""}]}
        html = self.run_js(f"planTile('Claude plan', {json.dumps(p)})")
        self.assertIn("ft plan bad", html)
        self.assertIn("<b>14%</b>", html)
        self.assertIn("<b>92%</b>", html)
        self.assertIn("Claude plan · team", html)
        self.assertIn("no Claude login", self.run_js("planTile('Claude plan', {error: 'no Claude login found'})"))
        codex = {"plan": "plus", "windows": [{"name": "week", "pct": 100, "resets_at": ""}], "credits": {"balance": 59210.4, "unlimited": False}}
        html = self.run_js(f"planTile('Codex plan', {json.dumps(codex)})")
        self.assertIn("plan-credits on", html)
        self.assertIn("on credits · 59,210 left", html)
        reset = {"plan": "team", "windows": [{"name": "5 h", "pct": None, "resets_at": ""}]}
        self.assertIn("<b>—</b>", self.run_js(f"planTile('Claude plan', {json.dumps(reset)})"))

    def test_grok_tile_shows_spend_without_percentages(self):
        g = {"plan": "xAI", "spend": [{"name": "today", "cost": 0, "tokens": 0}, {"name": "7 days", "cost": 13.12, "tokens": 19537829}], "last_at": 0}
        html = self.run_js(f"spendTile('Grok', {json.dumps(g)})")
        self.assertIn("Grok · xAI", html)
        self.assertIn("19.5M", html)
        self.assertIn("$13.12", html)
        self.assertIn('href="https://grok.com" target="_blank" rel="noopener noreferrer"', html)
        self.assertNotIn("%", html)

    def test_scripts_share_no_top_level_names(self):
        html = (LIB / "dashboard.html").read_text()
        main = html[html.rindex("<script>"):]
        decl = re.compile(r"^(?:const|let|var|function|async function|class) ([A-Za-z_$][\w$]*)", re.MULTILINE)
        names = set(decl.findall(main))
        for extra in ("fleet.js", "orchestrators.js"):
            clash = names & set(decl.findall((LIB / extra).read_text()))
            self.assertFalse(clash, f"{extra} redeclares {sorted(clash)}; the browser then rejects the whole main script")

    def test_squares_empty_without_workers(self):
        self.assertEqual(self.run_js(f"squaresHtml({json.dumps(card())})"), "")

    def test_filters_select_blowouts_and_text(self):
        hot = card(key="hot", usage={"blowout": True, "model": "claude-opus-5-5"})
        cold = card(key="cold", title="Other", usage={"blowout": False, "model": "x"})
        cards = json.dumps([hot, cold])
        self.assertEqual(self.run_js(f"{cards}.filter(fleetMatches).map(c => c.key)", "\nfleet.filter = 'blowouts';"), ["hot"])
        self.assertEqual(self.run_js(f"{cards}.filter(fleetMatches).map(c => c.key)", "\nfleet.filter = 'all'; fleet.text = 'oth';"), ["cold"])

    def test_cost_sort_puts_most_expensive_first(self):
        cards = json.dumps([card(key="a", usage={"cost": 1}), card(key="b", usage={"cost": 9}), card(key="c")])
        self.assertEqual(self.run_js(f"{cards}.sort(fleetCompare).map(c => c.key)", "\nfleet.sort = 'cost';"), ["b", "a", "c"])


if __name__ == "__main__":
    unittest.main()
