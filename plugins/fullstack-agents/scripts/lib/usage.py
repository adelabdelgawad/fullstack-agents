"""Token usage, context fill, compactions and estimated cost read incrementally from agent transcripts."""
import calendar
import json
import os
import re
import threading
import time
from pathlib import Path

PRICE_FILE = Path(os.environ.get("FSA_PRICES") or Path.home() / ".config" / "fullstack-agents" / "prices.json")
DEFAULT_WINDOW = 200_000
SAMPLE_KEEP_S = 600
IDS_KEEP = 4096
BLOWOUT_FILL = 0.9
WARN_FILL = 0.8
DEFAULT_PRICES = {
    "claude-fable-5-1": {"input": 10.0, "output": 50.0, "cache_read": 0.25, "window": 1_000_000},
    "claude-mythos-5-1": {"input": 10.0, "output": 50.0, "cache_read": 0.25, "window": 1_000_000},
    "claude-fable-5": {"input": 10.0, "output": 50.0, "cache_read": 1.0, "window": 1_000_000},
    "claude-opus-5-5": {"input": 4.0, "output": 20.0, "cache_read": 0.2, "window": 1_000_000},
    "claude-opus-5": {"input": 5.0, "output": 25.0, "cache_read": 0.5, "window": 1_000_000},
    "claude-opus-4": {"input": 5.0, "output": 25.0, "cache_read": 0.5, "window": 1_000_000},
    "claude-sonnet-5-5": {"input": 2.0, "output": 10.0, "cache_read": 0.2, "window": 1_000_000},
    "claude-sonnet-5": {"input": 2.0, "output": 10.0, "cache_read": 0.2, "window": 1_000_000},
    "claude-sonnet-4": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "window": 1_000_000},
    "claude-haiku-5-5": {"input": 0.1, "output": 0.5, "cache_read": 0.01, "window": 1_000_000},
    "claude-haiku-4": {"input": 1.0, "output": 5.0, "cache_read": 0.1, "window": 200_000},
}
_CACHE, _LOCK = {}, threading.Lock()
_PRICES = {"mtime": None, "table": DEFAULT_PRICES}

SECRET_RES = [
    (re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----(?:.*?-----END [A-Z ]*PRIVATE KEY-----|[^\"]*)", re.DOTALL), rb"[redacted]"),
    (re.compile(rb"sk-ant-[A-Za-z0-9_-]{8,}"), rb"[redacted]"),
    (re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}"), rb"[redacted]"),
    (re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}"), rb"[redacted]"),
    (re.compile(rb"\bAKIA[0-9A-Z]{16}\b"), rb"[redacted]"),
    (re.compile(rb"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), rb"[redacted]"),
    (re.compile(rb"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]{12,}"), rb"\1[redacted]"),
    (re.compile(rb"(\b[a-z][a-z0-9+.-]*://[^\s:/@\"'\\]*:)[^\s@/\"'\\]+@"), rb"\1[redacted]@"),
    (re.compile(rb"(?i)(\\?\"[a-z0-9_]*(?:secret|password|passwd|token|api_key|private_key)[a-z0-9_]*\\?\"\s*:\s*\\?\")"
                rb"[^\"\\]{6,}"), rb"\1[redacted]"),
    (re.compile(rb"(?i)(\b[A-Z0-9_]*(?:SECRET|PASSWORD|PASSWD|TOKEN|API_KEY|PRIVATE_KEY)[A-Z0-9_]*\s*[=:]\s*)"
                rb"[^\s\"'\\,;]{6,}"), rb"\1[redacted]"),
]


def redact(body):
    """Bytes with secret-shaped strings replaced by [redacted]; JSON stays valid because no pattern spans a quote."""
    for pattern, repl in SECRET_RES:
        body = pattern.sub(repl, body)
    return body


def prices():
    try:
        mtime = PRICE_FILE.stat().st_mtime
    except OSError:
        mtime = None
    if mtime != _PRICES["mtime"]:
        table = dict(DEFAULT_PRICES)
        if mtime is not None:
            try:
                loaded = json.loads(PRICE_FILE.read_text())
                table.update({k: v for k, v in loaded.items() if isinstance(v, dict)})
            except (OSError, ValueError):
                pass
        _PRICES.update(mtime=mtime, table=table)
    return _PRICES["table"]


def price_of(model):
    table = prices()
    key = max((k for k in table if model and model.startswith(k)), key=len, default=None)
    return table.get(key) if key else None


def window_of(model, seen=0):
    window = (price_of(model) or {}).get("window") or DEFAULT_WINDOW
    return 1_000_000 if seen > window else window


def cost_of(model, t):
    p = price_of(model)
    if not p:
        return None
    rate = p["input"]
    return (t["input"] * rate + t["output"] * p["output"] + t["write_5m"] * rate * 1.25
            + t["write_1h"] * rate * 2 + t["cache_read"] * p.get("cache_read", rate * 0.1)) / 1e6


def _blank():
    return {"ino": None, "offset": 0, "ids": [], "seen": set(), "models": {}, "model": "", "context": 0,
            "window": 0, "compactions": 0, "compact_pre": 0, "samples": [], "daily": {}, "codex_prev": {}, "agent": False}


def _iso(ts):
    try:
        return calendar.timegm(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return 0


def _zero():
    return {"input": 0, "output": 0, "write_5m": 0, "write_1h": 0, "cache_read": 0}


def _add(st, model, at, t):
    day = time.strftime("%Y-%m-%d", time.localtime(at or time.time()))
    for totals in (st["models"].setdefault(model, _zero()), st["daily"].setdefault(day, {}).setdefault(model, _zero())):
        for k, v in t.items():
            totals[k] += v
    st["samples"].append((at, t["input"] + t["output"] + t["write_5m"] + t["write_1h"] + t["cache_read"]))


def _claude_line(st, d):
    if d.get("type") == "system" and d.get("subtype") == "compact_boundary":
        st["compactions"] += 1
        st["compact_pre"] = (d.get("compactMetadata") or {}).get("preTokens") or st["compact_pre"]
        st["context"] = (d.get("compactMetadata") or {}).get("postTokens") or 0
        return
    msg = d.get("message") or {}
    u = msg.get("usage")
    if d.get("type") != "assistant" or not isinstance(u, dict):
        return
    key = msg.get("id") or d.get("requestId") or d.get("uuid")
    if key in st["seen"]:
        return
    st["seen"].add(key)
    st["ids"].append(key)
    if len(st["ids"]) > IDS_KEEP:
        st["seen"].discard(st["ids"].pop(0))
    cc = u.get("cache_creation") or {}
    w1h = cc.get("ephemeral_1h_input_tokens") or 0
    t = {"input": u.get("input_tokens") or 0, "output": u.get("output_tokens") or 0,
         "write_1h": w1h, "write_5m": max((u.get("cache_creation_input_tokens") or 0) - w1h, 0),
         "cache_read": u.get("cache_read_input_tokens") or 0}
    model = msg.get("model") or st["model"]
    if model and not model.startswith("<"):
        st["model"] = model
    _add(st, st["model"], _iso(d.get("timestamp")), t)
    if st["agent"] or not d.get("isSidechain"):
        st["context"] = t["input"] + t["write_5m"] + t["write_1h"] + t["cache_read"]


def _codex_line(st, d):
    p = d.get("payload") or {}
    if d.get("type") == "turn_context" and isinstance(p.get("model"), str):
        st["model"] = p["model"]
        return
    if p.get("type") != "token_count" or not isinstance(p.get("info"), dict):
        return
    info = p["info"]
    last, total = info.get("last_token_usage") or {}, info.get("total_token_usage") or {}
    st["context"] = last.get("input_tokens") or 0
    st["window"] = info.get("model_context_window") or st["window"]
    cached = total.get("cached_input_tokens") or 0
    now_t = {"input": max((total.get("input_tokens") or 0) - cached, 0), "output": total.get("output_tokens") or 0,
             "write_5m": 0, "write_1h": total.get("cache_write_input_tokens") or 0, "cache_read": cached}
    prev = st["codex_prev"]
    delta = {k: max(v - prev.get(k, 0), 0) for k, v in now_t.items()}
    st["codex_prev"] = now_t
    if any(delta.values()):
        _add(st, st["model"], _iso(d.get("timestamp")), delta)


def _scan(path, engine):
    try:
        info = os.stat(path)
    except OSError:
        return None
    with _LOCK:
        st = _CACHE.get(str(path))
        if st is None or st["ino"] != info.st_ino or info.st_size < st["offset"]:
            st = _CACHE[str(path)] = _blank()
            st["ino"], st["agent"] = info.st_ino, engine == "claude-agent"
        if info.st_size == st["offset"]:
            return st
        with open(path, "rb") as f:
            f.seek(st["offset"])
            chunk = f.read(info.st_size - st["offset"])
        end = chunk.rfind(b"\n") + 1
        st["offset"] += end
        claude = engine != "codex"
        marks = (b'"usage"', b"compact_boundary") if claude else (b"token_count", b"turn_context")
        handle = _claude_line if claude else _codex_line
        for line in chunk[:end].splitlines():
            if not any(m in line for m in marks):
                continue
            try:
                handle(st, json.loads(line))
            except (ValueError, AttributeError, TypeError):
                continue
        cutoff = time.time() - SAMPLE_KEEP_S
        st["samples"] = [s for s in st["samples"] if s[0] >= cutoff]
        return st


def _summary(st, now):
    tokens = sum(sum(t.values()) for t in st["models"].values())
    costs = [cost_of(m, t) for m, t in st["models"].items()]
    cost = sum(c for c in costs if c is not None) if any(c is not None for c in costs) else None
    window = st["window"] or window_of(st["model"], st["context"])
    fill = min(st["context"] / window, 1.0) if window else 0.0
    return {"model": st["model"], "tokens": tokens, "cost": cost, "context": st["context"], "window": window,
            "fill": round(fill, 4), "compactions": st["compactions"], "compact_pre": st["compact_pre"],
            "tpm": sum(n for at, n in st["samples"] if now - at <= 60),
            "today": _today(st, now), "blowout": st["compactions"] > 0 or fill >= BLOWOUT_FILL}


def _today(st, now):
    models = st["daily"].get(time.strftime("%Y-%m-%d", time.localtime(now)), {})
    costs = [c for c in (cost_of(m, t) for m, t in models.items()) if c is not None]
    return {"tokens": sum(sum(t.values()) for t in models.values()), "cost": sum(costs) if costs else None}


def _agent_label(meta):
    try:
        d = json.loads(meta.read_text())
    except (OSError, ValueError):
        return ""
    return " · ".join(x for x in (str(d.get("agentType", "")).split(":")[-1], d.get("description", "")) if x)


def _sum_costs(values):
    known = [v for v in values if v is not None]
    return sum(known) if known else None


def transcript_usage(path, engine="claude", now=None):
    """Usage summary of one transcript, or None when it cannot be read."""
    st = _scan(path, engine)
    return _summary(st, now or time.time()) if st else None


def session_usage(path, now=None):
    """Lead usage plus its subagents' tokens and cost; context fill stays the lead's own."""
    now = now or time.time()
    lead = transcript_usage(path, "claude", now)
    if not lead:
        return None
    agents = {}
    for log in sorted(Path(path).with_suffix("").glob("subagents/*.jsonl")):
        u = transcript_usage(log, "claude-agent", now)
        if u:
            u["label"] = _agent_label(log.with_name(log.stem + ".meta.json"))
            agents[log.stem.removeprefix("agent-")] = u
    sub_cost = [a["cost"] for a in agents.values() if a["cost"] is not None]
    lead["agents"] = {k: {f: v[f] for f in ("model", "tokens", "cost", "fill", "compactions", "label")} for k, v in agents.items()}
    lead["agent_tokens"] = sum(a["tokens"] for a in agents.values())
    lead["agent_cost"] = sum(sub_cost) if sub_cost else None
    lead["total_cost"] = None if lead["cost"] is None and not sub_cost else (lead["cost"] or 0) + sum(sub_cost)
    lead["tpm"] += sum(a["tpm"] for a in agents.values())
    lead["today"] = {"tokens": lead["today"]["tokens"] + sum(a["today"]["tokens"] for a in agents.values()),
                     "cost": _sum_costs([lead["today"]["cost"]] + [a["today"]["cost"] for a in agents.values()])}
    return lead
