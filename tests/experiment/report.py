"""results.json and REPORT.md from saved artifacts only; every figure names the file it came from."""
from pathlib import Path

from common import now, read_json, write_json

DIFFERENCES = [
    "headless `claude -p` sessions; plan-approval stops get the recorded canned reply instead of a person",
    "the plugin is loaded with --plugin-dir from the pinned snapshot, not from the installed plugin list",
    "fresh CLAUDE_CONFIG_DIR and HOME: no user settings, personal CLAUDE.md, auto-memory, MCP servers or other plugins",
    "default reasoning effort (CLAUDE_EFFORT is not passed); model pinned with --model; CLI auto-update disabled",
    ("toolchains and caches under the real HOME (cargo, rustup, nvm, git identity) are absent unless passed with "
    "--env-allow"),
    ("`claude -p` cancels async Stop hooks at exit, so the end-of-turn reply classifier is killed before it runs: "
     "counted as a failed classifier process with no usage in every stage of both arms"),
]

ISOLATION = {
    "guarantees": [
        "each session runs in its own git clone (no shared git common dir, origin remote removed)",
        "each session has its own HOME, CLAUDE_CONFIG_DIR, TMPDIR, XDG dirs and FSA state dirs (operational separation)",
        "each session starts from an allowlisted environment; secret values are never recorded",
        "the baseline workflow tree is read-only and re-hashed after every session",
    ],
    "limitations": [
        ("same OS user: agent processes can read any file this user can, including other arms and evaluation material "
        "present on this host; a sentinel or leak scan is a heuristic, not access control"),
        "shared network, model account and rate limits",
        "the spend watcher polls and is an approximate limit; spend can overshoot by one poll and in-flight requests",
        "the task-identifier scan of candidate workflows is a heuristic, not proof of no task-specific content",
    ],
}


def _implementer_runs(sandbox):
    runs = Path(sandbox) / "state/runs"
    return [{"id": p.name.removesuffix(".result.json"), "state": d.get("state"), "details": d.get("details")}
            for p in sorted(runs.glob("*.result.json")) if (d := read_json(p, {}))]


def _stage_row(rec):
    acct, session = rec.get("accounting") or {}, rec.get("session") or {}
    runs = _implementer_runs(rec["sandbox"])
    return {"stage": rec["stage"], "kind": rec["kind"], "state": rec["state"], "reason": rec.get("reason"),
            "seconds": rec.get("seconds"), "cli_reported_usd": acct.get("cli_reported_usd"),
            "estimated_usd": acct.get("estimated_usd"), "processes": len(acct.get("processes", [])),
            "failed_processes": sum(r["failed"] for r in acct.get("by_role", {}).values()),
            "implementer_runs": runs, "implementer_retries": max(len(runs) - 1, 0) if runs else 0,
            "auto_replies": len(session.get("auto_replies", [])), "gaps": acct.get("gaps", []),
            "workflow_sha256": rec.get("workflow_sha256"), "workflow_mismatch_after": rec.get("workflow_mismatch_after"),
            "instruction_sources": rec.get("instruction_sources"), "start_tree": rec.get("start_tree"),
            "capture": (rec.get("capture") or {}).get("status"), "sandbox": rec["sandbox"]}


def _totals(rows, arm_state):
    def total(key):
        return round(sum(r[key] or 0 for r in rows), 6)
    gaps = sum(len(r["gaps"]) for r in rows)
    return {"seconds": total("seconds"), "cli_reported_usd": total("cli_reported_usd"),
            "estimated_usd": total("estimated_usd"), "billed_usd": None, "processes": total("processes"),
            "failed_processes": total("failed_processes"), "implementer_retries": total("implementer_retries"),
            "improver_retries": sum(1 for r in rows if r["stage"].endswith("-retry")),
            "auto_replies": total("auto_replies"), "human_interventions": len(arm_state["human_interventions"]),
            "measurement_gaps": gaps, "usage_is_lower_bound": gaps > 0}


def arm_summary(arm_dir):
    state = read_json(Path(arm_dir) / "arm.json")
    if not state:
        return None
    rows = [_stage_row(state["stages"][s]) for s in state["order"]]
    final = state.get("final_stage")
    capture = (state["stages"].get(final) or {}).get("capture") if final else None
    totals = _totals(rows, state)
    final_row = next((r for r in rows if r["stage"] == final), None)
    overhead = {k: round(totals[k] - (final_row[k] or 0), 6) for k in ("seconds", "cli_reported_usd", "estimated_usd")} \
        if final_row else None
    return {"state": state["state"], "reason": state.get("reason"), "stages": rows, "totals": totals,
            "overhead_before_final": overhead, "deliverable": capture, "workflow_changes": state["workflow_changes"],
            "final_workflow": state.get("final_workflow"), "human_interventions": state["human_interventions"],
            "auto_replies": [dict(stage=r["stage"], **a) for s in state["order"]
                             for r in [state["stages"][s]] for a in (r.get("session") or {}).get("auto_replies", [])],
            "artifact": str(Path(arm_dir) / "arm.json")}


def verdict(evaluation, arms):
    if not evaluation:
        return "unevaluated", ["no independent evaluation has been run"]
    va, vb = (evaluation["arms"].get(a, {}).get("verdict") for a in ("A", "B"))
    caveats = ["single task, n=1: a task-specific case study, not evidence of general improvement"]
    if (arms.get("B") or {}).get("final_workflow", {}) and arms["B"]["final_workflow"].get("identical_to_base"):
        caveats.append("B's final run used the baseline workflow: it is a repeat attempt, not a harness improvement")
    for name, arm in arms.items():
        if arm and arm["totals"]["usage_is_lower_bound"]:
            caveats.append(f"arm {name} usage has measurement gaps; its totals are lower bounds")
        if arm and arm["state"] != "succeeded":
            caveats.append(f"arm {name} ended {arm['state']}: {arm['reason']}")
    if evaluation.get("leak_hits"):
        caveats.append("evaluation material is mentioned in sandbox files (leak scan hits)")
    if evaluation.get("environment_suspect"):
        caveats.append("no regression check passes on the source commit: the evaluation environment is suspect")
    if evaluation.get("commitment") == "MISMATCH":
        caveats.append("evaluation checks differ from the hash committed at init")
    if "inconclusive" in (va, vb) or None in (va, vb):
        return "inconclusive", caveats
    if va == vb:
        return f"tie: both {va}", caveats
    return ("A" if va == "accepted" else "B") + " better on acceptance for this task", caveats


def build(exp_dir):
    exp_dir = Path(exp_dir)
    exp = read_json(exp_dir / "experiment.json")
    arms = {a: arm_summary(exp_dir / "arms" / a) for a in ("A", "B")}
    evaluation = read_json(exp_dir / "eval/evaluation.json")
    outcome, caveats = verdict(evaluation, arms)
    results = {"generated": now(), "experiment": {k: exp[k] for k in ("id", "source_repo", "commit", "task_sha256",
                                                                       "model", "order", "budgets", "workflows")},
               "isolation": ISOLATION, "differences_from_normal_use": DIFFERENCES, "arms": arms,
               "evaluation": evaluation and {k: evaluation.get(k) for k in (
                   "arms", "checks_sha256", "commitment", "leak_hits", "checks_unchanged_after_run",
                   "environment_suspect")},
               "comparison": {"practical": {a: arms[a] and arms[a]["totals"] for a in arms}, "outcome": outcome,
                              "caveats": caveats, "cost_kinds": {
                                  "cli_reported_usd": "API-equivalent cost reported by each claude process",
                                  "estimated_usd": "transcript tokens priced with scripts/lib/usage.py (estimate)",
                                  "billed_usd": "unknown: subscription billing is not observable here"}}}
    write_json(exp_dir / "results.json", results)
    (exp_dir / "REPORT.md").write_text(markdown(results, exp_dir))
    return results


def _money(v):
    return "unknown" if v is None else f"${v:.4f}"


def markdown(r, exp_dir):
    e, comp = r["experiment"], r["comparison"]
    out = [f"# Workflow comparison {e['id']}", "",
           f"Outcome: **{comp['outcome']}**", "", *[f"- {c}" for c in comp["caveats"]], "",
           (f"Source `{e['source_repo']}` at `{e['commit']}` · task sha256 `{e['task_sha256'][:16]}` · model "
           f"`{e['model']}` · order {', '.join(e['order'])}"), "",
           "## Practical comparison (all overhead included)", "",
           ("| Arm | State | Wall s | CLI-reported | Estimated | Billed | Processes | Failed | Impl. retries | "
           "Improver retries | Auto replies | Human | Gaps |"), "|" + "---|" * 13]
    for name, arm in r["arms"].items():
        if not arm:
            out.append(f"| {name} | not run |" + " |" * 11)
            continue
        t = arm["totals"]
        out.append(f"| {name} | {arm['state']} | {t['seconds']} | {_money(t['cli_reported_usd'])} | "
                   f"{_money(t['estimated_usd'])} | unknown | {t['processes']} | {t['failed_processes']} | "
                   f"{t['implementer_retries']} | {t['improver_retries']} | {t['auto_replies']} | "
                   f"{t['human_interventions']} | {t['measurement_gaps']} |")
    out += _stages(r) + _evaluation(r) + _changes(r) + _isolation(r, exp_dir)
    return "\n".join(out) + "\n"


def _stages(r):
    out = ["", "## Stages", "", ("| Arm | Stage | Kind | State | Wall s | CLI-reported | Estimated | Auto replies | "
           "Workflow sha256 | Sandbox |"), "|" + "---|" * 10]
    for name, arm in r["arms"].items():
        for s in (arm or {}).get("stages", []):
            out.append(f"| {name} | {s['stage']} | {s['kind']} | {s['state']} | {s['seconds']} | "
                       f"{_money(s['cli_reported_usd'])} | {_money(s['estimated_usd'])} | {s['auto_replies']} | "
                       f"`{(s['workflow_sha256'] or '-')[:12]}` | `{s['sandbox']}` |")
    return out


def _evaluation(r):
    ev = r["evaluation"]
    if not ev:
        return ["", "## Evaluation", "", "Not run."]
    out = ["", "## Evaluation (same evaluation-owned checks for every target)", "",
           (f"checks sha256 `{ev['checks_sha256'][:16]}` · commitment {ev['commitment'] or 'none'} · "
           f"leak-scan hits {len(ev['leak_hits'])}"), "",
           "| Arm | Verdict | Check | Kind | Arm status | Source status | Outcome |", "|" + "---|" * 7]
    for name, a in ev["arms"].items():
        for c in a["acceptance"]:
            out.append(f"| {name} | {a['verdict']} | {c['id']} | acceptance | {c['status']} | {c['baseline']} | "
                       f"{'required pass' if c['status'] == 'pass' else 'NOT MET'} |")
        for c in a["regression"]:
            out.append(f"| {name} | {a['verdict']} | {c['id']} | regression | {c['arm']} | {c['baseline']} | "
                       f"{c['outcome']} |")
    return out


def _changes(r):
    b = r["arms"].get("B")
    out = ["", "## Workflow changes tested by B", ""]
    if not b:
        return out + ["B not run."]
    for ch in b["workflow_changes"]:
        status = "fell back to current" if ch["fell_back"] else ("kept base" if ch["keep_base"] else "candidate")
        out.append(f"- {ch['stage']}: {status}; attempts {len(ch['attempts'])}; diff `{ch['diff'] or '-'}`")
        out += [f"  - {a['stage']}: {a['changed_lines']} lines, problems: {'; '.join(a['problems']) or 'none'}"
                for a in ch["attempts"]]
    fw = b.get("final_workflow") or {}
    return out + ["", f"Final workflow: {fw.get('label', 'not reached')}"]


def _isolation(r, exp_dir):
    iso = r["isolation"]
    return ["", "## Differences from normal use", "", *[f"- {d}" for d in r["differences_from_normal_use"]],
            "", "## Isolation", "", "Guarantees:", *[f"- {g}" for g in iso["guarantees"]], "", "Limitations:",
            *[f"- {x}" for x in iso["limitations"]], "", "## Artifacts", "",
            f"- experiment: `{exp_dir / 'experiment.json'}`", f"- results: `{exp_dir / 'results.json'}`",
            *[f"- arm {n}: `{a['artifact']}`" for n, a in r["arms"].items() if a],
            f"- evaluation: `{exp_dir / 'eval/evaluation.json'}`",
            "- cost kinds: CLI-reported (API-equivalent), estimated (transcript-priced), billed (unknown)"]
