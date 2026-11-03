"""Herdr tab OSC 52 copy scanner, and that the old per-pane chrome left no dead references."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

HTML = Path(__file__).resolve().parents[2] / "plugins/fullstack-agents/scripts/lib/dashboard.html"

REMOVED_NAMES = [
    "herdrSidebarHtml", "herdrTabsHtml", "wireHerdrPicks", "closeHerdrTab", "applyHerdrSidebarRatio",
    "herdrChromeSnapshot", "restoreHerdrChrome", "updateHerdrTabOverflow", "followNewHerdrTab", "herdrKnownTabs",
    "openHerdrGlobalMenu", "herdrSidebarRatio", "herdrDragging", "selectedHerdrPane", "sessionHerdrPane",
    "statusMeta", "statusHtml", "workspaceStatus", "fsa-herdr-sidebar-ratio",
    "herdr-view", "herdr-list", "herdr-sidebar-", "herdr-workspace", "herdr-agent", "herdr-tab", "herdr-main",
]


@unittest.skipUnless(shutil.which("node"), "node unavailable: herdr client tests require Node.js")
class Osc52ScannerTests(unittest.TestCase):
    def run_js(self, body):
        source = HTML.read_text()
        code = re.search(r"function createOsc52Scanner[\s\S]*?(?=\nfunction webglRendererOk)", source).group()
        script = code + "\n" + body
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_bel_terminated_sequence_decodes(self):
        out = self.run_js("""
const received = [];
const scan = createOsc52Scanner(text => received.push(text));
const payload = Buffer.from('Hello, OSC 52', 'utf8').toString('base64');
const bytes = [0x1b, 0x5d, 0x35, 0x32, 0x3b, ...Buffer.from('c;' + payload, 'latin1'), 0x07];
scan(Uint8Array.from(bytes));
process.stdout.write(JSON.stringify(received));
""")
        self.assertEqual(out, ["Hello, OSC 52"])

    def test_st_terminated_sequence_decodes(self):
        out = self.run_js("""
const received = [];
const scan = createOsc52Scanner(text => received.push(text));
const payload = Buffer.from('via ST', 'utf8').toString('base64');
const bytes = [0x1b, 0x5d, 0x35, 0x32, 0x3b, ...Buffer.from('c;' + payload, 'latin1'), 0x1b, 0x5c];
scan(Uint8Array.from(bytes));
process.stdout.write(JSON.stringify(received));
""")
        self.assertEqual(out, ["via ST"])

    def test_sequence_split_byte_by_byte_across_chunks(self):
        out = self.run_js("""
const received = [];
const scan = createOsc52Scanner(text => received.push(text));
const payload = Buffer.from('byte at a time', 'utf8').toString('base64');
const bytes = [0x1b, 0x5d, 0x35, 0x32, 0x3b, ...Buffer.from('c;' + payload, 'latin1'), 0x07];
for (const b of bytes) scan(Uint8Array.of(b));
process.stdout.write(JSON.stringify(received));
""")
        self.assertEqual(out, ["byte at a time"])

    def test_query_payload_is_ignored(self):
        out = self.run_js("""
const received = [];
const scan = createOsc52Scanner(text => received.push(text));
const bytes = [0x1b, 0x5d, 0x35, 0x32, 0x3b, ...Buffer.from('c;?', 'latin1'), 0x07];
scan(Uint8Array.from(bytes));
process.stdout.write(JSON.stringify(received));
""")
        self.assertEqual(out, [])

    def test_utf8_payload_decodes_multibyte_text(self):
        out = self.run_js("""
const received = [];
const scan = createOsc52Scanner(text => received.push(text));
const payload = Buffer.from('héllo 世界', 'utf8').toString('base64');
const bytes = [0x1b, 0x5d, 0x35, 0x32, 0x3b, ...Buffer.from('c;' + payload, 'latin1'), 0x07];
scan(Uint8Array.from(bytes));
process.stdout.write(JSON.stringify(received));
""")
        self.assertEqual(out, ["héllo 世界"])

    def test_oversize_sequence_is_dropped(self):
        out = self.run_js("""
const received = [];
const scan = createOsc52Scanner(text => received.push(text));
scan(Uint8Array.from([0x1b, 0x5d, 0x35, 0x32, 0x3b]));
scan(new Uint8Array((4 << 20) + 10).fill(0x41));
scan(Uint8Array.of(0x07));
process.stdout.write(JSON.stringify(received));
""")
        self.assertEqual(out, [])

    def test_plain_output_calls_no_text(self):
        out = self.run_js("""
const received = [];
const scan = createOsc52Scanner(text => received.push(text));
scan(Uint8Array.from(Buffer.from('ordinary shell output\\r\\n', 'utf8')));
process.stdout.write(JSON.stringify(received));
""")
        self.assertEqual(out, [])


@unittest.skipUnless(shutil.which("node"), "node unavailable: herdr client tests require Node.js")
class CopySelectionTests(unittest.TestCase):
    def test_blocked_copy_offers_a_click_that_retries_the_same_text(self):
        source = HTML.read_text()
        code = re.search(r"async function copySelection[\s\S]*?\n}\n", source).group()
        script = code + """
const toasts = [], writes = [];
let allow = false, restored = 0;
async function writeClipboard(text) { writes.push(text.length); return allow; }
function showHerdrToast(message, action) { toasts.push({message, action}); }
(async () => {
  const text = "x".repeat(40000);
  await copySelection(text, () => restored++);
  allow = true;
  await toasts[0].action.run();
  process.stdout.write(JSON.stringify({toasts: toasts.map(t => [t.message, t.action && t.action.label]), writes, restored}));
})();
"""
        out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(out["toasts"], [["copy blocked by the browser", "copy 40000 chars"], ["copied 40000 chars", None]])
        self.assertEqual(out["writes"], [40000, 40000])
        self.assertEqual(out["restored"], 2)

    def test_herdr_client_copy_reports_the_real_result(self):
        source = HTML.read_text()
        self.assertIn("const onCopyText = text => { if (text) copySelection(text, () => term.focus()); };", source)


class RemovedChromeTests(unittest.TestCase):
    def test_removed_herdr_sidebar_and_tab_chrome_left_no_references(self):
        source = HTML.read_text()
        found = [name for name in REMOVED_NAMES if name in source]
        self.assertEqual(found, [])

    def test_herdr_client_uses_the_websocket_endpoint(self):
        source = HTML.read_text()
        self.assertIn("/api/herdr/client", source)


    def test_herdr_client_has_red_attach_button_using_the_file_endpoint(self):
        source = HTML.read_text()
        self.assertIn("data-herdr-client-attach", source)
        self.assertIn(".herdr-client-attach { color: var(--herdr-red)", source)
        self.assertIn('uploadFiles(files, "/api/herdr/file?")', source)
        self.assertIn("wireFileDrop(host, attach)", source)

if __name__ == "__main__":
    unittest.main()
