"""Stage execution and persistence for both arms; arm B's improvement loop lives in improve.py."""
import re
import time
from pathlib import Path

import measure
import workflow
from common import now, read_json, sha256_text, sweep, write_json
from sandbox import Sandbox, others_locked, unlock_all
from session import Limits, run_session

LEAD_AGENT = "fullstack-agents:fullstack-agent"
IMPROVER_TOOLS = ("Read", "Grep", "Glob", "Edit", "Write")
STOP_ARM = ("budget_exhausted", "interrupted")


class Arm:
    """One arm's persisted state; completed stages are reused when `run` is repeated."""

    def __init__(self, exp_dir, experiment, name):
        self.exp_dir, self.exp, self.name = Path(exp_dir), experiment, name
        self.dir = self.exp_dir / "arms" / name
        self.path = self.dir / "arm.json"
        self.budget = experiment["budgets"][name]
        unlock_all(self.exp_dir)
        self.state = read_json(self.path) or {"arm": name, "stages": {}, "order": [], "workflow_changes": [],
                                              "human_interventions": [], "state": "pending"}
        for rec in self.state["stages"].values():
            if rec.get("state") == "running":
                rec.update(state="interrupted", reason="the runner exited before recording this stage")

    def save(self):
        write_json(self.path, self.state)

    def spent(self):
        return sum(s["accounting"]["budget_usd"] for s in self.state["stages"].values() if s.get("accounting"))

    def elapsed(self):
        return sum(s.get("seconds") or 0 for s in self.state["stages"].values())

    def replies_used(self):
        return sum(len(s["session"]["auto_replies"]) for s in self.state["stages"].values() if s.get("session"))

    def limits(self, poll_s):
        wall_left = self.budget["wall_s"] - self.elapsed()
        deadline = time.time() + max(min(wall_left, self.budget["session_s"]), 0)
        return Limits(deadline, self.budget["usd"], self.spent(), poll_s)

    def exhausted(self):
        if self.spent() >= self.budget["usd"]:
            return "budget_exhausted"
        return "timed_out" if self.elapsed() >= self.budget["wall_s"] else None

    def done(self, stage):
        rec = self.state["stages"].get(stage)
        return rec if rec and rec.get("state") not in (None, "running") else None


def _token(experiment):
    path = experiment.get("token_file")
    if not path or not Path(path).expanduser().is_file():
        return None
    return Path(path).expanduser().read_text().strip() or None


def _instruction_sources(sb, record):
    """Instruction files the CLI reports loading (debug log) and the init event's plugin and memory paths."""
    debug = sb.root / "debug.log"
    text = debug.read_text(errors="replace") if debug.is_file() else ""
    files = sorted(set(re.findall(r"(/[^\s\"'():,]+/(?:CLAUDE|AGENTS|CLAUDE\.local)\.md)", text)))
    inits = [s["init"] for s in record["steps"] if s.get("init")]
    first = inits[0] if inits else {}
    return {"instruction_files_in_debug_log": files, "debug_log_present": bool(text),
            "plugins": first.get("plugins"), "memory_paths": first.get("memory_paths"),
            "model": first.get("model"), "agents": first.get("agents"), "permission_mode": first.get("permissionMode"),
            "claude_code_version": first.get("claude_code_version"), "verified": bool(inits)}


def _redact_token(root, token):
    """Replace the token value in every sandbox file outside .git; returns the files it was found in."""
    if not token:
        return []
    found, needle = [], token.encode()
    for path in Path(root).rglob("*"):
        if ".git" in path.parts or not path.is_file() or path.is_symlink() or path.stat().st_size > 200_000_000:
            continue
        data = path.read_bytes()
        if needle in data:
            path.write_bytes(data.replace(needle, b"[redacted-token]"))
            found.append(str(path))
    return found


def _plugin_loaded(sources, tree):
    paths = [p.get("path") for p in sources.get("plugins") or [] if isinstance(p, dict)]
    return str(tree) in paths


def run_stage(arm, stage, kind, tree, prompt, poll_s=5.0, cwd=None, setup=None, extra_args=()):
    """Run one session in a fresh sandbox; implementation stages load `tree` as the plugin under test."""
    exp = arm.exp
    sb = Sandbox(arm.dir / "stages" / stage)
    start = sb.create(exp["source_repo"], exp["commit"], f"{arm.name}-{stage}")
    if setup:
        setup(sb)
    env = sb.env(exp["real_claude"], _token(exp), exp.get("env_allow", ()))
    env["FSA_EXP_ROLE"] = "lead" if kind == "implementation" else "improver"
    record = {"stage": stage, "kind": kind, "state": "running", "started": now(), "sandbox": str(sb.root),
              "start_tree": start["tree"], "start_clean": start["clean"], "env": Sandbox.recorded(env),
              "workflow": str(tree) if tree else None, "prompt_sha256": sha256_text(prompt)}
    (sb.root / "prompt.md").write_text(prompt)
    arm.state["stages"][stage] = record
    if stage not in arm.state["order"]:
        arm.state["order"].append(stage)
    arm.save()
    args = _args(exp, kind, tree, sb, extra_args)
    started = time.monotonic()
    try:
        with others_locked(arm.exp_dir, sb.root, arm.name) as locked:
            record["locked_during_session"] = locked
            session = run_session(sb, sb.root / cwd if cwd else sb.repo, env, args, prompt, arm.limits(poll_s),
                                  sb.root / "logs", arm.budget["auto_replies"] - arm.replies_used())
    except KeyboardInterrupt:
        sweep(sb.marker)
        record.update(state="interrupted", reason="runner received SIGINT")
        _finish(arm, stage, sb, record, None, started, tree)
        raise
    record.update(state=session["state"], reason=session["reason"])
    return _finish(arm, stage, sb, record, session, started, tree)


def _args(exp, kind, tree, sb, extra_args):
    common = ["--model", exp["model"], "--dangerously-skip-permissions", "--strict-mcp-config",
              "--debug-file", str(sb.root / "debug.log")]
    if kind == "implementation":
        return [*common, "--plugin-dir", str(tree), "--agent", LEAD_AGENT, *extra_args]
    return [*common, "--tools", *IMPROVER_TOOLS, *extra_args]


def _finish(arm, stage, sb, record, session, started, tree):
    record["seconds"] = round(time.monotonic() - started, 2)
    record["ended"] = now()
    record["session"] = session
    record["token_redacted_in"] = _redact_token(sb.root, _token(arm.exp))
    acct = measure.account(sb.root, arm.exp.get("resume_cost_semantics", "unverified"))
    acct["budget_usd"] = max(acct["cli_reported_usd"], acct["estimated_usd"])
    record["accounting"] = acct
    if session:
        record["instruction_sources"] = _instruction_sources(sb, session)
        if tree and record["kind"] == "implementation":
            record["instruction_sources"]["plugin_dir_loaded"] = _plugin_loaded(record["instruction_sources"], tree)
    if record["kind"] == "implementation":
        record["capture"] = sb.capture(arm.exp["commit"], sb.root / "capture")
    if tree:
        manifest_rec = read_json(Path(tree).parent / "manifest.json")
        record["workflow_sha256"] = manifest_rec and manifest_rec["sha256"]
        record["workflow_mismatch_after"] = manifest_rec and workflow.verify(tree, manifest_rec)
    arm.save()
    return record


def run_arm_a(arm, poll_s=5.0):
    """Arm A: one implementation session with the pinned baseline workflow."""
    base = Path(arm.exp["workflows"]["base"]["tree"])
    if not arm.done("a-final"):
        if arm.exhausted():
            return _close(arm, arm.exhausted(), "budget exhausted before the session started")
        run_stage(arm, "a-final", "implementation", base, arm.exp["task_text"], poll_s)
    final = arm.state["stages"]["a-final"]
    return _close(arm, final["state"], final["reason"], final_stage="a-final")


def _close(arm, state, reason, final_stage=None):
    arm.state.update(state=state, reason=reason, final_stage=final_stage, ended=now())
    arm.save()
    return arm.state


def resume_stage(arm, stage, message, poll_s=5.0):
    """A real human reply to a stage waiting on the user; recorded apart from automatic replies."""
    rec = arm.state["stages"].get(stage)
    if not rec or rec.get("state") != "needs_human":
        raise SystemExit(f"stage {stage} is not waiting on a human")
    sb = Sandbox(rec["sandbox"])
    env = sb.env(arm.exp["real_claude"], _token(arm.exp), arm.exp.get("env_allow", ()))
    env["FSA_EXP_ROLE"] = "lead" if rec["kind"] == "implementation" else "improver"
    arm.state["human_interventions"].append({"stage": stage, "at": now(), "request": rec["reason"],
                                             "message": message})
    tree = Path(rec["workflow"]) if rec["workflow"] else None
    started = time.monotonic() - (rec.get("seconds") or 0)
    with others_locked(arm.exp_dir, sb.root, arm.name):
        session = run_session(sb, sb.repo if rec["kind"] == "implementation" else sb.root / "workspace", env,
                              _args(arm.exp, rec["kind"], tree, sb, ()), message, arm.limits(poll_s), sb.root / "logs",
                              arm.budget["auto_replies"] - arm.replies_used(), record=rec["session"])
    rec.update(state=session["state"], reason=session["reason"])
    return _finish(arm, stage, sb, rec, session, started, tree)
