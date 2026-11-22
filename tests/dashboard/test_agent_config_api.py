"""/api/agent-config: read and save the CTO default and a session's agent settings over real HTTP."""
import http.client
import http.server
import importlib.util
import json
import os
import tempfile
import threading
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
_loader = SourceFileLoader("fsa_dashboard", str(REPO / "plugins/fullstack-agents/scripts/fsa-dashboard"))
dash = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_dashboard", _loader))
_loader.exec_module(dash)

TOKEN = "t0ken"
KNOWN = "abc-123"


class StubServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), dash.Handler)
        self.token = TOKEN

    def source(self, key):
        return "/tmp/transcript.jsonl" if key == f"{KNOWN}/{KNOWN}" else None


class AgentConfigApiTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-agent-cfg-")
        self.env = patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": self.scratch.name})
        self.env.start()
        self.server = StubServer()
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.agents = Path(self.scratch.name) / "fullstack-agents" / "agents"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.env.stop()
        self.scratch.cleanup()

    def call(self, method, path, body=None, token=TOKEN):
        conn = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        headers = {"Cookie": f"fsa_t={token}"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers.update({"Content-Type": "application/json", "Content-Length": str(len(data))})
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        return resp.status, raw

    def test_default_read_when_nothing_saved(self):
        status, raw = self.call("GET", "/api/agent-config")
        self.assertEqual(status, 200)
        reply = json.loads(raw)
        self.assertEqual(reply["scope"], "default")
        self.assertIsNone(reply["settings"])
        self.assertEqual(reply["builtin"]["implementer"], "claude")
        self.assertIn("codex", reply["engines"])
        self.assertIn("haiku", reply["subagent_models"])

    def test_save_default_then_read_back(self):
        settings = {"implementer": "codex", "models": {"codex_implement": "gpt-x", "codex_plan": ""},
                    "grok_scan": True, "subagents": {"test-runner": "haiku", "diff-reviewer": ""}}
        status, raw = self.call("POST", "/api/agent-config", {"settings": settings})
        self.assertEqual(status, 200, raw)
        expected = {"implementer": "codex", "models": {"codex_implement": "gpt-x"}, "grok_scan": True,
                    "subagents": {"test-runner": "haiku"}}
        self.assertEqual(json.loads(raw)["settings"], expected)
        self.assertEqual(json.loads((self.agents / "default.json").read_text()), expected)
        self.assertEqual(json.loads(self.call("GET", "/api/agent-config")[1])["settings"], expected)

    def test_session_settings_saved_apart_from_default(self):
        status, raw = self.call("GET", f"/api/agent-config?sid={KNOWN}")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["scope"], "session")
        self.assertIsNone(json.loads(raw)["settings"])
        status, raw = self.call("POST", "/api/agent-config", {"sid": KNOWN, "settings": {"implementer": "grok"}})
        self.assertEqual(status, 200, raw)
        self.assertTrue((self.agents / f"session-{KNOWN}.json").exists())
        self.assertFalse((self.agents / "default.json").exists())

    def test_unknown_session_and_bad_values_rejected(self):
        self.assertEqual(self.call("GET", "/api/agent-config?sid=nope")[0], 404)
        self.assertEqual(self.call("GET", "/api/agent-config?sid=../x")[0], 404)
        self.assertEqual(self.call("POST", "/api/agent-config", {"sid": "nope", "settings": {}})[0], 404)
        status, raw = self.call("POST", "/api/agent-config", {"settings": {"implementer": "gpt"}})
        self.assertEqual(status, 400)
        self.assertIn(b"implementer", raw)
        bad_model = {"settings": {"models": {"claude_implement": "x; rm -rf /"}}}
        self.assertEqual(self.call("POST", "/api/agent-config", bad_model)[0], 400)
        self.assertEqual(self.call("POST", "/api/agent-config", ["not", "a", "dict"])[0], 400)
        self.assertFalse((self.agents / "default.json").exists())

    def test_requires_token(self):
        self.assertEqual(self.call("GET", "/api/agent-config", token="wrong")[0], 403)
        self.assertEqual(self.call("POST", "/api/agent-config", {"settings": {}}, token="wrong")[0], 403)


if __name__ == "__main__":
    unittest.main()
