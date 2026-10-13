#!/usr/bin/env python3
"""Dispatch one bounded Codex unit; preserve Codex leadership and audit its scope."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from handoff import BUNDLE, git, repo_path


def block(text, name):
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not re.fullmatch(re.escape(name) + r":[ \t]*", line):
            continue
        values = []
        for value in lines[index + 1:]:
            if not value.strip() or re.match(r"^[A-Z_]+:", value.strip()):
                break
            values.append(value.strip().removeprefix("- ").strip())
        return values
    return []


def snapshot(root, content_paths=(), exclude=None):
    names = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")
    ignored = git(root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z").decode().split("\0")
    result = {}
    for name in names:
        if not name:
            continue
        if exclude and (root / name).is_relative_to(exclude):
            continue
        path = root / name
        if path.is_symlink():
            result[name] = "link:" + os.readlink(path)
        elif path.is_file():
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            result[name] = "absent"
    # Ignored trees can be large: metadata catches ordinary writes without
    # hashing every dependency/build artifact. Explicit paths use content hashes.
    for name in ignored:
        if not name or (exclude and (root / name).is_relative_to(exclude)):
            continue
        path = root / name
        if path.is_symlink():
            result[name] = "link:" + os.readlink(path)
        elif path.is_file():
            if name in content_paths:
                result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            else:
                stat = path.stat()
                result[name] = f"stat:{stat.st_ino}:{stat.st_size}:{stat.st_mtime_ns}:{stat.st_ctime_ns}:{stat.st_mode}"
    # Detect forbidden commits/config/ref edits without flagging routine index
    # refreshes produced by read-only git commands.
    for metadata in ("HEAD", "config", "packed-refs"):
        raw_path = Path(git(root, "rev-parse", "--git-path", metadata).decode().strip())
        path = raw_path if raw_path.is_absolute() else root / raw_path
        result[".git/" + metadata] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "absent"
    refs = subprocess.run(["git", "-C", str(root), "show-ref"], capture_output=True)
    if refs.returncode not in (0, 1):
        raise ValueError("cannot snapshot Git refs")
    result[".git/refs"] = hashlib.sha256(refs.stdout).hexdigest()
    return result


def worker(args):
    root = args.root.resolve()
    text = args.brief.read_text()
    if len(text) > 16000:
        raise ValueError("brief exceeds 16000 characters; narrow the unit")
    if args.mode == "implement" and not re.search(r"^PLAN:[ \t]*\S", text, re.M):
        raise ValueError("implementation brief requires PLAN:")
    if args.mode == "investigate" and not re.search(r"^REPORT:[ \t]*\S", text, re.M):
        raise ValueError("investigation brief requires REPORT:")
    key = "ALLOWED_PATHS" if args.mode == "implement" else "FILES"
    paths = list(dict.fromkeys(repo_path(root, value) for value in block(text, key)))
    if not 1 <= len(paths) <= args.max_paths:
        raise ValueError(f"brief requires a {key}: block with one to {args.max_paths} exact paths")
    skill_match = re.search(r"^SKILLS:[ \t]*([^\r\n]+)$", text, re.M)
    if skill_match:
        names = re.split(r"[ ,]+", skill_match[1].strip())
    else:
        names = []
        if any(path.endswith(".py") for path in paths):
            names.append("fastapi")
        if any(path.endswith(".rs") for path in paths):
            names.append("rust-correctness")
        if any(path.endswith((".ts", ".tsx")) for path in paths):
            names.append("nextjs")
    skills = []
    for name in dict.fromkeys(names):
        if not name.startswith("fullstack-agents-"):
            name = "fullstack-agents-" + name
        if not re.fullmatch(r"fullstack-agents-[a-z0-9-]+", name):
            raise ValueError(f"invalid skill name: {name}")
        path = BUNDLE / "skills" / name / "SKILL.md"
        if not path.is_file():
            raise ValueError(f"unknown skill: {name}")
        skills.append(str(path))
    prompt = ("ROLE: bounded Codex worker. The Codex lead owns planning and the final audit; Claude only supplies audit findings. "
              "Do not delegate, dispatch workers, call Claude, change permissions, commit or deploy. "
              "Read project instructions that apply to the listed paths. The brief defines your scope. "
              "Search first, then bounded ranges; load the listed skill files once, only relevant references. "
              "Use a supplied style profile rather than scanning the repository again. "
              "For implementation, edit only ALLOWED_PATHS. If another path is needed, stop and put it in open_risks. "
              "Run only the brief's authorized checks. Save full logs, return concise evidence.\n"
              + "SKILL_FILES:\n" + "\n".join(skills) + "\n\n" + text)
    run = Path(tempfile.mkdtemp(prefix="fsa-codex-worker-", dir=args.runs_dir)).resolve()
    before = snapshot(root, paths, exclude=run)
    (run / "prompt.txt").write_text(prompt)
    output = run / "result.json"
    command = ["codex", "exec", "--cd", str(root), "--sandbox",
               "workspace-write" if args.mode == "implement" else "read-only",
               "--output-schema", str(BUNDLE / "schemas/worker.schema.json"),
               "--output-last-message", str(output), "--json"]
    if args.model:
        command += ["--model", args.model]
    # Prevent nested workers; explicit CLI runtime overrides win over defaults.
    command += ["-c", "agents.enabled=false", "-"]
    timed_out = False
    error = None
    with (run / "events.jsonl").open("w") as stdout, (run / "stderr.txt").open("w") as stderr:
        try:
            process = subprocess.run(command, input=prompt, cwd=root, text=True,
                                     stdout=stdout, stderr=stderr, timeout=args.timeout)
            returncode = process.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            returncode = 2
        except OSError as failure:
            error = str(failure)
            returncode = 2
    after = snapshot(root, paths, exclude=run)
    touched = sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))
    outside = [name for name in touched if name not in (paths if args.mode == "implement" else [])]
    valid_result = False
    if returncode == 0 and output.is_file():
        try:
            result = json.loads(output.read_text())
            valid_result = (isinstance(result, dict) and set(result) == {"summary", "files", "tests", "open_risks"}
                            and isinstance(result["summary"], str)
                            and all(isinstance(result[key], list) and all(isinstance(item, str) for item in result[key])
                                    for key in ("files", "tests", "open_risks")))
        except (ValueError, OSError):
            pass
    status = "OUT_OF_SCOPE" if outside else "INCOMPLETE" if returncode or not valid_result else "COMPLETE"
    manifest = {"status": status, "mode": args.mode, "root": str(root), "paths": paths,
                "touched": touched, "outside_scope": outside, "timed_out": timed_out,
                "error": error, "exit_code": returncode, "run": str(run), "result": str(output)}
    (run / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))
    # Never restore somebody else's tree or pretend scope auditing blocked edits.
    return 0 if status == "COMPLETE" else 3 if outside else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["investigate", "implement"])
    parser.add_argument("brief", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path)
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-paths", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    try:
        if min(args.max_paths, args.timeout) <= 0:
            raise ValueError("limits must be positive")
        return worker(args)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, f"worker incomplete: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
