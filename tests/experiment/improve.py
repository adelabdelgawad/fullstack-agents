"""Arm B: a bounded propose -> probe -> compose loop over the workflow tree, then one final implementation run."""
import json
import shutil
from pathlib import Path

import workflow
from arms import _close, run_stage
from common import manifest, manifest_sha, now, write_json

RULES = f"""Edit rules:
- Edit only files under harness/skills/, harness/agents/*.md and harness/scripts/lib/roles/*.md; never hooks, settings,
  scripts or guards. At most {workflow.MAX_CHANGED_LINES} changed lines in total against the pinned baseline.
- Change how the agent works (procedure, tool use, verification, completion), never the task's subject matter: no
  task-specific code, file names, identifiers or solution steps.
- There is no rubric, answer key, reference solution or score in your context. Judge only by the task request and by
  what the trajectories show; every edit must answer a specific moment in a trajectory.
- Write NOTES.md in the workspace root: for each edit, the trajectory moment it answers, then one transferable lesson
  as three lines `cue: ...`, `lesson: ...`, `evidence: ...`.
"""

PROPOSE = """You are improving a coding-agent workflow, the FSA Claude Code plugin, for its next run of the same task.
harness/ is a writable copy of the current workflow. evidence/ holds trajectories of runs that used it, and TASK.md the
task those runs were given. Propose one improvement to the workflow in harness/. Leaving harness/ unchanged is a valid
outcome; then write KEEP_BASE in NOTES.md.

""" + RULES

COMPOSE = """You are composing ONE final workflow for the FSA Claude Code plugin from tested evidence.
harness/ holds the current workflow; candidate/ holds a proposed revision and candidate-NOTES.md its rationale;
evidence/ holds trajectories of runs with the current workflow and of the probe run with the candidate; TASK.md is the
task. Put in harness/ only the candidate edits the evidence supports; drop the rest. KEEPING THE CURRENT WORKFLOW
UNCHANGED IS A VALID OUTCOME: if the candidate did not demonstrably do better, leave harness/ as it is and write
KEEP_BASE in NOTES.md.

""" + RULES

REJECTED = "# YOUR PREVIOUS ATTEMPT WAS REJECTED\n\nFix these problems in harness/ and NOTES.md:\n{problems}\n\n"


def _tool_calls(config_dir, session_id):
    """One line per tool call of a lead transcript; edit contents are reduced to the file path."""
    paths = list(Path(config_dir).glob(f"projects/*/{session_id}.jsonl"))
    if not paths:
        return ["(no transcript)"]
    calls, errors = [], set()
    for line in paths[0].read_text(errors="replace").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        for item in (d.get("message") or {}).get("content") or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "tool_use":
                inp = item.get("input") or {}
                shown = inp.get("command") or inp.get("file_path") or inp.get("subagent_type") or ", ".join(inp)
                calls.append((item.get("id"), f"{item.get('name')}: {str(shown)[:300]}"))
            elif item.get("type") == "tool_result" and item.get("is_error"):
                errors.add(item.get("tool_use_id"))
    return [f"{text}{'  [error]' if cid in errors else ''}" for cid, text in calls]


def trajectory(stage):
    """Evidence for an improver: what happened in a stage, without the diff's content."""
    acct, session = stage["accounting"], stage.get("session") or {}
    lines = [f"# Stage {stage['stage']}", f"state: {stage['state']} ({stage['reason']})",
             f"wall seconds: {stage['seconds']}", f"estimated usd: {acct['estimated_usd']:.4f}",
             "processes: " + ", ".join(f"{p['role']} exit {p['exit']} {p['seconds']}s" for p in acct["processes"]),
             f"automatic replies: {len(session.get('auto_replies', []))}"]
    capture = stage.get("capture") or {}
    for tree in capture.get("worktrees", []):
        lines.append(f"changed files: {', '.join(tree['files']) or '(none)'}")
    for i, step in enumerate(session.get("steps", [])):
        lines += [f"\n## Final message of step {i}", (step.get("final_text") or "")[-4000:]]
    if session.get("session_id"):
        lines += ["\n## Lead tool calls", *_tool_calls(Path(stage["sandbox"]) / "config", session["session_id"])]
    return "\n".join(lines) + "\n"


def _workspace_setup(arm, current, extras, evidence, notes=None, prior=None):
    def setup(sb):
        ws = sb.root / "workspace"
        workflow.materialize(prior or current, ws / "harness")
        for name, tree in extras.items():
            workflow.materialize(tree, ws / name)
        (ws / "evidence").mkdir()
        for stage in evidence:
            (ws / "evidence" / f"{stage['stage']}.md").write_text(trajectory(stage))
        (ws / "TASK.md").write_text(arm.exp["task_text"])
        if notes:
            (ws / "candidate-NOTES.md").write_text(notes)
    return setup


def _lessons(notes):
    keys, out, cur = ("cue", "lesson", "evidence"), [], {}
    for line in notes.splitlines():
        key, _, value = line.strip().lstrip("-* ").partition(":")
        if key.lower() in keys and value.strip():
            cur[key.lower()] = value.strip()
            if all(k in cur for k in keys):
                out.append(cur)
                cur = {}
    return out


def _freeze(arm, stage, ws, base, check):
    dest = arm.dir / "workflows" / stage
    shutil.copytree(ws / "harness", dest / "tree", ignore=workflow.IGNORE)
    files = manifest(dest / "tree")
    notes = (ws / "NOTES.md").read_text() if (ws / "NOTES.md").is_file() else ""
    (dest / "changes.diff").write_text(check["diff"])
    (dest / "NOTES.md").write_text(notes)
    write_json(dest / "manifest.json", {"files": files, "sha256": manifest_sha(files), "created": now(),
                                        "parent": str(base), "stage": stage})
    workflow.read_only(dest / "tree")
    return dest / "tree", notes


def improver(arm, stage, mission, current, extras, evidence, patches, poll_s, notes=None):
    """Up to two improver sessions; an invalid or failed result falls back to `current`."""
    base = Path(arm.exp["workflows"]["base"]["tree"])
    prompt, prior, attempts = mission, None, []
    for attempt in range(2):
        name = stage if attempt == 0 else f"{stage}-retry"
        rec = run_stage(arm, name, "improver", None, prompt, poll_s, cwd="workspace",
                        setup=_workspace_setup(arm, current, extras, evidence, notes, prior))
        ws = Path(rec["sandbox"]) / "workspace"
        check = workflow.check_candidate(base, ws / "harness", patches, arm.exp["task_text"])
        if rec["state"] != "succeeded":
            check["problems"].append(f"improver session {rec['state']}: {rec['reason']}")
            check["valid"] = False
        attempts.append({"stage": name, "problems": check["problems"], "changed": check["changed"],
                         "changed_lines": check["changed_lines"], "identifier_hits": check["identifier_hits"]})
        if check["valid"]:
            tree, notes = _freeze(arm, stage, ws, current, check)
            keep = check["empty"] or "KEEP_BASE" in notes
            return {"stage": stage, "tree": str(current if keep else tree), "candidate_tree": str(tree),
                    "keep_base": keep, "fell_back": False, "attempts": attempts, "notes": notes,
                    "lessons": _lessons(notes), "diff": str(tree.parent / "changes.diff")}
        if rec["state"] in ("budget_exhausted", "interrupted", "timed_out") or arm.exhausted():
            break
        prompt, prior = REJECTED.format(problems="\n".join(f"- {p}" for p in check["problems"])) + mission, ws / "harness"
    return {"stage": stage, "tree": str(current), "candidate_tree": None, "keep_base": False, "fell_back": True,
            "attempts": attempts, "notes": "", "lessons": [], "diff": None}


def _patches(arm):
    out = []
    for rec in arm.state["stages"].values():
        for tree in (rec.get("capture") or {}).get("worktrees", []):
            out.append(Path(tree["patch"]).read_text())
    return out


def _record_change(arm, result):
    arm.state["workflow_changes"].append({k: result[k] for k in ("stage", "tree", "candidate_tree", "keep_base",
                                                                 "fell_back", "attempts", "diff")})
    arm.state.setdefault("lessons", []).extend({"stage": result["stage"], **x} for x in result["lessons"])
    write_json(arm.dir / "lessons.json", {"scope": "this experiment only; promotion needs a separate reviewed decision",
                                          "lessons": arm.state["lessons"]})
    arm.save()


def _round(arm, r, current, evidence, poll_s):
    proposal = improver(arm, f"b-propose-{r}", PROPOSE, current, {}, evidence, _patches(arm), poll_s)
    _record_change(arm, proposal)
    if proposal["tree"] == str(current) or arm.exhausted():
        return current
    probe = run_stage(arm, f"b-probe-{r}", "implementation", Path(proposal["tree"]), arm.exp["task_text"], poll_s)
    evidence.append(probe)
    if arm.exhausted():
        return current
    composed = improver(arm, f"b-compose-{r}", COMPOSE, current, {"candidate": Path(proposal["tree"])}, evidence,
                        _patches(arm), poll_s, notes=proposal["notes"])
    _record_change(arm, composed)
    return Path(composed["tree"])


def run_arm_b(arm, poll_s=5.0):
    """Every probe, proposal, retry and composition is a stage of this arm and counts toward its totals."""
    base = current = Path(arm.exp["workflows"]["base"]["tree"])
    if arm.state["stages"]:
        return _close(arm, "failed", "arm B already has stages; start a new experiment to rerun it")
    evidence = [run_stage(arm, "b-base", "implementation", base, arm.exp["task_text"], poll_s)]
    for r in range(1, arm.budget["rounds"] + 1):
        if arm.exhausted():
            break
        current = _round(arm, r, current, evidence, poll_s)
    if arm.exhausted():
        return _close(arm, arm.exhausted(), "arm budget exhausted before the final run")
    final = run_stage(arm, "b-final", "implementation", current, arm.exp["task_text"], poll_s)
    arm.state["final_workflow"] = {"tree": str(current), "identical_to_base": current == base,
                                   "label": "repeat attempt with the baseline workflow (no harness change)"
                                   if current == base else "harness change applied"}
    return _close(arm, final["state"], final["reason"], final_stage="b-final")
