#!/usr/bin/env python3
"""Compare the pinned FSA workflow (arm A) with a bounded Harness²-inspired loop (arm B); see docs/EXPERIMENT_RUNNER.md."""
import argparse
import shutil
import sys
import time
from pathlib import Path

import evaluate as evaluation
import preflight as preflights
import report
import workflow
from arms import Arm, _close, resume_stage, run_arm_a
from common import (
    experiments_dir,
    git,
    manifest,
    manifest_sha,
    now,
    read_json,
    sha256_text,
    write_json,
)
from improve import run_arm_b

RUNNERS = {"A": run_arm_a, "B": run_arm_b}


def cmd_init(a):
    source = Path(a.source).resolve()
    commit = git(["rev-parse", f"{a.commit}^{{commit}}"], cwd=source).strip()
    exp_id = a.id or time.strftime("%Y%m%d-%H%M%S")
    exp_dir = experiments_dir() / exp_id
    if exp_dir.exists():
        sys.exit(f"experiment exists: {exp_dir}")
    task_text = Path(a.task).read_text()
    base = workflow.snapshot(a.workflow, exp_dir / "workflows/base")
    (exp_dir / "task").mkdir(parents=True)
    (exp_dir / "task/TASK.md").write_text(task_text)
    real = a.real_claude or shutil.which("claude")
    if not real:
        sys.exit("claude CLI not found; pass --real-claude")
    budgets = {"A": {"usd": a.usd_a, "wall_s": a.wall_a, "session_s": a.session_s, "auto_replies": a.replies_a},
               "B": {"usd": a.usd_b, "wall_s": a.wall_b, "session_s": a.session_s, "auto_replies": a.replies_b,
                     "rounds": a.rounds, "improver_attempts": 2}}
    exp = {"id": exp_id, "created": now(), "source_repo": str(source), "commit": commit,
           "source_dirty": git(["status", "--porcelain"], cwd=source) != "", "task_text": task_text,
           "task_sha256": sha256_text(task_text), "model": a.model, "order": a.order.split(","), "budgets": budgets,
           "workflows": {"base": {"tree": str(exp_dir / "workflows/base/tree"), "sha256": base["sha256"],
                                  "source": base["source"], "delta_from_head": base["delta_from_head"]}},
           "real_claude": str(Path(real).resolve()), "token_file": a.token_file, "env_allow": a.env_allow,
           "checks_sha256": a.checks_sha256, "sandboxes": []}
    write_json(exp_dir / "experiment.json", exp)
    print(exp_dir)


def _load(exp):
    exp_dir = Path(exp) if Path(exp).is_dir() else experiments_dir() / exp
    data = read_json(exp_dir / "experiment.json")
    if not data:
        sys.exit(f"no experiment at {exp_dir}")
    return exp_dir, data


def _register_sandboxes(exp_dir, exp):
    exp["sandboxes"] = sorted(str(p) for p in exp_dir.glob("arms/*/stages/*") if p.is_dir())
    write_json(exp_dir / "experiment.json", exp)


def cmd_run(a):
    exp_dir, exp = _load(a.exp)
    arms = [a.arm] if a.arm else exp["order"]
    code = 0
    for name in arms:
        arm = Arm(exp_dir, exp, name)
        try:
            state = RUNNERS[name](arm, a.poll)
        except KeyboardInterrupt:
            state = _close(arm, "interrupted", "runner received SIGINT")
            code = 130
        print(f"arm {name}: {state['state']} ({state.get('reason')})")
        _register_sandboxes(exp_dir, exp)
        if code:
            break
    report.build(exp_dir)
    return code


def cmd_resume(a):
    exp_dir, exp = _load(a.exp)
    arm = Arm(exp_dir, exp, a.arm)
    rec = resume_stage(arm, a.stage, a.message, a.poll)
    if arm.state.get("final_stage") == a.stage:
        _close(arm, rec["state"], rec["reason"], final_stage=a.stage)
    report.build(exp_dir)
    print(f"stage {a.stage}: {rec['state']} ({rec['reason']})")


def _deliverable(exp_dir, name):
    state = read_json(exp_dir / "arms" / name / "arm.json")
    final = state and state.get("final_stage")
    capture = final and state["stages"][final].get("capture")
    if not capture:
        return None, f"arm {name} produced no final implementation"
    if capture["status"] == "ambiguous_deliverable":
        return None, "several worktrees changed; the deliverable is ambiguous"
    return capture["deliverable"], None


def cmd_evaluate(a):
    exp_dir, exp = _load(a.exp)
    _register_sandboxes(exp_dir, exp)
    arms = {n: _deliverable(exp_dir, n) for n in ("A", "B") if (exp_dir / "arms" / n / "arm.json").is_file()}
    result = evaluation.evaluate(exp_dir, a.checks, exp, arms)
    report.build(exp_dir)
    for name, c in result["arms"].items():
        print(f"arm {name}: {c['verdict']} (acceptance {'met' if c['acceptance_pass'] else 'NOT met'}, "
              f"new regressions {len(c['new_regressions'])}, unknown {len(c['unknown_regressions'])})")


def cmd_report(a):
    exp_dir, _exp = _load(a.exp)
    results = report.build(exp_dir)
    print(f"{exp_dir / 'REPORT.md'}\noutcome: {results['comparison']['outcome']}")


def cmd_preflight(a):
    exp_dir, exp = _load(a.exp)
    rec = preflights.preflight(exp_dir, exp, a.model, a.cap)
    acct = rec.get("accounting") or {}
    exp["resume_cost_semantics"] = acct.get("resume_cost_semantics", "unverified")
    exp["preflight"] = str(exp_dir / "preflight/preflight.json")
    write_json(exp_dir / "experiment.json", exp)
    load = rec["loading"]
    print(f"auth {'ok' if load['auth_ok'] else 'FAILED'} · single pinned plugin {load['single_pinned_plugin']} · "
          f"lead agent {load['lead_agent_listed']} · hooks from snapshot {load['hooks_from_snapshot']} · personal "
          f"instructions {load['personal_instructions_check']}"
          f" · subagents in parent total {acct.get('parent_total_includes_subagents', 'unknown')} · resume cost "
          f"{exp['resume_cost_semantics']} · spent ${rec['cli_reported_usd_total']:.4f} (CLI-reported)")


def cmd_checks_hash(a):
    print(manifest_sha(manifest(Path(a.dir))))


def parser():
    p = argparse.ArgumentParser(prog="fsa_experiment.py", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init")
    i.add_argument("--source", required=True)
    i.add_argument("--commit", required=True)
    i.add_argument("--task", required=True)
    i.add_argument("--workflow", required=True, help="plugin directory to pin as the baseline (e.g. the installed cache)")
    i.add_argument("--model", required=True)
    i.add_argument("--id")
    i.add_argument("--order", default="A,B")
    i.add_argument("--usd-a", type=float, default=3.0)
    i.add_argument("--usd-b", type=float, default=9.0)
    i.add_argument("--wall-a", type=float, default=3600)
    i.add_argument("--wall-b", type=float, default=10800)
    i.add_argument("--session-s", type=float, default=3600)
    i.add_argument("--replies-a", type=int, default=2)
    i.add_argument("--replies-b", type=int, default=6)
    i.add_argument("--rounds", type=int, default=1)
    i.add_argument("--token-file", default="~/.config/fullstack-agents/experiment-oauth-token")
    i.add_argument("--env-allow", nargs="*", default=[])
    i.add_argument("--checks-sha256")
    i.add_argument("--real-claude")
    r = sub.add_parser("run")
    r.add_argument("exp")
    r.add_argument("--arm", choices=("A", "B"))
    r.add_argument("--poll", type=float, default=5.0)
    s = sub.add_parser("resume")
    s.add_argument("exp")
    s.add_argument("--arm", required=True, choices=("A", "B"))
    s.add_argument("--stage", required=True)
    s.add_argument("--message", required=True)
    s.add_argument("--poll", type=float, default=5.0)
    e = sub.add_parser("evaluate")
    e.add_argument("exp")
    e.add_argument("--checks", required=True)
    o = sub.add_parser("report")
    o.add_argument("exp")
    f = sub.add_parser("preflight")
    f.add_argument("exp")
    f.add_argument("--model", default="haiku")
    f.add_argument("--cap", type=float, default=0.25, help="USD cap per preflight call (CLI --max-budget-usd)")
    h = sub.add_parser("checks-hash")
    h.add_argument("dir")
    return p


def main(argv=None):
    a = parser().parse_args(argv)
    handler = {"init": cmd_init, "run": cmd_run, "resume": cmd_resume, "evaluate": cmd_evaluate,
               "report": cmd_report, "checks-hash": cmd_checks_hash, "preflight": cmd_preflight}[a.cmd]
    return handler(a) or 0


if __name__ == "__main__":
    sys.exit(main())
