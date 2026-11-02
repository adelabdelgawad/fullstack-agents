#!/usr/bin/env python3
"""WebSocket frame codec and pty plumbing for a full herdr terminal served over one connection."""
import fcntl
import hashlib
import base64
import json
import os
import signal
import struct
import termios
import threading
import time
import urllib.parse

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
OP_CONT, OP_TEXT, OP_BIN, OP_CLOSE, OP_PING, OP_PONG = 0, 1, 2, 8, 9, 10
MAX_MESSAGE = 1 << 20


def unmask(data, mask):
    n = len(data)
    key = (mask * (n // 4 + 1))[:n]
    return (int.from_bytes(data, "big") ^ int.from_bytes(key, "big")).to_bytes(n, "big")


def accept_key(key):
    return base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()


def same_origin(origin, host):
    netloc = urllib.parse.urlsplit(origin).netloc
    return bool(netloc) and netloc == host


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


def spawn_herdr(path, cols, rows):
    env = {k: v for k, v in os.environ.items() if not k.startswith("HERDR_")}
    env.update(TERM="xterm-256color", COLORTERM="truecolor")
    master, slave = os.openpty()
    set_size(master, cols, rows)
    pid = os.fork()
    if pid == 0:
        try:
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
            os.dup2(slave, 0)
            os.dup2(slave, 1)
            os.dup2(slave, 2)
            os.close(master)
            if slave > 2:
                os.close(slave)
            os.execve(path, [path], env)
        finally:
            os._exit(127)
    os.close(slave)
    return pid, master


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


def stop_child(pid, fd, reader=None):
    for sig in (signal.SIGHUP, signal.SIGKILL):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            break
        if reaped(pid, 2.0):
            break
    # The reader must be gone before the fd number can be reused by another thread.
    if reader is not None:
        reader.join(2.0)
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
