"""Linked dashboards ("nodes"): the registry, the authenticated proxy to a linked host and the folder listing.

A node is another host's fsa-dashboard. Its token stays in this host's registry (mode 0600); the browser only ever
talks to this dashboard, which forwards `/api/node/<id>/api/...` to the linked host with the token as its cookie.
"""
import http.client
import json
import os
import re
import socket
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

NODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
HOST_RE = re.compile(r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$"
                     r"|^\[?[0-9A-Fa-f:.]+\]?$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
PROXY_PREFIX = "/api/node/"
TIMEOUT_S = 10
STREAM_PATHS = ("/api/herdr/live",)
FORWARD_HEADERS = ("Content-Type", "X-Screen-Hash", "Cache-Control")
MAX_DIRS = 500
_lock = threading.Lock()
_tunnels = threading.BoundedSemaphore(8)


def registry_path():
    env = os.environ.get("FSA_NODES_FILE")
    if env:
        return Path(env)
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "fullstack-agents" / "nodes.json"


def load():
    try:
        data = json.loads(registry_path().read_text())
    except (OSError, ValueError):
        return []
    return [n for n in data if isinstance(n, dict) and NODE_ID_RE.match(str(n.get("id", "")))] \
        if isinstance(data, list) else []


def _save(nodes):
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(nodes, fh, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def public(nodes=None):
    """The registry without tokens: what the browser may see."""
    return [{k: n[k] for k in ("id", "label", "host", "port")} for n in (load() if nodes is None else nodes)]


def find(node_id):
    return next((n for n in load() if n["id"] == node_id), None)


def validate(body):
    """A link request {url, label?} -> (label, host, port, token); ValueError names what is wrong.

    `url` is the linked host's dashboard URL as its owner opens it, e.g. http://10.0.0.12:8766/?t=TOKEN.
    """
    if not isinstance(body, dict):
        raise ValueError("bad request")
    raw = str(body.get("url") or "").strip()
    if raw and "://" not in raw:
        raw = "http://" + raw
    try:
        url = urlsplit(raw)
        port = url.port or 80
    except ValueError:
        raise ValueError("the URL's port must be 1-65535") from None
    if url.scheme != "http":
        raise ValueError("paste the host's dashboard URL, starting http://")
    host = url.hostname or ""
    if not HOST_RE.match(host) or len(host) > 253:
        raise ValueError("the URL needs an IP address or host name")
    token = (parse_qs(url.query).get("t") or [""])[0].strip()
    if not TOKEN_RE.match(token):
        raise ValueError("the URL needs the dashboard's ?t= token")
    label = re.sub(r"\s+", " ", str(body.get("label") or "").strip())[:40] or host
    return label, host.strip("[]"), port, token


def _slug(label, taken):
    base = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:30] or "host"
    base = base if base != "local" else "host"
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    return slug


def probe(host, port, token):
    """'' when the host answers with this token, else why not."""
    try:
        conn = http.client.HTTPConnection(host, port, timeout=TIMEOUT_S)
        conn.request("GET", "/api/herdr", headers={"Cookie": f"fsa_t={token}"})
        status = conn.getresponse().status
        conn.close()
    except (OSError, http.client.HTTPException) as exc:
        return f"unreachable: {exc}"
    if status == 403:
        return "the host refused this token"
    return "" if status == 200 else f"the host answered HTTP {status}"


def add(body):
    label, host, port, token = validate(body)
    error = probe(host, port, token)
    if error:
        raise ConnectionError(error)
    with _lock:
        nodes = [n for n in load() if not (n["host"] == host and n["port"] == port)]
        node = {"id": _slug(label, {n["id"] for n in nodes}), "label": label, "host": host, "port": port, "token": token}
        _save([*nodes, node])
    return public([node])[0]


def remove(node_id):
    with _lock:
        nodes = load()
        kept = [n for n in nodes if n["id"] != node_id]
        if len(kept) == len(nodes):
            return False
        _save(kept)
    return True


def split_proxy_path(path):
    """'/api/node/<id>/api/x' -> (id, '/api/x'); None when the path is not a proxy path or not allowed."""
    if not path.startswith(PROXY_PREFIX):
        return None
    node_id, _, rest = path[len(PROXY_PREFIX):].partition("/")
    rest = "/" + rest
    if not NODE_ID_RE.match(node_id) or not rest.startswith("/api/") or rest.startswith(PROXY_PREFIX) \
            or rest.startswith("/api/nodes") or ".." in rest.split("/"):
        return None
    return node_id, rest


def forward(handler, node, rest, query, body=None):
    """Forward one GET/POST to the node and copy its answer back; SSE answers stream until either side closes."""
    # A `t=` meant for this dashboard would win over the node's cookie there, so it never leaves this host.
    query = "&".join(p for p in query.split("&") if p and not p.startswith("t=")) if query else ""
    target = rest + (f"?{query}" if query else "")
    headers = {"Cookie": f"fsa_t={node['token']}", "Host": f"{node['host']}:{node['port']}"}
    if body is not None:
        headers["Content-Type"] = handler.headers.get("Content-Type") or "application/json"
        headers["Content-Length"] = str(len(body))
    if handler.headers.get("Accept"):
        headers["Accept"] = handler.headers["Accept"]
    streaming = rest in STREAM_PATHS
    try:
        conn = http.client.HTTPConnection(node["host"], node["port"], timeout=None if streaming else 15)
        conn.request(handler.command, target, body=body, headers=headers)
        resp = conn.getresponse()
    except (OSError, http.client.HTTPException) as exc:
        return handler.send(502, f"{node['label']} is unreachable: {exc}".encode(), "text/plain")
    extra = {k: resp.getheader(k) for k in FORWARD_HEADERS[1:] if resp.getheader(k)}
    ctype = resp.getheader("Content-Type") or "application/octet-stream"
    if not streaming or resp.status != 200:
        data = resp.read()
        conn.close()
        return _send_raw(handler, resp.status, data, ctype, extra)
    handler.close_connection = True
    handler.send_response(200)
    for k, v in {"Content-Type": ctype, "Cache-Control": "no-store", "Connection": "close", **extra}.items():
        handler.send_header(k, v)
    handler.end_headers()
    try:
        while True:
            chunk = resp.read1(65536) if hasattr(resp, "read1") else resp.read(4096)
            if not chunk:
                break
            handler.wfile.write(chunk)
            handler.wfile.flush()
    except OSError:
        pass
    finally:
        conn.close()


def _send_raw(handler, code, body, ctype, extra):
    handler.send_response(code)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(body)))
    if "Cache-Control" not in extra:
        handler.send_header("Cache-Control", "no-store")
    if handler.command == "POST" and not getattr(handler, "body_read", True):
        handler.close_connection = True
        handler.send_header("Connection", "close")
    for k, v in extra.items():
        handler.send_header(k, v)
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except ConnectionError:
        pass


def tunnel_websocket(handler, node, rest, query):
    """Relay a WebSocket upgrade to the node: the node sees its own Host and Origin, so its same-origin check passes."""
    if not _tunnels.acquire(blocking=False):
        return handler.send(429, b"too many remote terminals", "text/plain")
    try:
        _tunnel(handler, node, rest, query)
    finally:
        _tunnels.release()


def _tunnel(handler, node, rest, query):
    hostport = f"{node['host']}:{node['port']}"
    key = handler.headers.get("Sec-WebSocket-Key", "")
    query = "&".join(p for p in query.split("&") if p and not p.startswith("t=")) if query else ""
    request = (f"GET {rest}{'?' + query if query else ''} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
               f"Origin: http://{hostport}\r\nCookie: fsa_t={node['token']}\r\n\r\n")
    try:
        upstream = socket.create_connection((node["host"], node["port"]), timeout=TIMEOUT_S)
        upstream.sendall(request.encode())
        upstream.settimeout(None)
    except OSError as exc:
        return handler.send(502, f"{node['label']} is unreachable: {exc}".encode(), "text/plain")
    handler.close_connection = True
    client = handler.connection
    client.settimeout(None)
    # A browser sends no frame before the 101 answer, so nothing waits in the request buffer.

    def pump(src, dst):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except OSError:
            pass
        finally:
            for s in (src, dst):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    back = threading.Thread(target=pump, args=(upstream, client), daemon=True)
    back.start()
    pump(client, upstream)
    back.join(timeout=5)
    upstream.close()


def list_dirs(path, hidden=False):
    """The sub-folders of one absolute folder, git repositories marked. Names only, never file contents."""
    if not isinstance(path, str) or not path:
        path = str(Path.home())
    if not os.path.isabs(path) or "\x00" in path:
        raise ValueError("path must be absolute")
    real = os.path.realpath(path)
    if not os.path.isdir(real):
        raise FileNotFoundError("not a folder")
    dirs = []
    with os.scandir(real) as entries:
        for entry in entries:
            if not hidden and entry.name.startswith("."):
                continue
            try:
                if not entry.is_dir():
                    continue
            except OSError:
                continue
            full = os.path.join(real, entry.name)
            dirs.append({"name": entry.name, "path": full, "git": os.path.exists(os.path.join(full, ".git"))})
    dirs.sort(key=lambda d: d["name"].lower())
    parent = os.path.dirname(real) if real != "/" else None
    return {"path": real, "parent": parent, "git": os.path.exists(os.path.join(real, ".git")),
            "home": str(Path.home()), "dirs": dirs[:MAX_DIRS], "truncated": len(dirs) > MAX_DIRS}

