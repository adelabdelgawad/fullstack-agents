"""Usage accounting for one sandbox: the per-process CLI ledger and the transcript estimate, kept separate."""
import json
from pathlib import Path

from common import usage

TOKEN_KEYS = ("input", "output", "write_5m", "write_1h", "cache_read")


def processes(ledger):
    """Start and end records of every `claude` process, joined by pid in start order."""
    starts, ends = [], {}
    for line in Path(ledger).read_text().splitlines():
        entry = json.loads(line)
        (starts.append(entry) if entry["event"] == "start" else ends.setdefault(entry["pid"], []).append(entry))
    out = []
    for start in starts:
        end = (ends.get(start["pid"]) or [None]).pop(0) if ends.get(start["pid"]) else None
        out.append({"pid": start["pid"], "role": start.get("role", "unknown"), "argv": start["argv"],
                    "started": start["at"], "ended": end and end["at"], "seconds": end and end["seconds"],
                    "exit": end and end["exit"], "result": end and end.get("result")})
    return out


def _tokens(u):
    cc = u.get("cache_creation") or {}
    w1h = cc.get("ephemeral_1h_input_tokens") or 0
    return {"input": u.get("input_tokens") or 0, "output": u.get("output_tokens") or 0, "write_1h": w1h,
            "write_5m": max((u.get("cache_creation_input_tokens") or 0) - w1h, 0),
            "cache_read": u.get("cache_read_input_tokens") or 0}


def transcripts(config_dir):
    """Transcript usage summed over every session file, each assistant message counted once by its id."""
    seen, models, files, duplicates = set(), {}, [], 0
    for path in sorted(Path(config_dir).glob("projects/**/*.jsonl")):
        files.append(str(path))
        for line in path.read_text(errors="replace").splitlines():
            if '"usage"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            msg = d.get("message") or {}
            if d.get("type") != "assistant" or not isinstance(msg.get("usage"), dict):
                continue
            key = msg.get("id") or d.get("requestId") or d.get("uuid")
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            totals = models.setdefault(msg.get("model") or "unknown", dict.fromkeys(TOKEN_KEYS, 0))
            for k, v in _tokens(msg["usage"]).items():
                totals[k] += v
    costs = {m: usage.cost_of(m, t) for m, t in models.items()}
    return {"files": files, "messages": len(seen), "duplicate_lines": duplicates, "models": models,
            "estimated_usd": sum(c for c in costs.values() if c is not None) if models else 0.0,
            "unpriced_models": sorted(m for m, c in costs.items() if c is None)}


def _model_usage_cost(model_usage):
    """Our price table applied to a process's CLI-reported per-model tokens (for runs without a transcript)."""
    total, unpriced = 0.0, []
    for model, u in (model_usage or {}).items():
        t = {"input": u.get("inputTokens", 0), "output": u.get("outputTokens", 0), "write_5m": 0,
             "write_1h": u.get("cacheCreationInputTokens", 0), "cache_read": u.get("cacheReadInputTokens", 0)}
        cost = usage.cost_of(model, t)
        if cost is None:
            unpriced.append(model)
        else:
            total += cost
    return total, unpriced


def _cli_cost(procs, resume_semantics):
    """CLI-reported cost; a resumed session's processes are summed, or only its last one counts if cumulative."""
    per_session, gaps, unpersisted_usd = {}, [], 0.0
    for p in procs:
        r = p["result"]
        if p["exit"] is None:
            gaps.append({"pid": p["pid"], "role": p["role"], "gap": "process has no end record"})
        if not r or r.get("total_cost_usd") is None:
            gaps.append({"pid": p["pid"], "role": p["role"], "gap": "no CLI result event (usage not reported)"})
            continue
        per_session.setdefault(r.get("session_id") or f"pid-{p['pid']}", []).append(r["total_cost_usd"])
        if "--no-session-persistence" in p["argv"]:
            cost, unpriced = _model_usage_cost(r.get("modelUsage"))
            unpersisted_usd += cost
            gaps += [{"pid": p["pid"], "role": p["role"], "gap": f"unpriced model {m}"} for m in unpriced]
    resumed = [sid for sid, costs in per_session.items() if len(costs) > 1]
    if resumed and resume_semantics not in ("cumulative", "incremental"):
        gaps.append({"gap": f"{len(resumed)} resumed session(s): resume cost semantics unverified; the CLI sum may "
                            "double-count"})
    pick = (lambda c: c[-1]) if resume_semantics == "cumulative" else sum
    return sum(pick(c) for c in per_session.values()), gaps, unpersisted_usd


def account(sandbox_root, resume_semantics="unverified"):
    """CLI-reported cost, independent transcript estimate and coverage gaps for one sandbox; billing is unknown."""
    root = Path(sandbox_root)
    procs = processes(root / "processes.jsonl")
    trans = transcripts(root / "config")
    reported, gaps, unpersisted_usd = _cli_cost(procs, resume_semantics)
    gaps += [{"gap": f"unpriced model {m} in transcripts"} for m in trans["unpriced_models"]]
    by_role = {}
    for p in procs:
        row = by_role.setdefault(p["role"], {"processes": 0, "failed": 0, "cli_reported_usd": 0.0})
        row["processes"] += 1
        row["failed"] += 1 if (p["exit"] or 0) != 0 or p["exit"] is None else 0
        row["cli_reported_usd"] += (p["result"] or {}).get("total_cost_usd") or 0.0
    return {"processes": procs, "by_role": by_role, "transcripts": trans,
            "cli_reported_usd": round(reported, 6),
            "estimated_usd": round(trans["estimated_usd"] + unpersisted_usd, 6),
            "estimated_unpersisted_usd": round(unpersisted_usd, 6),
            "billed_usd": None, "gaps": gaps}


def live_estimate(sandbox_root):
    """Spend so far for the budget watcher: the larger of the two measures, since either may lag."""
    root = Path(sandbox_root)
    trans = transcripts(root / "config")["estimated_usd"]
    try:
        procs = processes(root / "processes.jsonl")
    except (OSError, ValueError):
        procs = []
    reported = sum((p["result"] or {}).get("total_cost_usd") or 0.0 for p in procs)
    return max(trans, reported)
