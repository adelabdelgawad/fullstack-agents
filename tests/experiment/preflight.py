"""Real-CLI preflights: dedicated-token auth, plugin and instruction loading, subagent and resume cost semantics."""
import re
import time
import uuid
from pathlib import Path

import measure
from arms import LEAD_AGENT, _instruction_sources, _token
from common import now, write_json
from sandbox import Sandbox
from session import Limits, _one

SUBAGENT_PROMPT = ("Use the Agent tool exactly once with subagent_type general-purpose and the prompt 'Reply with the "
                   "single word hi.' Then reply with the single word DONE. Use no other tool.")


def _run(sb, exp, args, prompt, name, cap_usd):
    env = sb.env(exp["real_claude"], _token(exp), exp.get("env_allow", ()))
    env["FSA_EXP_ROLE"] = "preflight"
    limits = Limits(time.time() + 300, cap_usd, 0.0, 1.0)
    full = ["-p", *args, "--output-format", "stream-json", "--verbose", "--max-budget-usd", f"{cap_usd:.2f}",
            "--debug-file", str(sb.root / "debug.log")]
    return _one(sb, sb.repo, env, full, prompt, sb.root / f"{name}.jsonl", limits)


def _cost(step):
    return (step["result"] or {}).get("total_cost_usd")


def _closer(value, a, b):
    """'a' or 'b' only when the candidates differ clearly and the value sits near one of them."""
    if value is None or abs(a - b) < max(0.05 * max(abs(a), abs(b)), 1e-6):
        return "unknown"
    near = min((abs(value - a), "a"), (abs(value - b), "b"))
    return near[1] if near[0] <= 0.25 * abs(a - b) else "unknown"


def _hook_evidence(sb, tree):
    """SessionStart hook output in the transcripts, and whether its plugin path is the pinned snapshot."""
    text = "".join(f.read_text(errors="replace") for f in (sb.root / "config").glob("projects/**/*.jsonl"))
    paths = sorted(set(re.findall(r"Plugin scripts:[^`]*`([^`]+)`", text)))
    return {"session_start_hook_entries": text.count('"hookEvent":"SessionStart"'), "plugin_scripts_paths": paths,
            "hooks_from_snapshot": bool(paths) and all(x.startswith(str(tree)) for x in paths)}


def check_auth_and_loading(exp, root, model, cap):
    sb = Sandbox(root / "loading")
    sb.create(exp["source_repo"], exp["commit"], "preflight-loading")
    tree = exp["workflows"]["base"]["tree"]
    step = _run(sb, exp, ["--model", model, "--dangerously-skip-permissions", "--strict-mcp-config", "--plugin-dir",
                          tree, "--agent", LEAD_AGENT], "Reply with the single word OK. Use no tools.", "load", cap)
    sources = _instruction_sources(sb, {"steps": [step]})
    debug = (sb.root / "debug.log").read_text(errors="replace") if (sb.root / "debug.log").is_file() else ""
    home = str(Path.home())
    personal = sorted(set(re.findall(re.escape(home) + r"/\.claude[^\s\"']*/CLAUDE\.md", debug)))
    plugins = [p for p in sources.get("plugins") or [] if "fullstack" in str(p.get("name", ""))]
    control = [f for f in sources["instruction_files_in_debug_log"] if f.startswith(str(sb.repo))]
    return {"auth_ok": bool(step["result"]) and not step["result"].get("is_error"), **_hook_evidence(sb, tree),
            "instruction_control_seen": control,
            "personal_instructions_check": ("none loaded" if not personal else "LOADED") if control else
            "unverified: the debug log lists no instruction file of the clone",
            "token_present": _token(exp) is not None, "exit": step["exit"], "result": step["result"],
            "fullstack_plugins": plugins, "single_pinned_plugin": [p.get("path") for p in plugins] == [tree],
            "lead_agent_listed": LEAD_AGENT in (sources.get("agents") or []), "instruction_sources": sources,
            "personal_claude_md_in_debug_log": personal, "hook_lines_in_debug_log": debug.count("hook"),
            "log": step["log"]}


def check_subagent_and_resume(exp, root, model, cap):
    sb = Sandbox(root / "accounting")
    sb.create(exp["source_repo"], exp["commit"], "preflight-accounting")
    sid = str(uuid.uuid4())
    base = ["--model", model, "--dangerously-skip-permissions", "--strict-mcp-config"]
    first = _run(sb, exp, [*base, "--session-id", sid], SUBAGENT_PROMPT, "subagent", cap)
    t1 = measure.transcripts(sb.root / "config")
    lead_only = _lead_cost(sb, sid)
    second = _run(sb, exp, [*base, "--resume", sid], "Reply with the single word AGAIN. Use no tools.", "resume", cap)
    t2 = measure.transcripts(sb.root / "config")
    c1, c2 = _cost(first), _cost(second)
    sub = _closer(c1, t1["estimated_usd"], lead_only)
    res = _closer(c2, t2["estimated_usd"], t2["estimated_usd"] - t1["estimated_usd"])
    if not [f for f in t1["files"] if "/subagents/" in f]:
        sub = "unknown"
    return {"subagent_files": [f for f in t1["files"] if "/subagents/" in f],
            "first_cli_usd": c1, "transcript_all_usd": t1["estimated_usd"], "transcript_lead_only_usd": lead_only,
            "parent_total_includes_subagents": {"a": True, "b": False}.get(sub, "unverified"),
            "resume_cli_usd": c2, "transcript_total_after_resume_usd": t2["estimated_usd"],
            "resume_cost_semantics": {"a": "cumulative", "b": "incremental"}.get(res, "unverified"),
            "logs": [first["log"], second["log"]]}


def _lead_cost(sb, sid):
    files = list((sb.root / "config").glob(f"projects/*/{sid}.jsonl"))
    if not files:
        return 0.0
    tmp = sb.root / "lead-only"
    (tmp / "projects/x").mkdir(parents=True, exist_ok=True)
    (tmp / "projects/x/lead.jsonl").write_text(files[0].read_text())
    return measure.transcripts(tmp)["estimated_usd"]


def preflight(exp_dir, exp, model, cap):
    root = Path(exp_dir) / "preflight"
    if root.exists():
        raise SystemExit(f"preflight already ran: {root}")
    record = {"at": now(), "model": model, "cap_usd_per_call": cap}
    record["loading"] = check_auth_and_loading(exp, root, model, cap)
    if record["loading"]["auth_ok"]:
        record["accounting"] = check_subagent_and_resume(exp, root, model, cap)
    spent = [measure.account(p)["cli_reported_usd"] for p in (root / "loading", root / "accounting") if p.is_dir()]
    record["cli_reported_usd_total"] = round(sum(spent), 6)
    write_json(root / "preflight.json", record)
    return record
