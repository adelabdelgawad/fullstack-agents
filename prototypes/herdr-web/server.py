#!/usr/bin/env python3
"""Prototype: a full herdr client in the browser over one WebSocket, rendered by xterm.js or ghostty-web."""
import argparse
import base64
import fcntl
import hashlib
import http.server
import json
import os
import pty
import re
import secrets
import signal
import struct
import termios
import threading
import time
import urllib.parse
from http.cookies import SimpleCookie
from pathlib import Path

HERE = Path(__file__).resolve().parent
XTERM = HERE.parent.parent / "plugins/fullstack-agents/scripts/lib/vendor/xterm"
GHOSTTY = HERE / "vendor/ghostty-web"
STATIC = {
    "/vendor/xterm/xterm.js": (XTERM / "xterm.js", "text/javascript"),
    "/vendor/xterm/xterm.css": (XTERM / "xterm.css", "text/css"),
    "/vendor/xterm/addon-fit.js": (XTERM / "addon-fit.js", "text/javascript"),
    "/vendor/xterm/addon-webgl.js": (HERE / "vendor/xterm-webgl/addon-webgl.js", "text/javascript"),
    "/vendor/jbm/JetBrainsMono-Regular.woff2": (HERE / "vendor/jetbrains-mono/JetBrainsMono-Regular.woff2", "font/woff2"),
    "/vendor/jbm/JetBrainsMono-Bold.woff2": (HERE / "vendor/jetbrains-mono/JetBrainsMono-Bold.woff2", "font/woff2"),
    "/vendor/jbm/JetBrainsMono-Italic.woff2": (HERE / "vendor/jetbrains-mono/JetBrainsMono-Italic.woff2", "font/woff2"),
    "/vendor/jbm/JetBrainsMono-BoldItalic.woff2": (HERE / "vendor/jetbrains-mono/JetBrainsMono-BoldItalic.woff2", "font/woff2"),
    "/vendor/ghostty-web/ghostty-web.js": (GHOSTTY / "ghostty-web.js", "text/javascript"),
    "/vendor/ghostty-web/__vite-browser-external-2447137e.js":
        (GHOSTTY / "__vite-browser-external-2447137e.js", "text/javascript"),
}
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
OP_CONT, OP_TEXT, OP_BIN, OP_CLOSE, OP_PING, OP_PONG = 0, 1, 2, 8, 9, 10
MAX_MESSAGE = 1 << 20
MAX_CLIENTS = 4
SESSION_NAME = re.compile(r"[A-Za-z0-9_.-]{1,64}")


def unmask(data, mask):
    n = len(data)
    key = (mask * (n // 4 + 1))[:n]
    return (int.from_bytes(data, "big") ^ int.from_bytes(key, "big")).to_bytes(n, "big")


class WebSocket:
    def __init__(self, sock, rfile):
        self.sock, self.rfile = sock, rfile
        self.lock = threading.Lock()
        self.closed = False

    def read(self, n):
        data = self.rfile.read(n)
        if len(data) < n:
            raise ConnectionError("client closed")
        return data

    def frame(self):
        head = self.read(2)
        fin, op = head[0] & 0x80, head[0] & 0x0F
        size = head[1] & 0x7F
        if size == 126:
            size = struct.unpack("!H", self.read(2))[0]
        elif size == 127:
            size = struct.unpack("!Q", self.read(8))[0]
        if not head[1] & 0x80 or size > MAX_MESSAGE:
            raise ConnectionError("unmasked or oversized frame")
        mask = self.read(4)
        return bool(fin), op, unmask(self.read(size), mask)

    def receive(self):
        """Next data message as (opcode, payload); answers pings, returns (OP_CLOSE, b"") on close."""
        kind, parts = None, bytearray()
        while True:
            fin, op, data = self.frame()
            if op == OP_PING:
                self.send(OP_PONG, data)
            elif op == OP_CLOSE:
                return OP_CLOSE, b""
            elif op in (OP_TEXT, OP_BIN, OP_CONT):
                kind = op if op != OP_CONT else kind
                parts += data
                if len(parts) > MAX_MESSAGE:
                    raise ConnectionError("message too large")
                if fin:
                    return kind, bytes(parts)

    def send(self, op, data=b""):
        n = len(data)
        if n < 126:
            head = bytes([0x80 | op, n])
        elif n < 65536:
            head = bytes([0x80 | op, 126]) + struct.pack("!H", n)
        else:
            head = bytes([0x80 | op, 127]) + struct.pack("!Q", n)
        with self.lock:
            if self.closed:
                return
            self.sock.sendall(head + data)
            self.closed = op == OP_CLOSE


def set_size(fd, cols, rows):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def spawn_herdr(session, cols, rows):
    args = ["herdr", "--session", session] if session else ["herdr"]
    env = {k: v for k, v in os.environ.items() if not k.startswith("HERDR_")}
    env.update(TERM="xterm-256color", COLORTERM="truecolor")
    pid, fd = pty.fork()
    if pid == 0:
        try:
            set_size(0, cols, rows)
            os.execvpe(args[0], args, env)
        finally:
            os._exit(127)
    return pid, fd


def reaped(pid, wait):
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        try:
            if os.waitpid(pid, os.WNOHANG)[0]:
                return True
        except ChildProcessError:
            return True
        time.sleep(0.05)
    return False


def stop_child(pid, fd):
    for sig in (signal.SIGHUP, signal.SIGKILL):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            break
        if reaped(pid, 2.0):
            break
    try:
        os.close(fd)
    except OSError:
        pass


def pump_output(fd, ws):
    while True:
        try:
            data = os.read(fd, 65536)
        except OSError:
            data = b""
        if not data:
            break
        try:
            ws.send(OP_BIN, data)
        except OSError:
            return
    try:
        ws.send(OP_CLOSE, struct.pack("!H", 1000) + b"herdr exited")
    except OSError:
        pass


def write_all(fd, data):
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view):]


def apply_control(fd, payload):
    message = json.loads(payload)
    if message.get("type") == "resize":
        cols, rows = int(message["cols"]), int(message["rows"])
        if 10 <= cols <= 500 and 5 <= rows <= 200:
            set_size(fd, cols, rows)


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "herdr-web-proto"

    def log_message(self, fmt, *args):
        if self.server.verbose:
            super().log_message(fmt, *args)

    def authorised(self, query):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        given = (query.get("t") or [""])[0] or (cookie["hwp_t"].value if "hwp_t" in cookie else "")
        return secrets.compare_digest(given, self.server.token)

    def send_body(self, code, body, kind="text/plain; charset=utf-8", headers=()):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(url.query)
        if url.path in STATIC:
            path, kind = STATIC[url.path]
            return self.send_body(200, path.read_bytes(), kind)
        if not self.authorised(query):
            return self.send_body(403, b"open the URL the server printed (it carries the token)")
        if url.path == "/":
            cookie = f"hwp_t={self.server.token}; HttpOnly; SameSite=Strict; Path=/"
            return self.send_body(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8",
                                  [("Set-Cookie", cookie)])
        if url.path == "/ws":
            return self.websocket(query)
        self.send_body(404, b"not found")

    def same_origin(self):
        origin = urllib.parse.urlsplit(self.headers.get("Origin", ""))
        return origin.netloc and origin.netloc == self.headers.get("Host")

    def upgrade(self):
        key = self.headers.get("Sec-WebSocket-Key", "")
        accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        self.wfile.flush()
        self.close_connection = True
        return WebSocket(self.connection, self.rfile)

    def websocket(self, query):
        if self.headers.get("Upgrade", "").lower() != "websocket" or not self.same_origin():
            return self.send_body(400, b"same-origin websocket upgrade required")
        try:
            cols, rows = int(query["cols"][0]), int(query["rows"][0])
        except (KeyError, ValueError):
            return self.send_body(400, b"cols and rows required")
        session = (query.get("session") or [""])[0]
        if not (10 <= cols <= 500 and 5 <= rows <= 200) or (session and not SESSION_NAME.fullmatch(session)):
            return self.send_body(400, b"bad size or session name")
        if not self.server.slots.acquire(blocking=False):
            return self.send_body(429, b"too many clients")
        try:
            self.serve_terminal(self.upgrade(), session, cols, rows)
        finally:
            self.server.slots.release()

    def serve_terminal(self, ws, session, cols, rows):
        pid, fd = spawn_herdr(session, cols, rows)
        threading.Thread(target=pump_output, args=(fd, ws), daemon=True).start()
        try:
            while True:
                op, payload = ws.receive()
                if op == OP_CLOSE:
                    break
                if op == OP_BIN:
                    write_all(fd, payload)
                elif op == OP_TEXT:
                    apply_control(fd, payload)
        except (ConnectionError, OSError, ValueError, KeyError):
            pass
        finally:
            stop_child(pid, fd)
            try:
                ws.send(OP_CLOSE, struct.pack("!H", 1000))
            except OSError:
                pass


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, token, verbose):
        super().__init__(addr, Handler)
        self.token, self.verbose = token, verbose
        self.slots = threading.BoundedSemaphore(MAX_CLIENTS)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to reach it from another machine")
    ap.add_argument("--port", type=int, default=7682)
    ap.add_argument("--token", default=os.environ.get("HERDR_WEB_TOKEN") or secrets.token_urlsafe(24))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    server = Server((args.host, args.port), args.token, args.verbose)
    shown = "localhost" if args.host in ("127.0.0.1", "localhost") else args.host
    print(f"herdr web prototype: http://{shown}:{args.port}/?t={args.token}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
