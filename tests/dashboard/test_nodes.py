"""Linked hosts: registry, authenticated proxy (plain, streamed, refused paths) and the folder listing, over real HTTP."""
import http.client
import http.server
import importlib.util
import json
import os
import stat
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
nodes = dash.nodes

TOKEN = "local-token"
REMOTE_TOKEN = "remote-token-123"


class Remote(http.server.BaseHTTPRequestHandler):
    """A stand-in linked dashboard: answers only its own token, echoes what it received."""
    protocol_version = "HTTP/1.1"
    seen = []

    def log_message(self, *args):
        return

    def reply(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Screen-Hash", "abc")
        self.send_header("Set-Cookie", "fsa_t=leak")
        self.end_headers()
        self.wfile.write(body)

    def authorised(self):
        return f"fsa_t={REMOTE_TOKEN}" in (self.headers.get("Cookie") or "")

    def do_GET(self):
        Remote.seen.append(("GET", self.path, self.headers.get("Cookie")))
        if not self.authorised():
            return self.reply(403, b"forbidden", "text/plain")
        if self.path.startswith("/api/herdr/live"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            for i in range(3):
                self.wfile.write(f"data: {i}\n\n".encode())
                self.wfile.flush()
            self.close_connection = True
            return
        self.reply(200, json.dumps({"path": self.path}).encode())

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        Remote.seen.append(("POST", self.path, body))
        if not self.authorised():
            return self.reply(403, b"forbidden", "text/plain")
        self.reply(200, json.dumps({"got": json.loads(body)}).encode())


class StubServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), dash.Handler)
        self.token = TOKEN


class NodesTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-nodes-")
        self.registry = Path(self.scratch.name) / "cfg" / "nodes.json"
        self.env = patch.dict(os.environ, {"FSA_NODES_FILE": str(self.registry)})
        self.env.start()
        Remote.seen = []
        self.remote = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Remote)
        self.remote.daemon_threads = True
        self.server = StubServer()
        for srv in (self.remote, self.server):
            threading.Thread(target=srv.serve_forever, daemon=True).start()

    def tearDown(self):
        for srv in (self.server, self.remote):
            srv.shutdown()
            srv.server_close()
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
        out = resp.status, resp.read(), dict(resp.getheaders())
        conn.close()
        return out

    def link(self, token=REMOTE_TOKEN):
        return self.call("POST", "/api/nodes", {"label": "GPU box", "host": "127.0.0.1",
                                                "port": self.remote.server_address[1], "token": token})

    def test_link_saves_private_registry_and_hides_token(self):
        status, body, _ = self.link()
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)["node"]["id"], "gpu-box")
        self.assertEqual(stat.S_IMODE(self.registry.stat().st_mode), 0o600)
        status, body, _ = self.call("GET", "/api/nodes")
        self.assertEqual(status, 200)
        self.assertNotIn(REMOTE_TOKEN, body.decode())
        self.assertEqual(json.loads(body)["nodes"][0]["label"], "GPU box")

    def test_link_refused_token_is_not_saved(self):
        status, body, _ = self.link("wrong-token-1")
        self.assertEqual(status, 502)
        self.assertIn(b"refused", body)
        self.assertFalse(self.registry.exists())

    def test_link_rejects_bad_fields(self):
        for bad in ({"host": "a b", "port": 1, "token": REMOTE_TOKEN}, {"host": "h", "port": 70000, "token": REMOTE_TOKEN},
                    {"host": "h", "port": 80, "token": "x"}):
            self.assertEqual(self.call("POST", "/api/nodes", bad)[0], 400, bad)

    def test_link_needs_local_token(self):
        self.assertEqual(self.call("GET", "/api/nodes", token="nope")[0], 403)
        self.assertEqual(self.call("POST", "/api/nodes", {}, token="nope")[0], 403)

    def test_proxy_get_and_post_carry_remote_token(self):
        self.link()
        status, body, headers = self.call("GET", "/api/node/gpu-box/api/state?x=1")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"path": "/api/state?x=1"})
        self.assertEqual(headers.get("X-Screen-Hash"), "abc")
        self.assertNotIn("Set-Cookie", headers)
        self.assertIn(f"fsa_t={REMOTE_TOKEN}", Remote.seen[-1][2])
        status, body, _ = self.call("POST", "/api/node/gpu-box/api/herdr/action", {"action": "x"})
        self.assertEqual((status, json.loads(body)), (200, {"got": {"action": "x"}}))

    def test_proxy_drops_local_token_query(self):
        self.link()
        status, body, _ = self.call("GET", f"/api/node/gpu-box/api/state?t={TOKEN}&a=1")
        self.assertEqual((status, json.loads(body)), (200, {"path": "/api/state?a=1"}))

    def test_websocket_tunnel_relays_upgrade_with_node_origin(self):
        import socket as sock_mod
        listener = sock_mod.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        got = {}

        def fake_node():
            conn, _ = listener.accept()
            got["request"] = conn.recv(4096).decode()
            conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\n\r\n")
            got["frame"] = conn.recv(16)
            conn.sendall(b"pong")
            conn.close()

        threading.Thread(target=fake_node, daemon=True).start()
        with patch.object(nodes, "probe", lambda *a: ""):
            self.call("POST", "/api/nodes", {"label": "ws", "host": "127.0.0.1", "port": port, "token": REMOTE_TOKEN})
        host = "%s:%d" % self.server.server_address
        client = sock_mod.create_connection(self.server.server_address, timeout=5)
        client.sendall((f"GET /api/node/ws/api/herdr/client?cols=80&rows=24 HTTP/1.1\r\nHost: {host}\r\n"
                        f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: k3y\r\n"
                        f"Origin: http://{host}\r\nCookie: fsa_t={TOKEN}\r\n\r\n").encode())
        first = client.recv(256)
        self.assertTrue(first.startswith(b"HTTP/1.1 101"), first)
        client.sendall(b"ping")
        self.assertEqual(client.recv(16), b"pong")
        client.close()
        listener.close()
        self.assertEqual(got["frame"], b"ping")
        self.assertIn(f"Origin: http://127.0.0.1:{port}", got["request"])
        self.assertIn(f"fsa_t={REMOTE_TOKEN}", got["request"])
        self.assertIn("Sec-WebSocket-Key: k3y", got["request"])
        self.assertNotIn(TOKEN, got["request"].replace(REMOTE_TOKEN, ""))

    def test_link_refuses_cross_origin_post(self):
        conn = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        data = b"{}"
        conn.request("POST", "/api/nodes", body=data, headers={
            "Cookie": f"fsa_t={TOKEN}", "Origin": "http://evil.example", "Content-Type": "application/json",
            "Content-Length": "2"})
        self.assertEqual(conn.getresponse().status, 403)
        conn.close()

    def test_proxy_streams_live_events(self):
        self.link()
        status, body, headers = self.call("GET", "/api/node/gpu-box/api/herdr/live?session=s")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/event-stream")
        self.assertEqual(body, b"data: 0\n\ndata: 1\n\ndata: 2\n\n")

    def test_proxy_refuses_other_paths_and_unknown_hosts(self):
        self.link()
        for path in ("/api/node/gpu-box/static/x", "/api/node/gpu-box/api/node/gpu-box/api/state",
                     "/api/node/gpu-box/api/nodes", "/api/node/gpu-box/api/../x"):
            self.assertEqual(self.call("GET", path)[0], 400, path)
        self.assertEqual(self.call("GET", "/api/node/other/api/state")[0], 404)
        self.assertEqual(self.call("GET", "/api/node/gpu-box/api/state", token="nope")[0], 403)

    def test_remove_link(self):
        self.link()
        status, body, _ = self.call("POST", "/api/nodes/remove", {"id": "gpu-box"})
        self.assertEqual((status, json.loads(body)["nodes"]), (200, []))
        self.assertEqual(self.call("POST", "/api/nodes/remove", {"id": "gpu-box"})[0], 404)

    def test_folder_listing_marks_git_and_hides_dot_folders(self):
        root = Path(self.scratch.name) / "tree"
        (root / "repo" / ".git").mkdir(parents=True)
        (root / "plain").mkdir()
        (root / ".hidden").mkdir()
        (root / "file.txt").write_text("x")
        status, body, _ = self.call("GET", f"/api/fs/dirs?path={root}")
        listing = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual([(d["name"], d["git"]) for d in listing["dirs"]], [("plain", False), ("repo", True)])
        self.assertEqual(listing["parent"], str(root.parent))
        hidden = json.loads(self.call("GET", f"/api/fs/dirs?path={root}&hidden=1")[1])
        self.assertIn(".hidden", [d["name"] for d in hidden["dirs"]])
        self.assertEqual(self.call("GET", "/api/fs/dirs?path=relative/x")[0], 400)
        self.assertEqual(self.call("GET", f"/api/fs/dirs?path={root}/missing")[0], 404)


if __name__ == "__main__":
    unittest.main()
