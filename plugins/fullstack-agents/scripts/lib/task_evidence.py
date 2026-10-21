"""Completion evidence for v2 deliverables: spec, checks, runs, baselines and the done gate.

See docs/TASK_LIFECYCLE_DESIGN.md §12 (§12.11 wins over §12.1-§12.10).
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import task_tracking
import task_rules
import task_brief

EVID_START = "<!-- fsa:evidence:start -->"
EVID_END = "<!-- fsa:evidence:end -->"
SCHEMA = 1
METHODS = ("command", "review", "inspection", "document", "analysis")
KINDS = ("code", "docs", "design", "investigation", "other")
OUTCOMES = ("pass", "fail", "timeout", "unavailable", "inconclusive", "baseline")
EXTERNAL_RESULTS = ("pass", "fail", "timeout", "unavailable")
GATE_OK = frozenset(("pass", "baseline"))
MAX_SCOPE_FILES = 5000
MAX_SCOPE_BYTES = 200 * 1024 * 1024
DEFAULT_TIMEOUT = 540
COMMANDS = ("accept", "check", "baseline", "verify")

def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

# ---------------------------------------------------------------- block I/O

def _find_block(text):
    start = text.find(EVID_START)
    if start == -1:
        return None
    end = text.find(EVID_END)
    if end == -1:
        raise ValueError("Evidence section missing its end marker")
    return start, end

def has_block(text):
    return EVID_START in text

def _validate_block(payload):
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError("Evidence block has an invalid schema")
    if not set(payload).issubset({"schema", "deliverables", "baselines", "runs"}):
        raise ValueError("Evidence block has unknown keys")
    deliverables, baselines, runs = (payload.get("deliverables", {}), payload.get("baselines", {}),
                                      payload.get("runs", {}))
    if not all(isinstance(value, dict) for value in (deliverables, baselines, runs)):
        raise ValueError("Evidence block sections must be objects")
    return {"schema": SCHEMA, "deliverables": deliverables, "baselines": baselines, "runs": runs}

def load_block(text):
    """Always returns a well-shaped dict; a missing block is an empty one. Malformed is a clear error."""
    found = _find_block(text)
    if found is None:
        return {"schema": SCHEMA, "deliverables": {}, "baselines": {}, "runs": {}}
    start, end = found
    match = re.search(r"```json\s*\n(.*?)\n```", text[start:end], re.DOTALL)
    if not match:
        raise ValueError("Evidence section must contain a fenced json block")
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise ValueError(f"Evidence JSON is invalid: {error}") from error
    try:
        return _validate_block(payload)
    except (TypeError, KeyError) as error:
        raise ValueError(f"Evidence block is malformed: {error}") from error

def render_block(block):
    body = {"schema": SCHEMA, "deliverables": block.get("deliverables", {}),
            "baselines": block.get("baselines", {}), "runs": block.get("runs", {})}
    text = json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False)
    return f"{EVID_START}\n```json\n{text}\n```\n{EVID_END}\n"

def splice_block(text, section):
    """Replace an existing block in place, or insert one right after the task log."""
    found = _find_block(text)
    if found is not None:
        start, end = found
        end += len(EVID_END)
        if end < len(text) and text[end] == "\n":
            end += 1
        return text[:start] + section + text[end:]
    anchor = text.find(task_tracking.LOG_END)
    if anchor == -1:
        raise ValueError("Task log end marker not found")
    anchor += len(task_tracking.LOG_END)
    newline = text.find("\n", anchor)
    anchor = newline + 1 if newline != -1 else len(text)
    return text[:anchor] + "\n" + section + text[anchor:]

# ---------------------------------------------------------------- git helpers

def _git(args, cwd, timeout=20):
    try:
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except OSError as error:
        raise ValueError(f"git unavailable: {error}") from error
    if result.returncode != 0:
        raise ValueError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout

def _head(root):
    return _git(["rev-parse", "HEAD"], root).strip()

def _is_ancestor(root, ref, descendant="HEAD"):
    try:
        result = subprocess.run(["git", "merge-base", "--is-ancestor", ref, descendant],
                                 cwd=root, capture_output=True, timeout=20)
    except OSError as error:
        raise ValueError(f"git unavailable: {error}") from error
    return result.returncode == 0

def _check_within_root(root, relpath):
    resolved = (root / relpath).resolve()
    if resolved != root and not resolved.is_relative_to(root):
        raise ValueError(f"scope path escapes the repository: {relpath}")

def _scoped_files(root, paths):
    if not paths:
        return []
    for path in paths:
        _check_within_root(root, path)
    output = _git(["ls-files", "-co", "--exclude-standard", "-z", "--", *paths], root)
    return sorted({path for path in output.split("\0") if path})

def _baseline_code_state(root, ref):
    output = _git(["ls-tree", "-r", "--full-tree", ref], root)
    return hashlib.sha256(output.encode()).hexdigest()

# ---------------------------------------------------------------- state fingerprint (§12.6, §12.11.1/8)

def deliverable_state(root, spec, ledger_path=None):
    scope = spec["scope"]
    ledger_rel = str(ledger_path.resolve().relative_to(root)) if ledger_path is not None else None
    paths = sorted(set(scope["paths"]) | set(scope.get("dependencies", [])))
    tracked = [path for path in _scoped_files(root, paths) if path != ledger_rel]
    entries, count, total_bytes = [], 0, 0
    for rel in tracked:
        count += 1
        full = root / rel
        if full.is_file():
            data = full.read_bytes()
            total_bytes += len(data)
            entries.append([rel, hashlib.sha256(data).hexdigest()])
        else:
            entries.append([rel, "missing"])
    for rel in scope.get("inputs", []):
        if rel == ledger_rel:
            continue
        full = root / rel
        count += 1
        if full.is_file():
            data = full.read_bytes()
            total_bytes += len(data)
            entries.append([f"input:{rel}", hashlib.sha256(data).hexdigest()])
        else:
            entries.append([f"input:{rel}", "missing"])
    if count > MAX_SCOPE_FILES or total_bytes > MAX_SCOPE_BYTES:
        raise ValueError("narrow the scope")
    for name in sorted(scope.get("env", [])):
        entries.append([f"env:{name}", hashlib.sha256(os.environ.get(name, "").encode()).hexdigest()])
    canonical = json.dumps(entries, sort_keys=True, ensure_ascii=False)
    return {"digest": hashlib.sha256(canonical.encode()).hexdigest(), "head": _head(root), "files": count}

# ---------------------------------------------------------------- spec validation (§12.3, §12.11.1/4)

def _nonempty_str(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")
    return value.strip()

def _str_list(value, field):
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field} must be a list of nonempty strings")
    return [item.strip() for item in value]

def _validate_expect(value, check_id):
    if not isinstance(value, dict):
        raise ValueError(f"check {check_id}.expect is required")
    if "none" in value:
        if set(value) != {"none"}:
            raise ValueError(f"check {check_id}.expect.none must be the only key")
        return {"none": _nonempty_str(value["none"], f"check {check_id}.expect.none")}
    if set(value) - {"patterns", "reject"}:
        raise ValueError(f"check {check_id}.expect has unknown keys")
    patterns = _str_list(value.get("patterns", []), f"check {check_id}.expect.patterns")
    reject = _str_list(value.get("reject", []), f"check {check_id}.expect.reject")
    if not patterns and not reject:
        raise ValueError(f"check {check_id}.expect needs patterns/reject or none")
    for pattern in patterns + reject:
        try:
            re.compile(pattern)
        except re.error as error:
            raise ValueError(f"check {check_id}.expect has an invalid pattern: {error}") from error
    return {"patterns": patterns, "reject": reject}

def _validate_scope(value, kind, root):
    if not isinstance(value, dict):
        raise ValueError("scope must be an object")
    allowed = {"paths", "dependencies", "dependencies_none", "inputs", "env", "rationale"}
    if not set(value).issubset(allowed):
        raise ValueError(f"Unknown scope keys: {sorted(set(value) - allowed)}")
    rationale = _nonempty_str(value.get("rationale", ""), "scope.rationale")
    paths = _str_list(value.get("paths", []), "scope.paths")
    if not paths:
        raise ValueError("scope.paths must be nonempty")
    dependencies = _str_list(value.get("dependencies", []), "scope.dependencies")
    dependencies_none = value.get("dependencies_none")
    if kind == "code":
        if not dependencies and not dependencies_none:
            raise ValueError("code scope needs scope.dependencies or scope.dependencies_none with a reason")
        if dependencies_none is not None:
            dependencies_none = _nonempty_str(dependencies_none, "scope.dependencies_none")
    inputs = _str_list(value.get("inputs", []), "scope.inputs")
    env = _str_list(value.get("env", []), "scope.env")
    for path in paths + dependencies + inputs:
        _check_within_root(root, path)
    return {"paths": paths, "dependencies": dependencies, "dependencies_none": dependencies_none,
            "inputs": inputs, "env": env, "rationale": rationale}

def _validate_checks(value):
    if not isinstance(value, dict) or not value:
        raise ValueError("checks must be a nonempty object")
    checks = {}
    for check_id, check in value.items():
        if not isinstance(check, dict):
            raise ValueError(f"check {check_id} must be an object")
        method = check.get("method")
        if method not in METHODS:
            raise ValueError(f"check {check_id} has an invalid method")
        entry = {"method": method}
        if method == "command":
            entry["command"] = _nonempty_str(check.get("command", ""), f"check {check_id}.command")
            entry["cwd"] = check.get("cwd") or "."
            entry["expect"] = _validate_expect(check.get("expect"), check_id)
        elif "command" in check or "cwd" in check or "expect" in check:
            raise ValueError(f"check {check_id} is not a command check")
        checks[check_id] = entry
    return checks

def _validate_criteria(value, checks):
    if not isinstance(value, list) or not value:
        raise ValueError("criteria must be a nonempty list")
    criteria, seen = [], set()
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != {"id", "text", "checks"}:
            raise ValueError("criterion must have exactly id, text and checks")
        identifier = _nonempty_str(entry["id"], "criterion id")
        if identifier in seen:
            raise ValueError(f"Duplicate criterion id: {identifier}")
        seen.add(identifier)
        text = _nonempty_str(entry["text"], f"criterion {identifier}.text")
        refs = entry["checks"]
        if not isinstance(refs, list) or not refs or any(check_id not in checks for check_id in refs):
            raise ValueError(f"criterion {identifier} must reference known checks")
        criteria.append({"id": identifier, "text": text, "checks": list(dict.fromkeys(refs))})
    return criteria

def _stamp_digests(spec):
    for check_id, check in spec["checks"].items():
        referencing = [criterion for criterion in spec["criteria"] if check_id in criterion["checks"]]
        payload = {"check": check, "kind": spec["kind"], "scope": spec["scope"],
                   "automated_waiver": spec["automated_waiver"], "criteria": referencing}
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        check["definition_digest"] = hashlib.sha256(canonical.encode()).hexdigest()

def _build_spec(payload, root):
    if not isinstance(payload, dict):
        raise ValueError("Spec must be a JSON object")
    required = {"kind", "scope", "criteria", "checks"}
    allowed = required | {"automated_waiver"}
    if not set(payload).issubset(allowed):
        raise ValueError(f"Unknown spec keys: {sorted(set(payload) - allowed)}")
    if required - set(payload):
        raise ValueError(f"Spec missing required keys: {sorted(required - set(payload))}")
    kind = payload["kind"]
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    waiver = payload.get("automated_waiver")
    if waiver is not None:
        waiver = _nonempty_str(waiver, "automated_waiver")
    scope = _validate_scope(payload["scope"], kind, root)
    checks = _validate_checks(payload["checks"])
    criteria = _validate_criteria(payload["criteria"], checks)
    used = {check_id for criterion in criteria for check_id in criterion["checks"]}
    if set(checks) - used:
        raise ValueError(f"Checks not used by any criterion: {sorted(set(checks) - used)}")
    if kind == "code" and waiver is None and not any(check["method"] == "command" for check in checks.values()):
        raise ValueError("code deliverables need a command check or automated_waiver")
    spec = {"kind": kind, "scope": scope, "automated_waiver": waiver, "criteria": criteria, "checks": checks}
    _stamp_digests(spec)
    return spec

def _reason_needed(existing, spec):
    if existing is None or not existing.get("results"):
        return False, []
    removed_checks = set(existing["checks"]) - set(spec["checks"])
    removed_criteria = {c["id"] for c in existing["criteria"]} - {c["id"] for c in spec["criteria"]}
    invalidated = sorted(
        check_id for check_id, check in spec["checks"].items()
        if check_id in existing["checks"] and existing["checks"][check_id]["definition_digest"] != check["definition_digest"]
        and check_id in existing.get("results", {}))
    invalidated += sorted(removed_checks & set(existing.get("results", {})))
    needed = bool(existing["scope"] != spec["scope"] or existing["kind"] != spec["kind"] or
                  existing["automated_waiver"] != spec["automated_waiver"] or removed_checks or removed_criteria or invalidated)
    return needed, invalidated

# ---------------------------------------------------------------- row lookup

def _load(root, path, args):
    path, text = task_tracking._owned_text(args, root, path)
    items, start, end = task_tracking._parse(text)
    version, _width = task_tracking._format(text)
    if version != "v2":
        raise ValueError("Completion evidence requires a v2 ledger")
    item = next((item for item in items if item["id"] == args.id), None)
    if item is None:
        raise ValueError(f"Unknown task ID: {args.id}")
    if item.get("parent"):
        raise ValueError(f"Completion evidence applies to deliverables only; {args.id} is a step")
    block = load_block(text)
    return path, text, items, start, end, item, block

def _write(path, text, items, start, end, block, logs):
    changed = task_tracking._mutated(text, items, start, end, "v2", logs)
    changed = splice_block(changed, render_block(block))
    task_tracking._atomic(path, changed)
    return changed

# ---------------------------------------------------------------- accept

def _read_input(value):
    data = sys.stdin.read() if value == "-" else Path(value).expanduser().read_text()
    try:
        return json.loads(data)
    except json.JSONDecodeError as error:
        raise ValueError(f"Spec input is not valid JSON: {error}") from error

def cmd_accept(args, root, path):
    if args.from_brief:
        payload = task_brief.parse_brief(Path(args.from_brief).expanduser().read_text())
    else:
        payload = _read_input(args.input)
    with task_tracking._lock(root, path):
        path, text, items, start, end, _item, block = _load(root, path, args)
        existing = block["deliverables"].get(args.id)
        if args.from_brief and existing is not None:
            payload = task_brief.merge_spec(existing, payload)
        spec = _build_spec(payload, root)
        needs_reason, invalidated = _reason_needed(existing, spec)
        if needs_reason and not args.reason:
            raise ValueError("Changing an evidence spec with recorded results requires --reason")
        spec["spec_at"] = _now()
        spec["results"] = dict(existing["results"]) if existing else {}
        block["deliverables"][args.id] = spec
        extra = {"brief": args.from_brief} if args.from_brief else {}
        logs = [task_rules.log_line(args.id, "accept", reason=args.reason or "",
                                     invalidated=",".join(invalidated), **extra)]
        _write(path, text, items, start, end, block, logs)
    return {"file": str(path), "updated": path.stat().st_mtime}

# ---------------------------------------------------------------- evidence file placement (§12.11.8)

def _resolve_evidence_path(root, raw):
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise ValueError(f"Evidence file not found: {raw}")
    return resolved

def _is_inside_scope(resolved, scoped_abs):
    return any(resolved == scoped or resolved.is_relative_to(scoped) for scoped in scoped_abs)

def _validate_evidence_paths(method, scope, root, paths):
    if not paths:
        raise ValueError(f"{method} check needs at least one evidence file")
    scoped = set(scope["paths"]) | set(scope.get("dependencies", [])) | set(scope.get("inputs", []))
    scoped_abs = {(root / item).resolve() for item in scoped}
    evidence = []
    for raw in paths:
        resolved = _resolve_evidence_path(root, raw)
        inside = _is_inside_scope(resolved, scoped_abs)
        if method in ("document", "analysis") and not inside:
            raise ValueError(f"{method} evidence must lie inside the declared scope: {raw}")
        if method in ("command", "review", "inspection") and inside:
            raise ValueError(f"evidence for {method} checks must lie outside the declared scope: {raw}")
        evidence.append({"path": str(resolved), "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest()})
    return evidence

def _assert_fresh(evidence_info, started_at_iso):
    # A small tolerance absorbs clock/filesystem-mtime jitter around the start instant itself.
    started = datetime.fromisoformat(started_at_iso.replace("Z", "+00:00")) - timedelta(seconds=1)
    mtime = datetime.fromtimestamp(Path(evidence_info["path"]).stat().st_mtime, timezone.utc)
    if mtime < started:
        raise ValueError(f"Evidence log was not modified during the run: {evidence_info['path']}")

# ---------------------------------------------------------------- outcome resolution (§12.11.3/4)

def _resolve_command_result(check, evidence, raw_result):
    if raw_result != "pass" or check["method"] != "command":
        return raw_result
    expect = check["expect"]
    if "none" in expect:
        return "pass"
    text = "\n".join(Path(info["path"]).read_text(errors="replace") for info in evidence)
    patterns_ok = all(re.search(pattern, text) for pattern in expect.get("patterns", []))
    reject_ok = not any(re.search(pattern, text) for pattern in expect.get("reject", []))
    return "pass" if patterns_ok and reject_ok else "inconclusive"

def _wins(candidate, current):
    if candidate["started_at"] != current["started_at"]:
        return candidate["started_at"] > current["started_at"]
    return current["result"] in GATE_OK and candidate["result"] not in GATE_OK

def _apply_finish(root, path, block, items, deliverable_id, check_id, run_id, run,
                   raw_result, evidence_paths, reason, exit_code, executor):
    spec = block["deliverables"][deliverable_id]
    check = spec["checks"][check_id]
    if run["definition_digest"] != check["definition_digest"]:
        raise ValueError("check definition changed since start; finish refused")
    evidence = _validate_evidence_paths(check["method"], spec["scope"], root, evidence_paths)
    if check["method"] == "command":
        for info in evidence:
            _assert_fresh(info, run["started_at"])
        result = _resolve_command_result(check, evidence, raw_result)
    else:
        result = raw_result
    if result not in OUTCOMES:
        raise ValueError(f"Invalid result: {result}")
    if result == "unavailable" and not reason:
        raise ValueError("unavailable needs --reason")
    state_after = deliverable_state(root, spec, path)
    entry = {"result": result, "started_at": run["started_at"], "finished_at": _now(),
              "state_before": run["state_before"], "state_after": state_after, "evidence": evidence,
              "definition_digest": check["definition_digest"], "reason": reason, "executor": executor}
    if exit_code is not None:
        entry["exit"] = exit_code
    block["runs"].pop(run_id, None)
    current = spec["results"].get(check_id)
    logs = [task_rules.log_line(deliverable_id, "check_finish", check=check_id, run=run_id,
                                 result=result, executor=executor, reason=reason or "")]
    if current is None or _wins(entry, current):
        spec["results"][check_id] = entry
    item = next(row for row in items if row["id"] == deliverable_id)
    if item["status"] == "done" and result not in GATE_OK:
        item["status"] = "in_progress"
        spec.pop("completed", None)
        logs.append(task_rules.log_line(deliverable_id, "status", **{
            "from": "done", "to": "in_progress", "reason": f"check {check_id} {result}"}))
    return logs

# ---------------------------------------------------------------- check start/finish/run/attribute

def cmd_check_start(args, root, path):
    with task_tracking._lock(root, path):
        path, text, items, start, end, _item, block = _load(root, path, args)
        spec = block["deliverables"].get(args.id)
        if spec is None:
            raise ValueError(f"No evidence spec recorded for {args.id}; run accept first")
        check = spec["checks"].get(args.check)
        if check is None:
            raise ValueError(f"Unknown check {args.check} for {args.id}")
        run_id = secrets.token_hex(16)
        run = {"deliverable": args.id, "check": args.check, "definition_digest": check["definition_digest"],
               "state_before": deliverable_state(root, spec, path), "started_at": _now(), "open": True}
        block["runs"][run_id] = run
        logs = [task_rules.log_line(args.id, "check_start", check=args.check, run=run_id)]
        _write(path, text, items, start, end, block, logs)
    return {"file": str(path), "run": run_id}

def cmd_check_finish(args, root, path):
    with task_tracking._lock(root, path):
        path, text, items, start, end, _item, block = _load(root, path, args)
        run = block["runs"].get(args.run)
        if run is None:
            raise ValueError(f"Run {args.run} already finished or unknown")
        if run["deliverable"] != args.id or run["check"] != args.check:
            raise ValueError("Run does not match the given deliverable and check")
        logs = _apply_finish(root, path, block, items, args.id, args.check, args.run, run,
                              args.result, args.evidence, args.reason, None, "attested")
        _write(path, text, items, start, end, block, logs)
    return {"file": str(path), "result": args.result}

def _resolve_cwd(root, cwd):
    candidate = Path(cwd)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if resolved != root and not resolved.is_relative_to(root):
        raise ValueError("check cwd must remain inside the repository")
    return resolved

def _default_log_path(root, path, deliverable_id, check_id):
    key = hashlib.sha256(f"{root}\0{path}".encode()).hexdigest()[:16]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return task_tracking._state_dir() / "evidence" / key / f"{deliverable_id}-{check_id}-{stamp}.log"

def _validate_log_path(root, spec, log_path):
    scope = spec["scope"]
    scoped_abs = {(root / item).resolve() for item in set(scope["paths"]) | set(scope.get("dependencies", [])) | set(scope.get("inputs", []))}
    probe = log_path.resolve() if log_path.exists() else log_path.parent.resolve() / log_path.name
    if _is_inside_scope(probe, scoped_abs):
        raise ValueError(f"check log must lie outside the declared scope: {log_path}")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not os.access(log_path.parent, os.W_OK):
        raise ValueError(f"log directory is not writable: {log_path.parent}")

def _execute(command, cwd, log_path, timeout):
    with open(log_path, "wb") as log:
        try:
            proc = subprocess.Popen(["bash", "-c", command], cwd=cwd, stdout=log,
                                     stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as error:
            log.write(f"\n[fsa-task] failed to launch: {error}\n".encode())
            return 127, False
        try:
            return proc.wait(timeout=timeout), False
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait()
            return None, True

def _map_exit(exit_code, timed_out):
    if timed_out:
        return "timeout", f"timeout after the configured window"
    if exit_code == 0:
        return "pass", None
    if exit_code in (126, 127):
        return "unavailable", f"exit {exit_code}: command unavailable"
    return "fail", None

def cmd_check_run(args, root, path):
    with task_tracking._lock(root, path):
        path, text, items, start, end, _item, block = _load(root, path, args)
        spec = block["deliverables"].get(args.id)
        if spec is None:
            raise ValueError(f"No evidence spec recorded for {args.id}; run accept first")
        check = spec["checks"].get(args.check)
        if check is None or check["method"] != "command":
            raise ValueError(f"{args.check} is not a command check")
        log_path = Path(args.log).expanduser() if args.log else _default_log_path(root, path, args.id, args.check)
        log_path = log_path if log_path.is_absolute() else root / log_path
        _validate_log_path(root, spec, log_path)
        run_id = secrets.token_hex(16)
        run = {"deliverable": args.id, "check": args.check, "definition_digest": check["definition_digest"],
               "state_before": deliverable_state(root, spec, path), "started_at": _now(), "open": True}
        block["runs"][run_id] = run
        logs = [task_rules.log_line(args.id, "check_start", check=args.check, run=run_id)]
        _write(path, text, items, start, end, block, logs)
        cwd, command = _resolve_cwd(root, check.get("cwd", ".")), check["command"]
    timeout = args.timeout or DEFAULT_TIMEOUT
    exit_code, timed_out = _execute(command, cwd, log_path, timeout)
    raw_result, reason = _map_exit(exit_code, timed_out)
    with task_tracking._lock(root, path):
        path, text, items, start, end, _item, block = _load(root, path, args)
        run = block["runs"].get(run_id)
        if run is None or not run["open"]:
            raise ValueError("Run vanished before finish; ledger changed unexpectedly")
        logs = _apply_finish(root, path, block, items, args.id, args.check, run_id, run, raw_result,
                              [str(log_path)], reason, exit_code, "tool")
        _write(path, text, items, start, end, block, logs)
    return {"file": str(path), "run": run_id, "result": block["deliverables"][args.id]["results"][args.check]["result"],
            "log": str(log_path)}

def _read_log_text(evidence):
    parts = []
    for info in evidence:
        try:
            parts.append(Path(info["path"]).read_text(errors="replace"))
        except OSError:
            continue
    return "\n".join(parts)

def cmd_check_attribute(args, root, path):
    with task_tracking._lock(root, path):
        path, text, items, start, end, _item, block = _load(root, path, args)
        spec = block["deliverables"].get(args.id)
        if spec is None:
            raise ValueError(f"No evidence spec recorded for {args.id}")
        check = spec["checks"].get(args.check)
        if check is None or check["method"] != "command":
            raise ValueError(f"{args.check} is not a command check")
        result = spec["results"].get(args.check)
        if result is None or result["result"] != "fail":
            raise ValueError("attribute requires the check's latest result to be a fail")
        baseline = block["baselines"].get(args.baseline)
        if baseline is None:
            raise ValueError(f"Unknown baseline: {args.baseline}")
        if baseline["command"] != check["command"]:
            raise ValueError("baseline command does not match the check command")
        missing = [signature for signature in baseline["signatures"] if signature not in _read_log_text(result["evidence"])]
        if missing:
            raise ValueError(f"result log is missing baseline signatures: {missing}")
        if not _is_ancestor(root, baseline["ref"]):
            raise ValueError("baseline ref is not an ancestor of HEAD")
        if not args.reason:
            raise ValueError("attribute requires --reason")
        attributed = {"result": result, "baseline": args.baseline, "ref": baseline["ref"],
                      "recorded_at": baseline["recorded_at"]}
        spec["results"][args.check] = {**result, "result": "baseline", "attributed": attributed, "reason": args.reason}
        logs = [task_rules.log_line(args.id, "attribute", check=args.check, baseline=args.baseline, reason=args.reason)]
        _write(path, text, items, start, end, block, logs)
    return {"file": str(path), "result": "baseline"}

# ---------------------------------------------------------------- baseline

def cmd_baseline(args, root, path):
    with task_tracking._lock(root, path):
        path, text = task_tracking._owned_text(args, root, path)
        items, start, end = task_tracking._parse(text)
        version, _width = task_tracking._format(text)
        if version != "v2":
            raise ValueError("Completion evidence requires a v2 ledger")
        block = load_block(text)
        if not _is_ancestor(root, args.ref):
            raise ValueError("baseline ref must be an ancestor of HEAD")
        log_path = Path(args.log).expanduser()
        log_path = log_path if log_path.is_absolute() else root / log_path
        if not log_path.is_file():
            raise ValueError(f"Baseline log not found: {args.log}")
        log_text = (log_bytes := log_path.read_bytes()).decode(errors="replace")
        missing = [signature for signature in args.signature if signature not in log_text]
        if missing:
            raise ValueError(f"Baseline log is missing signatures: {missing}")
        block["baselines"][args.id] = {
            "command": args.baseline_command, "ref": args.ref, "log": str(log_path.resolve()),
            "log_sha256": hashlib.sha256(log_bytes).hexdigest(), "signatures": list(args.signature),
            "state": _baseline_code_state(root, args.ref), "reason": args.reason, "recorded_at": _now()}
        logs = [task_rules.log_line(args.id, "baseline", command=args.baseline_command, ref=args.ref,
                                     reason=args.reason)]
        _write(path, text, items, start, end, block, logs)
    return {"file": str(path)}

# ---------------------------------------------------------------- verify / gate (§12.5, §12.11.10)

def _check_report(root, spec, check_id, current_state):
    check = spec["checks"][check_id]
    result = spec["results"].get(check_id)
    if result is None:
        return {"method": check["method"], "status": "missing"}, f"{check_id}: no result recorded"
    if result["definition_digest"] != check["definition_digest"]:
        return {"method": check["method"], "status": "stale (definition changed)"}, f"{check_id}: check definition changed since this result"
    if result["result"] not in GATE_OK:
        label = "attested, not executed by fsa-task" if result.get("executor") == "attested" else result["result"]
        return {"method": check["method"], "status": result["result"]}, f"{check_id}: {label}"
    if result["state_before"]["digest"] != result["state_after"]["digest"]:
        return {"method": check["method"], "status": "changed during verification"}, f"{check_id}: changed during verification"
    if current_state is not None and result["state_after"]["digest"] != current_state["digest"]:
        return {"method": check["method"], "status": "stale"}, f"{check_id}: stale, scope changed since this result"
    altered = [info for info in result["evidence"] if not Path(info["path"]).is_file()
               or hashlib.sha256(Path(info["path"]).read_bytes()).hexdigest() != info["sha256"]]
    if altered:
        return {"method": check["method"], "status": "evidence missing or altered"}, f"{check_id}: evidence missing or altered"
    if result["result"] == "baseline":
        if (attributed := result.get("attributed")) is None:
            return {"method": check["method"], "status": "baseline result without attribution"}, f"{check_id}: baseline result without attribution"
        baseline = spec.get("_baselines", {}).get(attributed["baseline"])
        if baseline is None:
            return {"method": check["method"], "status": "baseline missing"}, f"{check_id}: baseline entry no longer exists"
        if baseline["command"] != check["command"]:
            return {"method": check["method"], "status": "baseline mismatch"}, f"{check_id}: baseline command no longer matches"
        if not (log_path := Path(baseline["log"])).is_file() or hashlib.sha256(log_path.read_bytes()).hexdigest() != baseline["log_sha256"]:
            return {"method": check["method"], "status": "baseline log missing or altered"}, f"{check_id}: baseline log missing or altered"
    status = "accepted" if result.get("executor") != "attested" else "accepted (attested, not executed by fsa-task)"
    return {"method": check["method"], "status": status}, None

def build_report(root, block, deliverable_id, ledger_path=None):
    spec = block["deliverables"].get(deliverable_id)
    if spec is None:
        return {"id": deliverable_id, "ok": False, "blocking": ["no evidence spec recorded; run accept"], "checks": {}}
    spec = {**spec, "_baselines": block["baselines"]}
    used_checks = sorted({check_id for criterion in spec["criteria"] for check_id in criterion["checks"]})
    checks_report, blocking = {}, []
    current_state = None
    try:
        current_state = deliverable_state(root, spec, ledger_path)
    except ValueError as error:
        blocking.append(str(error))
    for check_id in used_checks:
        entry, problem = _check_report(root, spec, check_id, current_state)
        checks_report[check_id] = entry
        if problem is not None:
            blocking.append(problem)
    return {"id": deliverable_id, "ok": not blocking, "blocking": blocking, "checks": checks_report,
            "scope": spec["scope"], "kind": spec["kind"]}

def render_report_text(report):
    lines = [f"{report['id']}: {'ready for done' if report['ok'] else 'blocked'}"]
    for check_id, entry in report["checks"].items():
        lines.append(f"  {check_id} ({entry['method']}): {entry['status']}")
    if not report["ok"]:
        lines.append("Blocking:")
        lines.extend(f"  - {reason}" for reason in report["blocking"])
    if "scope" in report:
        lines.append(f"scope: {json.dumps(report['scope'], ensure_ascii=False)}")
    return "\n".join(lines)

def require_done(block, deliverable_id, root, ledger_path=None):
    """Raise ValueError(verify report) when the gate blocks; else stamp completion onto block and return log lines."""
    report = build_report(root, block, deliverable_id, ledger_path)
    if not report["ok"]:
        raise ValueError(render_report_text(report))
    spec = block["deliverables"][deliverable_id]
    spec["completed"] = {"at": _now(), "with": {check_id: spec["results"][check_id]["result"] for check_id in report["checks"]}}
    accepted = ", ".join(sorted(report["checks"]))
    return [task_rules.log_line(deliverable_id, "done_gate", accepted=accepted)]

def cmd_verify(args, root, path):
    path = task_tracking._file(root, args.file)
    text = task_tracking._read(path)
    items, _start, _end = task_tracking._parse(text)
    version, _width = task_tracking._format(text)
    if version != "v2":
        raise ValueError("Completion evidence requires a v2 ledger")
    item = next((row for row in items if row["id"] == args.id), None)
    if item is None:
        raise ValueError(f"Unknown task ID: {args.id}")
    if item.get("parent"):
        raise ValueError(f"Completion evidence applies to deliverables only; {args.id} is a step")
    block = load_block(text)
    return build_report(root, block, args.id, path)

def print_verify(args, root, path):
    report = cmd_verify(args, root, path)
    print(json.dumps(report, ensure_ascii=False) if args.json else render_report_text(report))

# ---------------------------------------------------------------- show/summary completion kinds

def completion_kind(block, deliverable_id):
    spec = block["deliverables"].get(deliverable_id)
    if spec is None or not spec.get("completed"):
        return "unrecorded"
    if any(result == "baseline" for result in spec["completed"]["with"].values()):
        return "evidence_with_baseline"
    return "evidence"

def completion_counts(items):
    counts = {"evidence": 0, "evidence_with_baseline": 0, "unrecorded": 0}
    for item in items:
        if item.get("completion") in counts:
            counts[item["completion"]] += 1
    return counts
