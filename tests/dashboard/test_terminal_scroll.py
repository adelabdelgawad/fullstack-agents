"""Live terminal wheel scrolling keeps one request in flight on slow links."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

HTML = Path(__file__).resolve().parents[2] / "plugins/fullstack-agents/scripts/lib/dashboard.html"


@unittest.skipUnless(shutil.which("node"), "node unavailable: terminal tests require Node.js")
class TerminalScrollTests(unittest.TestCase):
    def run_js(self, body):
        source = HTML.read_text()
        code = re.search(r"function queueTerminalScroll[\s\S]*?(?=\nfunction disposeLiveTerminal)", source).group()
        script = """
const frames = [];
const requestAnimationFrame = f => { frames.push(f); return frames.length; };
const tick = () => frames.splice(0).forEach(f => f());
const posts = [];
let release = [];
function postLiveTerminal(current, body) {
  posts.push(body);
  return new Promise(resolve => release.push(resolve));
}
const settle = async () => { release.splice(0).forEach(r => r()); await new Promise(r => setTimeout(r, 0)); };
""" + code + "\n(async () => {" + body + "})().catch(e => { console.error(e); process.exit(1); });"
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_burst_of_wheel_ticks_becomes_one_request_then_the_remainder(self):
        out = self.run_js("""
const current = {session: "s1"};
for (let i = 0; i < 30; i++) queueTerminalScroll(current, -1);
tick();
for (let i = 0; i < 20; i++) queueTerminalScroll(current, -1);
tick();
const inFlight = posts.length;
await settle();
const after = posts.slice();
await settle();
process.stdout.write(JSON.stringify({inFlight, after, left: current.scrollLines}));
""")
        self.assertEqual(out["inFlight"], 1)
        self.assertEqual(out["after"], [{"type": "scroll", "direction": "up", "lines": 30},
                                        {"type": "scroll", "direction": "up", "lines": 20}])
        self.assertEqual(out["left"], 0)

    def test_opposite_directions_cancel_and_large_totals_respect_server_cap(self):
        out = self.run_js("""
const current = {session: "s1"};
queueTerminalScroll(current, 5); queueTerminalScroll(current, -5);
tick();
const cancelled = posts.length;
queueTerminalScroll(current, 250);
tick();
await settle(); await settle(); await settle();
process.stdout.write(JSON.stringify({cancelled, posts}));
""")
        self.assertEqual(out["cancelled"], 0)
        self.assertEqual([p["lines"] for p in out["posts"]], [100, 100, 50])
        self.assertTrue(all(p["direction"] == "down" for p in out["posts"]))

    def test_unconnected_terminal_drops_queued_scroll(self):
        out = self.run_js("""
const current = {session: ""};
queueTerminalScroll(current, 3);
tick();
process.stdout.write(JSON.stringify({posts, left: current.scrollLines}));
""")
        self.assertEqual(out, {"posts": [], "left": 0})


@unittest.skipUnless(shutil.which("node"), "node unavailable: terminal tests require Node.js")
class TerminalReconnectTests(unittest.TestCase):
    def run_js(self, body):
        source = HTML.read_text()
        code = re.search(r"const RECONNECT_QUIET[\s\S]*?(?=\naddEventListener\(\"online\")", source).group()
        script = """
const el = () => ({hidden: true, textContent: "", classList: {add() { this.on = true; }, remove() {}, toggle() {}}});
const nodes = {"[data-terminal-status]": el()};
const timers = [];
const setTimeout = (f, ms) => { timers.push(ms); return timers.length; };
const shown = [];
function closeLiveStream(current) { current.stream = null; }
function liveTerminalStatus(current, reason) { shown.push(reason); }
let opened = 0;
function openLiveStream() { opened++; }
""" + code + "\n(() => {" + body + "})();"
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_drops_keep_retrying_with_backoff_and_stay_quiet_at_first(self):
        out = self.run_js("""
const current = {root: {querySelector: q => nodes[q]}, mode: "live"};
const terminal = current;
for (let i = 0; i < 6; i++) liveTerminalClosed(current, "Connection closed");
process.stdout.write(JSON.stringify({timers, shown, status: nodes["[data-terminal-status]"].textContent, retries: current.retries}));
""")
        self.assertEqual(out["timers"], [1000, 2000, 4000, 8000, 10000, 10000])
        self.assertEqual(out["shown"], ["Connection closed"] * 3)
        self.assertEqual(out["retries"], 6)

    def test_ownership_conflict_is_reported_without_retry(self):
        out = self.run_js("""
const current = {root: {querySelector: q => nodes[q]}, mode: "live"};
liveTerminalClosed(current, "pane already has an attached client");
process.stdout.write(JSON.stringify({timers, shown}));
""")
        self.assertEqual(out, {"timers": [], "shown": ["pane already has an attached client"]})


if __name__ == "__main__":
    unittest.main()
