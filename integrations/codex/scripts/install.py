#!/usr/bin/env python3
"""Install only the independent Codex adapter; preserve all Claude files."""
import argparse
import hashlib
import json
import os
import shlex
import shutil
import tempfile
from pathlib import Path

from build import render

MARKER = ".fullstack-agents-install.json"


def digest(path):
    if path.is_symlink():
        return "link:" + os.readlink(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    temporary.replace(path)


def install(root, dry_run=False):
    if not root.is_dir():
        raise ValueError("target must be an existing project directory")
    root = root.resolve()
    marker = root / ".codex" / MARKER
    if marker.is_symlink():
        raise ValueError("installer manifest must not be a symlink")
    previous = json.loads(marker.read_text()) if marker.exists() else {"files": {}}
    with tempfile.TemporaryDirectory(prefix="fsa-codex-install-") as scratch:
        bundle = Path(scratch) / "bundle"
        inventory = render(bundle)
        files = {}
        links = {}
        base = Path(".codex/fullstack-agents")
        for path in bundle.rglob("*"):
            if path.is_file():
                files[str(base / path.relative_to(bundle))] = path.read_bytes()
        for path in (bundle / "roles").glob("*.toml"):
            files[str(Path(".codex/agents") / path.name)] = path.read_bytes()
        for name in inventory["skills"]:
            links[str(Path(".agents/skills") / name)] = f"../../.codex/fullstack-agents/skills/{name}"
        # Existing Codex model/sandbox/approval settings are never overwritten.
        config = root / ".codex/config.toml"
        if not config.exists():
            files[".codex/config.toml"] = (bundle / "config.toml.example").read_bytes()
        hooks_path = root / ".codex/hooks.json"
        hook_config = json.loads(hooks_path.read_text()) if hooks_path.exists() else {"hooks": {}}
        hooks = hook_config.setdefault("hooks", {})
        for event, mode, matcher in (("SessionStart", "start", ""),
                                     ("UserPromptSubmit", "prompt", ""),
                                     ("PostToolUse", "post", "^apply_patch$")):
            # Remove only this integration's own groups, retaining user hooks.
            groups = [group for group in hooks.get(event, [])
                      if not any(handler.get("statusMessage") == f"Fullstack Agents Codex: {mode}"
                                 for handler in group.get("hooks", []))]
            command = "python3 " + shlex.quote(str(root / base / "scripts/hook.py")) + " " + mode
            group = {"hooks": [{"type": "command", "command": command, "timeout": 30,
                                 "statusMessage": f"Fullstack Agents Codex: {mode}"}]}
            if matcher:
                group["matcher"] = matcher
            groups.append(group)
            hooks[event] = groups
        files[".codex/hooks.json"] = (json.dumps(hook_config, indent=2) + "\n").encode()
        owned = previous["files"]
        desired = {**{name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
                   **{name: "link:" + target for name, target in links.items()}}
        # Preflight every path before any mutation; refuse symlinked parent dirs.
        for name in set(desired) | set(owned):
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts or relative.parts[0] not in {".codex", ".agents"}:
                raise ValueError(f"invalid managed path: {name}")
            path = root / relative
            for parent in path.parents:
                if parent == root:
                    break
                if parent.is_symlink():
                    raise ValueError(f"symlinked installation parent: {parent}")
            if path.exists() or path.is_symlink():
                if name in {".codex/hooks.json", ".codex/config.toml"}:
                    if path.is_symlink() or not path.is_file():
                        raise ValueError(f"configuration is not a regular file: {name}")
                    continue
                if not path.is_file() and not path.is_symlink():
                    raise ValueError(f"installation collision: {name}")
                actual = digest(path)
                if actual != desired.get(name) and actual != owned.get(name):
                    raise ValueError(f"refusing to overwrite unowned or modified file: {name}")
        if dry_run:
            print(f"Would install {len(inventory['skills'])} skills and {len(inventory['agents'])} roles into {root}; Claude files untouched")
            return
        for name in set(owned) - set(desired):
            if name in {".codex/config.toml", ".codex/hooks.json"}:
                continue
            path = root / name
            if path.is_file() or path.is_symlink():
                path.unlink()
        for name, content in files.items():
            atomic_write(root / name, content)
        for name, target in links.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.is_symlink() and os.readlink(path) == target:
                continue
            if path.exists() or path.is_symlink():
                path.unlink()
            path.symlink_to(target, target_is_directory=True)
        atomic_write(marker, (json.dumps({"edition": inventory["edition"], "files": desired}, indent=2) + "\n").encode())
    print(f"Installed Codex-led Fullstack Agents into {root}")
    print("Start Codex in that project. Review/trust the new hooks with /hooks.")
    print("Bootstrap explicitly with $fullstack-agents-using-fullstack-agents if hooks are disabled.")
    print("Claude integration unchanged. Claude CLI is used only for bounded audits.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        install(args.project, args.dry_run)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"installation failed: {error}\n")


if __name__ == "__main__":
    main()
