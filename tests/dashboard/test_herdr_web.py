"""Frame codec, handshake and the pty round trip for the full herdr client over one WebSocket."""
import http.client
import importlib.util
import json
import os
import socket
import stat
import struct
import subprocess
import tempfile
import threading
import time
import unittest
from importlib.machinery import SourceFileLoader
from io import BytesIO
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "plugins/fullstack-agents/scripts/lib"
_herdr_web_loader = SourceFileLoader("herdr_web", str(LIB / "herdr_web.py"))
herdr_web = importlib.util.module_from_spec(importlib.util.spec_from_loader("herdr_web", _herdr_web_loader))
_herdr_web_loader.exec_module(herdr_web)
_loader = SourceFileLoader("fsa_dashboard_herdr_web", str(REPO / "plugins/fullstack-agents/scripts/fsa-dashboard"))
dash = importlib.util.module_from_spec(importlib.util.spec_from_loader("fsa_dashboard_herdr_web", _loader))
_loader.exec_module(dash)

FAKE_HERDR = """#!/usr/bin/env python3
import os, subprocess, sys
subprocess.run(["stty", "-echo"])
print("ARGV:" + " ".join(sys.argv), flush=True)
print("TERM:" + os.environ.get("TERM", ""), flush=True)
print("INIT:" + subprocess.run(["stty", "size"], capture_output=True, text=True).stdout, end="", flush=True)
for line in sys.stdin:
    line = line.rstrip("\\n")
    if line == "SIZE":
        sys.stdout.write(subprocess.run(["stty", "size"], capture_output=True, text=True).stdout)
    else:
        sys.stdout.write("ECHO:" + line + "\\n")
    sys.stdout.flush()
"""


def mask_frame(op, payload, mask=b"\x01\x02\x03\x04", fin=True):
    n = len(payload)
    first = (0x80 if fin else 0) | op
    if n < 126:
        head = bytes([first, 0x80 | n])
    elif n < 65536:
        head = bytes([first, 0x80 | 126]) + struct.pack("!H", n)
    else:
        head = bytes([first, 0x80 | 127]) + struct.pack("!Q", n)
    return head + mask + herdr_web.unmask(payload, mask)


def read_server_frame(rfile):
    head = rfile.read(2)
    fin, op = bool(head[0] & 0x80), head[0] & 0x0F
    size = head[1] & 0x7F
    if size == 126:
        size = struct.unpack("!H", rfile.read(2))[0]
    elif size == 127:
        size = struct.unpack("!Q", rfile.read(8))[0]
    return fin, op, rfile.read(size)


class RecordingSocket:
    def __init__(self):
        self.sent = bytearray()

    def sendall(self, data):
        self.sent += data


class FrameCodecTests(unittest.TestCase):
    def test_small_message_round_trip(self):
        ws = herdr_web.WebSocket(RecordingSocket(), BytesIO(mask_frame(herdr_web.OP_BIN, b"hello")))
        op, payload = ws.receive()
        self.assertEqual((op, payload), (herdr_web.OP_BIN, b"hello"))

    def test_126_length_frame(self):
        payload = b"x" * 200
        ws = herdr_web.WebSocket(RecordingSocket(), BytesIO(mask_frame(herdr_web.OP_BIN, payload)))
        self.assertEqual(ws.receive(), (herdr_web.OP_BIN, payload))

    def test_127_length_frame(self):
        payload = b"y" * 70000
        ws = herdr_web.WebSocket(RecordingSocket(), BytesIO(mask_frame(herdr_web.OP_BIN, payload)))
        self.assertEqual(ws.receive(), (herdr_web.OP_BIN, payload))

    def test_fragmented_message_reassembled(self):
        frames = mask_frame(herdr_web.OP_BIN, b"ab", fin=False) + mask_frame(herdr_web.OP_CONT, b"cd")
        ws = herdr_web.WebSocket(RecordingSocket(), BytesIO(frames))
        self.assertEqual(ws.receive(), (herdr_web.OP_BIN, b"abcd"))

    def test_ping_answered_with_pong_then_close_returned(self):
        sock = RecordingSocket()
        frames = mask_frame(herdr_web.OP_PING, b"p") + mask_frame(herdr_web.OP_CLOSE, b"")
        ws = herdr_web.WebSocket(sock, BytesIO(frames))
        self.assertEqual(ws.receive(), (herdr_web.OP_CLOSE, b""))
        fin, op, payload = read_server_frame(BytesIO(bytes(sock.sent)))
        self.assertEqual((op, payload), (herdr_web.OP_PONG, b"p"))

    def test_send_encodes_126_and_127_lengths(self):
        sock = RecordingSocket()
        ws = herdr_web.WebSocket(sock, BytesIO(b""))
        ws.send(herdr_web.OP_BIN, b"x" * 200)
        ws.send(herdr_web.OP_BIN, b"y" * 70000)
        rfile = BytesIO(bytes(sock.sent))
        self.assertEqual(read_server_frame(rfile)[2], b"x" * 200)
        self.assertEqual(read_server_frame(rfile)[2], b"y" * 70000)


class AcceptKeyTests(unittest.TestCase):
    def test_rfc6455_sample_key(self):
        self.assertEqual(herdr_web.accept_key("dGhlIHNhbXBsZSBub25jZQ=="), "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")


class SameOriginTests(unittest.TestCase):
    def test_matching_and_mismatching_netloc(self):
        self.assertTrue(herdr_web.same_origin("http://127.0.0.1:9", "127.0.0.1:9"))
        self.assertFalse(herdr_web.same_origin("http://evil.example:9", "127.0.0.1:9"))
        self.assertFalse(herdr_web.same_origin("", "127.0.0.1:9"))


def git_repo(path):
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "init"], check=True)
    return path


class HerdrClientServerTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="fsa-dash-herdr-web-")
        base = Path(self.scratch.name)
        self.home = git_repo(base / "home")
        self.bin = base / "bin"
        self.bin.mkdir()
        herdr_path = self.bin / "herdr"
        herdr_path.write_text(FAKE_HERDR)
        herdr_path.chmod(herdr_path.stat().st_mode | stat.S_IEXEC)
        self.env = mock.patch.dict(os.environ, {"PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}"})
        self.env.start()
        self.server = dash.Server(("127.0.0.1", 0), dash.Repo(str(self.home), None, None), "t")
        self.server.herdr_state = lambda: {"running": True, "workspaces": [], "tabs": [],
                                            "focused_pane_id": None, "agent_kinds": [], "panes": []}
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(5)
        self.server.server_close()
        self.env.stop()
        self.scratch.cleanup()

    def request(self, path, upgrade=True, origin=None):
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        host = f"127.0.0.1:{self.port}"
        headers = [f"GET {path} HTTP/1.1", f"Host: {host}"]
        if upgrade:
            headers += ["Upgrade: websocket", "Connection: Upgrade",
                        "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==", "Sec-WebSocket-Version: 13",
                        f"Origin: {origin if origin is not None else 'http://' + host}"]
        sock.sendall(("\r\n".join(headers) + "\r\n\r\n").encode())
        rfile = sock.makefile("rb")
        status = int(rfile.readline().split(b" ", 2)[1])
        headers_out = {}
        while True:
            line = rfile.readline().strip()
            if not line:
                break
            k, v = line.decode().split(":", 1)
            headers_out[k.strip().lower()] = v.strip()
        if status != 101:
            length = int(headers_out.get("content-length", 0))
            if length:
                rfile.read(length)
            sock.close()
        return sock, rfile, status, headers_out

    def connect(self, cols=80, rows=24, token="t"):
        sock, rfile, status, headers = self.request(f"/api/herdr/client?cols={cols}&rows={rows}&t={token}")
        self.assertEqual(status, 101)
        sock.settimeout(20)
        return sock, rfile

    def collect_until(self, rfile, needle, timeout=20):
        seen, deadline = b"", time.monotonic() + timeout
        while needle not in seen and time.monotonic() < deadline:
            try:
                _, _, payload = read_server_frame(rfile)
            except (TimeoutError, OSError):
                continue
            seen += payload
        return seen

    def test_echo_round_trip_and_argv_has_no_session_flag_and_term_set(self):
        sock, rfile = self.connect()
        try:
            sock.sendall(mask_frame(herdr_web.OP_BIN, b"hi\n"))
            seen = self.collect_until(rfile, b"ECHO:hi").decode()
            self.assertIn("ARGV:" + str(self.bin / "herdr"), seen)
            self.assertNotIn("--session", seen)
            self.assertIn("TERM:xterm-256color", seen)
            self.assertIn("ECHO:hi", seen)
        finally:
            sock.close()

    def test_initial_size_set_before_child_execs(self):
        sock, rfile = self.connect(cols=91, rows=33)
        try:
            seen = self.collect_until(rfile, b"INIT:33 91").decode()
            self.assertIn("INIT:33 91", seen)
        finally:
            sock.close()

    def test_resize_frame_changes_pty_size(self):
        sock, rfile = self.connect(cols=80, rows=24)
        try:
            sock.sendall(mask_frame(herdr_web.OP_TEXT, b'{"type":"resize","cols":120,"rows":40}'))
            sock.sendall(mask_frame(herdr_web.OP_BIN, b"SIZE\n"))
            seen = self.collect_until(rfile, b"40 120").decode()
            self.assertIn("40 120", seen)
        finally:
            sock.close()

    def test_child_is_reaped_after_client_closes(self):
        sock, rfile = self.connect()
        sock.sendall(mask_frame(herdr_web.OP_CLOSE, b""))
        # stop_child() waitpid's the child before the server answers with its own close frame
        op, deadline = None, time.monotonic() + 20
        while op != herdr_web.OP_CLOSE and time.monotonic() < deadline:
            try:
                _, op, _ = read_server_frame(rfile)
            except (TimeoutError, OSError):
                continue
        self.assertEqual(op, herdr_web.OP_CLOSE)
        sock.close()
        # the slot released in herdr_client()'s finally must be free for a fresh connection
        sock2, _ = self.connect()
        sock2.close()

    def test_forbidden_without_token(self):
        _, _, status, _ = self.request("/api/herdr/client?cols=80&rows=24&t=wrong")
        self.assertEqual(status, 403)

    def test_bad_request_without_upgrade_header(self):
        _, _, status, _ = self.request("/api/herdr/client?cols=80&rows=24&t=t", upgrade=False)
        self.assertEqual(status, 400)

    def test_bad_request_on_cross_origin(self):
        _, _, status, _ = self.request("/api/herdr/client?cols=80&rows=24&t=t", origin="http://evil.example")
        self.assertEqual(status, 400)

    def test_bad_request_on_missing_or_out_of_range_size(self):
        _, _, status, _ = self.request("/api/herdr/client?t=t")
        self.assertEqual(status, 400)
        _, _, status, _ = self.request("/api/herdr/client?cols=5&rows=24&t=t")
        self.assertEqual(status, 400)
        _, _, status, _ = self.request("/api/herdr/client?cols=80&rows=1000&t=t")
        self.assertEqual(status, 400)

    def test_service_unavailable_when_herdr_not_running(self):
        self.server.herdr_state = lambda: {"running": False, "workspaces": [], "tabs": [],
                                            "focused_pane_id": None, "agent_kinds": [], "panes": []}
        _, _, status, _ = self.request("/api/herdr/client?cols=80&rows=24&t=t")
        self.assertEqual(status, 503)

    def test_service_unavailable_when_herdr_binary_missing(self):
        with mock.patch.object(dash.shutil, "which", return_value=None):
            _, _, status, _ = self.request("/api/herdr/client?cols=80&rows=24&t=t")
        self.assertEqual(status, 503)

    def test_too_many_clients_returns_429(self):
        for _ in range(dash.HERDR_CLIENT_MAX):
            self.server.herdr_client_slots.acquire(blocking=False)
        try:
            _, _, status, _ = self.request("/api/herdr/client?cols=80&rows=24&t=t")
            self.assertEqual(status, 429)
        finally:
            for _ in range(dash.HERDR_CLIENT_MAX):
                self.server.herdr_client_slots.release()

    def post_file(self, path, body=b"hello", length=None, token="t"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Content-Type": "application/octet-stream", "Cookie": f"fsa_t={token}"}
        if length is not None:
            headers["Content-Length"] = length
        conn.request("POST", path, body=body, headers=headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, data

    def test_file_upload_stages_without_live_session(self):
        status, data = self.post_file("/api/herdr/file?name=note.txt")
        self.assertEqual(status, 200)
        path = Path(json.loads(data)["path"])
        self.addCleanup(path.unlink, missing_ok=True)
        self.assertEqual(path.read_bytes(), b"hello")

    def test_file_upload_forbidden_without_token(self):
        status, _ = self.post_file("/api/herdr/file?name=note.txt", token="wrong")
        self.assertEqual(status, 403)

    def test_file_upload_rejects_bad_content_length(self):
        status, _ = self.post_file("/api/herdr/file?name=note.txt", length="abc")
        self.assertEqual(status, 413)

    def test_static_assets_served(self):
        paths = ["/static/xterm/addon-webgl.js", "/static/fonts/JetBrainsMono-Regular.woff2",
                 "/static/fonts/JetBrainsMono-Bold.woff2", "/static/fonts/JetBrainsMono-Italic.woff2",
                 "/static/fonts/JetBrainsMono-BoldItalic.woff2"]
        for path in paths:
            _, _, status, headers = self.request(f"{path}?t=t", upgrade=False)
            self.assertEqual(status, 200, path)
            if path.endswith(".js"):
                self.assertEqual(headers["content-type"], "application/javascript", path)
            else:
                self.assertEqual(headers["content-type"], "font/woff2", path)


if __name__ == "__main__":
    unittest.main()
