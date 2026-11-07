"""Workflow trees: the pinned baseline snapshot, its manifest and HEAD delta, and bounded candidate edits."""
import fnmatch
import io
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path

from common import REPO, manifest, manifest_sha, now, write_json

IGNORE = shutil.ignore_patterns("__pycache__", ".in_use")
EDITABLE = ("skills/*", "agents/*.md", "scripts/lib/roles/*.md")
MAX_CHANGED_LINES = 200
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{5,}")


def read_only(root):
    for p in [Path(root), *Path(root).rglob("*")]:
        if not p.is_symlink():
            p.chmod(p.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def unified(a, b):
    proc = subprocess.run(["diff", "-ruN", "-x", "__pycache__", "-x", ".in_use", str(a), str(b)],
                          capture_output=True, text=True, check=False)
    return proc.stdout.replace(str(a), "a").replace(str(b), "b")


def extract_head(dest, ref="HEAD"):
    """plugins/fullstack-agents as committed at `ref`, extracted under `dest`."""
    archive = subprocess.run(["git", "-C", str(REPO), "archive", ref, "plugins/fullstack-agents"],
                             capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(dest, filter="data")
    return Path(dest) / "plugins/fullstack-agents"


def snapshot(source, dest, ref="HEAD"):
    """Copy an installed plugin tree read-only into `dest/tree`; record its manifest and its delta from `ref`."""
    source, dest = Path(source).resolve(), Path(dest)
    tree = dest / "tree"
    shutil.copytree(source, tree, ignore=IGNORE)
    files = manifest(tree)
    with tempfile.TemporaryDirectory() as tmp:
        head_root = extract_head(tmp, ref)
        head = manifest(head_root)
        (dest / "delta-from-head.diff").write_text(unified(head_root, tree))
    changed = sorted(p for p in set(head) | set(files) if head.get(p) != files.get(p))
    sha = subprocess.run(["git", "-C", str(REPO), "rev-parse", ref], capture_output=True, text=True,
                         check=True).stdout.strip()
    record = {"source": str(source), "created": now(), "files": files, "sha256": manifest_sha(files),
              "delta_from_head": {"ref": ref, "git_sha": sha,
                                  "changed": [{"path": p, "head": head.get(p), "snapshot": files.get(p)}
                                              for p in changed]}}
    write_json(dest / "manifest.json", record)
    read_only(tree)
    return record


def verify(tree, record):
    """Paths whose content differs from the recorded manifest (missing, changed or added)."""
    files = manifest(tree)
    return sorted(p for p in set(files) | set(record["files"]) if files.get(p) != record["files"].get(p))


def editable(path):
    return any(fnmatch.fnmatch(path, pattern) for pattern in EDITABLE)


def changed_lines(diff):
    return sum(1 for line in diff.splitlines()
               if line[:1] in "+-" and not line.startswith(("+++", "---")))


def _code_like(token):
    return "_" in token or any(c.isdigit() for c in token) or (token[0].islower() and token != token.lower())


def task_tokens(patches, task_text):
    """Code-like identifiers and paths from the task and the probe diffs; candidate text using them is flagged."""
    tokens = {t for t in re.findall(r"`([^`\n]{4,80})`", task_text)}
    tokens |= {t for t in TOKEN.findall(task_text) if _code_like(t)}
    for patch in patches:
        for line in patch.splitlines():
            if line.startswith(("+++ b/", "--- a/")):
                tokens.add(line[6:].strip())
            elif line[:1] in "+- ":
                tokens.update(t for t in TOKEN.findall(line) if _code_like(t))
    return tokens


def check_candidate(base_tree, cand_tree, patches, task_text=""):
    """Validate a candidate against the edit allowlist, the size cap and the task-identifier heuristic."""
    base, cand = manifest(base_tree), manifest(cand_tree)
    changed = sorted(p for p in set(base) | set(cand) if base.get(p) != cand.get(p))
    diff = unified(base_tree, cand_tree)
    tokens = task_tokens(patches, task_text)
    hits = set()
    for rel in changed:
        before = (Path(base_tree) / rel).read_text(errors="replace") if rel in base else ""
        after = (Path(cand_tree) / rel).read_text(errors="replace") if rel in cand else ""
        hits |= {t for t in tokens if t in after and t not in before}
    hits = sorted(hits)
    problems = [f"outside allowlist: {p}" for p in changed if not editable(p)]
    if changed_lines(diff) > MAX_CHANGED_LINES:
        problems.append(f"{changed_lines(diff)} changed lines exceed {MAX_CHANGED_LINES}")
    problems += [f"task-specific identifier (heuristic): {t}" for t in hits[:20]]
    return {"changed": changed, "changed_lines": changed_lines(diff), "diff": diff, "identifier_hits": hits,
            "problems": problems, "valid": not problems, "empty": not changed}


def materialize(source_tree, dest):
    """Writable copy of a workflow tree for an improver to edit."""
    shutil.copytree(source_tree, dest, ignore=IGNORE)
    for p in [Path(dest), *Path(dest).rglob("*")]:
        if not p.is_symlink():
            p.chmod(p.stat().st_mode | stat.S_IWUSR)
    return Path(dest)
