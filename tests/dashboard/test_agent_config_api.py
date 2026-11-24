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

    sources = {}

    def source(self, key):
        if key in self.sources:
            return self.sources[key]
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
        self.assertEqual(set(reply["model_choices"]), {"claude", "codex", "grok"})

    def test_codex_choices_come_from_its_visible_models(self):
        (Path(self.scratch.name) / "models_cache.json").write_text(json.dumps({"models": [
            {"slug": "gpt-6-sol", "visibility": "list"}, {"slug": "gpt-reserve", "visibility": "hide"}]}))
        with patch.dict(os.environ, {"CODEX_HOME": self.scratch.name}):
            reply = json.loads(self.call("GET", "/api/agent-config")[1])
        self.assertEqual(reply["model_choices"]["codex"], ["gpt-6-sol"])
        with patch.dict(os.environ, {"CODEX_HOME": str(Path(self.scratch.name) / "none")}):
            reply = json.loads(self.call("GET", "/api/agent-config")[1])
        self.assertIn("gpt-5.6-sol", reply["model_choices"]["codex"])

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

    def test_session_pinned_before_agent_settings_is_reported(self):
        pins = Path(self.scratch.name) / "fullstack-agents" / "pins"
        pins.mkdir(parents=True)
        (pins / f"session-{KNOWN}.json").write_text(json.dumps({"version": "3.87.0"}))
        body = json.loads(self.call("GET", f"/api/agent-config?sid={KNOWN}")[1])
        self.assertEqual((body["pinned_release"], body["applies"]), ("3.87.0", False))
        (pins / f"session-{KNOWN}.json").write_text(json.dumps({"version": "3.113.2"}))
        body = json.loads(self.call("GET", f"/api/agent-config?sid={KNOWN}")[1])
        self.assertEqual((body["pinned_release"], body["applies"]), ("3.113.2", True))
        body = json.loads(self.call("GET", "/api/agent-config")[1])
        self.assertEqual((body["pinned_release"], body["applies"]), (None, True))

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

    def test_subagent_conversation_starts_with_the_team_leaders_prompt(self):
        rows = [{"type": "user", "isSidechain": True, "timestamp": "2026-11-22T07:00:00Z",
                 "message": {"role": "user", "content": "Review the saved diff\nLENS: code"}},
                {"type": "assistant", "isSidechain": True, "timestamp": "2026-11-22T07:00:05Z",
                 "message": {"role": "assistant", "content": [{"type": "text", "text": "VERDICT: ok"}]}}]
        sub = Path(self.scratch.name) / "agent-a1.jsonl"
        sub.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        shell = Path(self.scratch.name) / "b1.output"
        shell.write_text("log")
        self.server.sources = {f"{KNOWN}/a1": str(sub), f"{KNOWN}/b1": str(shell)}
        status, raw = self.call("GET", f"/api/conversation?sid={KNOWN}&id=a1")
        self.assertEqual(status, 200, raw)
        messages = json.loads(raw)["messages"]
        self.assertEqual([(m["role"], m["text"]) for m in messages],
                         [("user", "Review the saved diff\nLENS: code"), ("assistant", "VERDICT: ok")])
        self.assertEqual(self.call("GET", f"/api/conversation?sid={KNOWN}&id=b1")[0], 404)
        self.assertEqual(self.call("GET", f"/api/conversation?sid={KNOWN}&id=zz")[0], 404)
        self.assertEqual(self.call("GET", f"/api/conversation?sid={KNOWN}&id=../x")[0], 400)

    def test_requires_token(self):
        self.assertEqual(self.call("GET", "/api/agent-config", token="wrong")[0], 403)
        self.assertEqual(self.call("POST", "/api/agent-config", {"settings": {}}, token="wrong")[0], 403)


if __name__ == "__main__":
    unittest.main()
