"""Subscription plan usage: Claude from the account's usage endpoint, Codex from its newest rollout's rate limits."""
import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
CACHE_S = 300
BACKOFF_S = 600
CACHE_FILE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "fullstack-agents" / "claude-plan.json"
BASES = (os.environ.get("CLAUDE_CONFIG_DIR"), "~/.claude", "~/.claude-anthropic")
CODEX_HOME = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
NAMED = {"five_hour": "5 h", "seven_day": "week", "seven_day_opus": "week · Opus", "seven_day_sonnet": "week · Sonnet"}
_LOCK, _CACHE = threading.Lock(), {"at": 0.0, "value": None, "busy": False}


def _credentials():
    for base in dict.fromkeys(b for b in BASES if b):
        path = Path(base).expanduser() / ".credentials.json"
        try:
            oauth = json.loads(path.read_text()).get("claudeAiOauth") or {}
        except (OSError, ValueError):
            continue
        if oauth.get("accessToken"):
            return oauth
    return None


def _fetch_claude():
    oauth = _credentials()
    if not oauth:
        return {"error": "no Claude login found"}
    if (oauth.get("expiresAt") or 0) / 1000 < time.time():
        return {"error": "Claude login expired; any Claude Code session refreshes it"}
    req = urllib.request.Request(USAGE_URL, headers={"Authorization": "Bearer " + oauth["accessToken"],
                                                     "anthropic-beta": "oauth-2025-04-20", "User-Agent": "fsa-dashboard"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        wait = int(e.headers.get("Retry-After") or 0) if str(e.headers.get("Retry-After") or "").isdigit() else 0
        return {"error": f"usage endpoint unavailable ({e.code})", "retry_after": max(wait, BACKOFF_S) if e.code == 429 else BACKOFF_S}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"error": f"usage endpoint unavailable ({type(e).__name__})", "retry_after": BACKOFF_S}
    windows = [{"name": label, "pct": float(w["utilization"]), "resets_at": w.get("resets_at") or ""}
               for key, label in NAMED.items() if isinstance(w := data.get(key), dict) and w.get("utilization") is not None]
    return {"plan": oauth.get("subscriptionType") or "", "windows": windows}


def _read_shared():
    try:
        return json.loads(CACHE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _write_shared(data):
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(CACHE_FILE)
    except OSError:
        pass


def _due(shared, now):
    return now >= max(shared.get("at", 0) + CACHE_S, shared.get("retry_at", 0))


def _refresh():
    """One fetch shared by every dashboard and fsa-usage through the cache file; a failure keeps the last good value."""
    now, shared = time.time(), _read_shared()
    if _due(shared, now):
        value = _fetch_claude()
        shared["at"] = now
        if value.get("windows") is not None:
            shared.update(good=value, good_at=now, error="", retry_at=0)
        else:
            shared.update(error=value.get("error", ""), retry_at=now + value.get("retry_after", BACKOFF_S))
        _write_shared(shared)
    with _LOCK:
        _CACHE.update(at=time.time(), value=_present(shared), busy=False)


def _present(shared):
    good = shared.get("good")
    if not good:
        return {"error": shared.get("error") or "loading plan usage"}
    if shared.get("error"):
        return {**good, "stale": f"as of {max(1, round((time.time() - shared.get('good_at', 0)) / 60))} min ago · {shared['error']}"}
    return good


def claude_plan(wait=False):
    """Plan usage from the shared cache; a due refresh runs in the background unless `wait` asks for it inline."""
    with _LOCK:
        stale = _CACHE["value"] is None or time.time() - _CACHE["at"] > 30
        start = stale and not _CACHE["busy"]
        if start:
            _CACHE["busy"] = True
    if start and wait:
        _refresh()
    elif start:
        threading.Thread(target=_refresh, daemon=True).start()
    return _CACHE["value"] or _present(_read_shared())


def _window(limit, label):
    if not isinstance(limit, dict) or limit.get("used_percent") is None:
        return None
    resets = limit.get("resets_at")
    iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(resets)) if isinstance(resets, (int, float)) else ""
    return {"name": label, "pct": float(limit["used_percent"]), "resets_at": iso}


def codex_plan():
    """Rate limits from the newest Codex rollout's last token_count event."""
    rollouts = sorted(CODEX_HOME.glob("sessions/*/*/*/rollout-*.jsonl"), key=lambda p: p.stat().st_mtime)[-1:]
    for path in rollouts:
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(f.tell() - 262144, 0))
            lines = f.read().decode(errors="replace").splitlines()
        for line in reversed(lines):
            if '"rate_limits"' not in line:
                continue
            try:
                limits = (json.loads(line).get("payload") or {}).get("rate_limits") or {}
            except ValueError:
                continue
            windows = [w for w in (_window(limits.get("primary"), "5 h"), _window(limits.get("secondary"), "week")) if w]
            if windows:
                return {"plan": limits.get("plan_type") or "", "windows": windows}
    return {"error": "no Codex rate limits recorded yet"}


def plan_usage(wait=False):
    return {"claude": claude_plan(wait), "codex": codex_plan()}
