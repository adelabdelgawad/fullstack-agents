"""Independent evaluation: the same evaluation-owned checks on fresh clones of the source and of each deliverable."""
import os
import shutil
import subprocess
from pathlib import Path

from common import git, manifest, manifest_sha, now, read_json, run_bounded, write_json

STATUSES = ("pass", "fail", "timeout", "unavailable", "skipped", "unexecuted")


def load_checks(checks_dir):
    spec = read_json(Path(checks_dir) / "checks.json")
    if not isinstance(spec, dict) or not spec.get("acceptance"):
        raise SystemExit("checks.json needs a non-empty 'acceptance' list")
    ids = [c["id"] for c in spec["acceptance"] + spec.get("regression", [])]
    if len(ids) != len(set(ids)):
        raise SystemExit("check ids must be unique")
    return spec


def _overlay_files(checks_dir, spec):
    root = Path(checks_dir) / spec.get("overlay", "overlay")
    return root, sorted(manifest(root)) if root.is_dir() else []


def _prepare(target_dir, source, commit, patch, checks_dir, spec):
    """Fresh clone + patch + overlay; returns (repo, problem, conflicts)."""
    repo = Path(target_dir) / "repo"
    git(["clone", "-q", "--no-local", "--no-checkout", str(source), str(repo)], cwd=target_dir)
    git(["checkout", "-q", "--detach", commit], cwd=repo)
    touched = []
    if patch and Path(patch).read_text().strip():
        proc = subprocess.run(["git", "-C", str(repo), "apply", "--index", "--binary", str(patch)],
                              capture_output=True, text=True, check=False)
        if proc.returncode:
            return repo, f"patch failed to apply: {proc.stderr.strip()[:500]}", []
        touched = git(["diff", "--cached", "--name-only"], cwd=repo).split()
    root, files = _overlay_files(checks_dir, spec)
    for rel in files:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, repo / rel)
    return repo, None, sorted(set(touched) & set(files))


def _env(target_dir, spec):
    home = Path(target_dir) / "home"
    home.mkdir(exist_ok=True)
    env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", *spec.get("env", [])) if k in os.environ}
    env.update(HOME=str(home), TMPDIR=str(home))
    return env


def run_target(name, target_dir, source, commit, patch, checks_dir, spec, deliverable_problem=None):
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    checks = [("acceptance", c) for c in spec["acceptance"]] + [("regression", c) for c in spec.get("regression", [])]
    problem, conflicts, repo = deliverable_problem, [], None
    if problem is None:
        repo, problem, conflicts = _prepare(target_dir, source, commit, patch, checks_dir, spec)
    results = []
    for kind, check in checks:
        row = {"id": check["id"], "kind": kind, "command": check["command"], "timeout": check.get("timeout", 600)}
        if problem:
            row.update(status="unexecuted", reason=problem)
        elif check.get("skip"):
            row.update(status="skipped", reason=check["skip"])
        else:
            log = target_dir / f"{check['id']}.log"
            status, code, seconds = run_bounded(check["command"], repo / check.get("cwd", "."), _env(target_dir, spec),
                                                row["timeout"], log)
            row.update(status=status, exit=code, seconds=seconds, log=str(log))
        results.append(row)
    return {"target": name, "patch": patch and str(patch), "problem": problem, "eval_path_conflicts": conflicts,
            "checks": results}


def classify(baseline, arm):
    """Acceptance is absolute (every check must pass); regressions are relative to the source commit."""
    base = {c["id"]: c["status"] for c in baseline["checks"]}
    acceptance = [c for c in arm["checks"] if c["kind"] == "acceptance"]
    regression = []
    for c in (c for c in arm["checks"] if c["kind"] == "regression"):
        before, after = base.get(c["id"], "unexecuted"), c["status"]
        if before == "pass" and after == "pass":
            outcome = "ok"
        elif before == "pass":
            outcome = "new_regression" if after in ("fail", "timeout") else "unknown"
        elif before == "fail":
            outcome = {"pass": "fixed", "fail": "existing_failure"}.get(after, "unknown")
        else:
            outcome = "unknown"
        regression.append({"id": c["id"], "baseline": before, "arm": after, "outcome": outcome})
    acceptance_pass = bool(acceptance) and all(c["status"] == "pass" for c in acceptance)
    new_regressions = [r["id"] for r in regression if r["outcome"] == "new_regression"]
    unknown = [r["id"] for r in regression if r["outcome"] == "unknown"]
    verdict = "accepted" if acceptance_pass and not new_regressions and not unknown else (
        "rejected" if not acceptance_pass or new_regressions else "inconclusive")
    return {"verdict": verdict, "acceptance_pass": acceptance_pass,
            "acceptance": [{"id": c["id"], "status": c["status"], "baseline": base.get(c["id"])} for c in acceptance],
            "regression": regression, "new_regressions": new_regressions, "unknown_regressions": unknown,
            "eval_path_conflicts": arm["eval_path_conflicts"]}


def leak_scan(sandbox_roots, needles):
    """Heuristic only: sandbox files naming evaluation material or the other arm; absence proves nothing."""
    hits = []
    for root in sandbox_roots:
        arm_dir = Path(root).parent.parent
        own = [*needles, *(str(a) for a in arm_dir.parent.iterdir() if a.is_dir() and a != arm_dir)]
        for path in Path(root).rglob("*"):
            if not path.is_file() or path.stat().st_size > 50_000_000 or "repo" in path.relative_to(root).parts[:1]:
                continue
            text = path.read_text(errors="replace")
            hits += [{"file": str(path), "needle": n} for n in own if n in text]
    return hits


def environment_suspect(baseline):
    """True when no regression check passes on the untouched source: the evaluation environment is likely broken."""
    regression = [c for c in baseline["checks"] if c["kind"] == "regression"]
    return bool(regression) and not any(c["status"] == "pass" for c in regression)


def evaluate(exp_dir, checks_dir, experiment, deliverables):
    """Run baseline and every arm's deliverable; `deliverables` maps arm -> (patch or None, problem or None)."""
    exp_dir, checks_dir = Path(exp_dir), Path(checks_dir).resolve()
    if exp_dir.resolve() in checks_dir.parents or checks_dir == exp_dir.resolve():
        raise SystemExit("checks must live outside the experiment directory")
    frozen = exp_dir / "eval/checks"
    if frozen.exists():
        shutil.rmtree(frozen)
    shutil.copytree(checks_dir, frozen)
    spec, files = load_checks(frozen), manifest(frozen)
    sha = manifest_sha(files)
    committed = experiment.get("checks_sha256")
    source, commit = experiment["source_repo"], experiment["commit"]
    targets = {"baseline": run_target("baseline", exp_dir / "eval/baseline", source, commit, None, frozen, spec)}
    for arm, (patch, problem) in deliverables.items():
        targets[arm] = run_target(arm, exp_dir / f"eval/{arm}", source, commit, patch, frozen, spec, problem)
    _root, overlay = _overlay_files(frozen, spec)
    known = set(git(["ls-tree", "-r", "--name-only", commit], cwd=source).split())
    needles = [str(checks_dir), *[f for f in overlay if f not in known]]
    record = {"at": now(), "checks_source": str(checks_dir), "checks_sha256": sha, "committed_sha256": committed,
              "commitment": None if not committed else ("match" if committed == sha else "MISMATCH"),
              "targets": targets, "arms": {a: classify(targets["baseline"], targets[a]) for a in deliverables},
              "leak_hits": leak_scan(experiment.get("sandboxes", []), needles)}
    record["checks_unchanged_after_run"] = manifest_sha(manifest(checks_dir)) == sha
    record["environment_suspect"] = environment_suspect(targets["baseline"])
    write_json(exp_dir / "eval/evaluation.json", record)
    return record
