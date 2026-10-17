"""Board-wide totals, session history, run failure causes and the in-memory activity feed."""
import calendar
import re
import threading
import time
from collections import deque

FEED_MAX = 150
LIVE_S = 3600
HISTORY_MAX = 80
CAUSE_TAIL = 16384
CAUSE_RE = re.compile(r"(?i)\b(error|failed|failure|panic|refused|denied|traceback|exception|out_of_scope|timed? ?out)\b")
STATE_TEXT = {"waiting": ("waiting on you", "warn"), "working": ("working", "ok"), "quiet": ("stale: no output for 5 min", "warn"),
              "idle": ("finished a turn", "info"), "still_open": ("left open", "info")}
RUN_TEXT = {"done": ("finished", "ok"), "failed": ("failed", "bad"), "stalled": ("stalled", "warn"), "abandoned": ("abandoned", "bad")}


def _sum(values):
    known = [v for v in values if v is not None]
    return sum(known) if known else None


def card_usage(sessions):
    uses = [s["usage"] for s in sessions if s.get("usage")]
    if not uses:
        return None
    lead = max(uses, key=lambda u: u["fill"])
    return {"cost": _sum(u.get("total_cost", u["cost"]) for u in uses), "tokens": sum(u["tokens"] + u.get("agent_tokens", 0) for u in uses),
            "fill": lead["fill"], "context": lead["context"], "window": lead["window"], "model": lead["model"],
            "compactions": max(u["compactions"] for u in uses), "blowout": any(u["blowout"] for u in uses),
            "tpm": sum(u["tpm"] for u in uses)}


def _live(s, now):
    return s.get("state") in ("working", "waiting", "quiet") or now - (s.get("updated") or 0) < LIVE_S


def totals(shown, every, runs, now):
    """Counts follow the sessions the board shows; spend covers every session of the repository."""
    live = [s for s in shown if _live(s, now)]
    uses = [s["usage"] for s in every if s.get("usage")]
    return {
        "live": len(live), "working": sum(s["state"] == "working" for s in live),
        "waiting": sum(s["state"] == "waiting" for s in live), "stale": sum(s["state"] == "quiet" for s in live),
        "workers": sum(a.get("state") == "running" for s in live for a in s.get("agents", []))
        + sum(r["state"] == "running" for r in runs),
        "failed": sum(r["state"] == "failed" for r in runs),
        "blowouts": sum(bool(s.get("usage") and s["usage"]["blowout"]) for s in live),
        "cost_today": _sum(u["today"]["cost"] for u in uses), "tokens_today": sum(u["today"]["tokens"] for u in uses),
        "unpriced_today": sum(u["today"]["tokens"] for u in uses if u["today"]["cost"] is None),
        "tpm": sum(u["tpm"] for u in uses),
    }


def history_rows(sessions):
    rows = []
    for s in sorted(sessions, key=lambda s: -(s.get("updated") or 0))[:HISTORY_MAX]:
        u = s.get("usage") or {}
        rows.append({"id": s["id"], "name": s.get("name", ""), "engine": s.get("engine") or "claude",
                     "model": u.get("model") or s.get("model", ""), "state": s.get("state", ""),
                     "updated": s.get("updated") or 0, "branch": s.get("branch", ""), "cwd": s.get("cwd", ""),
                     "cost": u.get("total_cost", u.get("cost")), "tokens": u.get("tokens", 0) + u.get("agent_tokens", 0),
                     "fill": u.get("fill", 0), "compactions": u.get("compactions", 0)})
    return rows


def run_cause(log, result):
    """Last error-shaped line of a run log, else the first open risk the run reported."""
    try:
        with open(log, "rb") as f:
            f.seek(0, 2)
            f.seek(max(f.tell() - CAUSE_TAIL, 0))
            lines = f.read().decode(errors="replace").splitlines()
    except OSError:
        lines = []
    hit = next((x.strip() for x in reversed(lines) if CAUSE_RE.search(x) and x.strip()), "")
    risks = (result or {}).get("open_risks") or []
    return (hit or (str(risks[0]) if risks else ""))[:300]


class ActivityFeed:
    """Events derived by diffing consecutive board states; only the latest FEED_MAX are kept in memory."""

    def __init__(self):
        self.lock, self.events, self.prev, self.runs, self.board = threading.Lock(), deque(maxlen=FEED_MAX), None, {}, set()

    def _emit(self, at, tone, who, text, key=""):
        self.events.appendleft({"at": at, "tone": tone, "who": who, "text": text, "key": key})

    def _sessions(self, st):
        out = {}
        for c in st.get("cards", []):
            uses = {s["id"]: s.get("usage") for s in c.get("sessions", [])}
            for s in c.get("now", []):
                u = uses.get(s["id"]) or {}
                out[s["id"]] = {"name": s.get("name", ""), "state": s.get("state", ""), "key": c["key"],
                                "compactions": u.get("compactions", 0), "hot": u.get("fill", 0) >= 0.8,
                                "agents": {a["id"]: (a.get("state"), a.get("label", "")) for a in s.get("agents", [])}}
        return out

    def _board(self, st):
        for e in st.get("events", []):
            ident = (e.get("at"), e.get("session"), e.get("text") or e.get("note"))
            if ident in self.board:
                continue
            self.board.add(ident)
            text = e.get("text") or e.get("note") or e.get("kind") or ""
            at = _epoch(e.get("at")) or time.time()
            if text:
                self._emit(at, "info", e.get("name") or "board", text)

    def _diff_session(self, sid, now_s, now):
        old = self.prev.get(sid)
        who, key = now_s["name"], now_s["key"]
        if old is None:
            self._emit(now, "info", who, "session started", key)
            return
        if now_s["state"] != old["state"] and now_s["state"] in STATE_TEXT:
            text, tone = STATE_TEXT[now_s["state"]]
            self._emit(now, tone, who, text, key)
        if now_s["compactions"] > old["compactions"]:
            self._emit(now, "bad", who, f"context compacted ({now_s['compactions']}×)", key)
        elif now_s["hot"] and not old["hot"]:
            self._emit(now, "warn", who, "context above 80%", key)
        for aid, (state, label) in now_s["agents"].items():
            before = old["agents"].get(aid)
            if before is None and state == "running":
                self._emit(now, "info", who, f"spawned {label or 'subagent'}", key)
            elif before and before[0] == "running" and state != "running":
                self._emit(now, "ok" if state == "completed" else "bad", who, f"{label or 'subagent'} {state}", key)

    def _diff_runs(self, st, now, seed):
        for c in st.get("cards", []):
            for r in c.get("runs", []):
                old = self.runs.get(r["id"])
                self.runs[r["id"]] = r["state"]
                if seed or old == r["state"]:
                    continue
                name = f"{r['mode']} {r.get('unit') or r['id']}"
                if old is None and r["state"] == "running":
                    self._emit(now, "info", c["title"], f"dispatched {name}", c["key"])
                elif r["state"] in RUN_TEXT:
                    text, tone = RUN_TEXT[r["state"]]
                    cause = f": {r['cause']}" if r.get("cause") else ""
                    self._emit(now, tone, c["title"], f"{name} {text}{cause}", c["key"])

    def update(self, st):
        now = time.time()
        with self.lock:
            seed = self.prev is None
            current = self._sessions(st)
            self._board(st)
            if not seed:
                for sid, s in current.items():
                    self._diff_session(sid, s, now)
            self._diff_runs(st, now, seed)
            self.prev = current
            return sorted(self.events, key=lambda e: -e["at"])


def _epoch(ts):
    try:
        return calendar.timegm(time.strptime(str(ts)[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return 0
