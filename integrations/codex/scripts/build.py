#!/usr/bin/env python3
"""Render a standalone Codex bundle from the shared Claude engineering content."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

PREFIX = "fullstack-agents-"
ADAPTER = Path(__file__).resolve().parents[1]
SOURCE = ADAPTER.parents[1] / "plugins" / "fullstack-agents"
RUNTIME = """## Codex runtime binding

Follow the bundle's `AGENTS.md` and `fullstack-agents-task-flow`: Codex leads,
Claude audits bounded diffs through `scripts/handoff.py`. Read only relevant
skill sections once. Existing user authorization wins over historical approval
steps. Native Codex roles replace Claude tools/dispatchers/hooks below. Bundle
paths resolve from the bundle; skill paths resolve beside `SKILL.md`. Validate
explicitly; do not assume historical hooks or dashboards are running.

"""

BARE_METAL_COORDINATION = """
Project execution bindings outrank the generic worktree rule above. When project
instructions bind bare-metal development to an existing checkout and branch, use
that same checkout and do not create another worktree. Resolve this binding before
branch or worktree decisions, including when the session starts in a stale default
checkout.
"""


def frontmatter(text):
    """The repository manifests use scalar, single-line names and descriptions."""
    if not text.startswith("---\n"):
        return {}, text
    header, body = text[4:].split("\n---\n", 1)
    fields = {}
    for line in header.splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            fields[key] = value.strip().strip("\"'")
    return fields, body.lstrip()


def manifest(name, description, body):
    # JSON-quoted strings are also valid YAML scalars.
    return f"---\nname: {name}\ndescription: {json.dumps(description, ensure_ascii=False)}\n---\n\n{body}"


def adapt(text, skill_names):
    text = text.replace("fullstack-agents:", PREFIX)
    for name in sorted(skill_names, key=len, reverse=True):
        text = text.replace(f"skills/{name}/", f"skills/{PREFIX}{name}/")
        text = text.replace(f"../{name}/", f"../{PREFIX}{name}/")
        # Bare cross-skill references are bundle paths, not local references.
        text = re.sub(r"(?<![\w/.-])" + re.escape(name) + r"/references/",
                      f"skills/{PREFIX}{name}/references/", text)
    text = text.replace("`Skill` tool", "skill file reader")
    text = text.replace("Skill tool", "skill file reader")
    text = text.replace("`TaskCreate`", "the lead's task tracker")
    text = text.replace("`TaskUpdate`", "the lead's task tracker")
    text = text.replace("Never use the Read tool on skill files.", "Read the skill file directly.")
    text = re.sub(r"\bClaude\b", "Codex", text)
    text = re.sub(r"\b(?:Sonnet|Haiku|Opus)(?:\s+\d+(?:\.\d+)*)?\b", "the configured Codex model", text)
    text = re.sub(r"`/(generate|review|analyze|scaffold|debug|optimize|validate|status)\b",
                  lambda match: "`$" + PREFIX + match[1], text)
    return text


def compact_entry(body):
    """Keep the skill entry small; retain the full rules as indexed references."""
    # Line ranges make section reads deterministic without loading every example.
    lines = body.splitlines()
    headings = [(index + 1, line.removeprefix("## "))
                for index, line in enumerate(lines) if line.startswith("## ")]
    index = "\n".join(f"- Line {line}: {title}" for line, title in headings)
    return (RUNTIME + "## Engineering guide\n\n"
            "The complete adapted rules are in [references/engineering-guide.md](references/engineering-guide.md). "
            "Before acting, read its relevant requirements/checklist sections and only the examples you need. "
            "Start with the section index below and read at most 200 lines per call. "
            "Load the complete guide only when the task spans all of it. "
            "Paths inside that guide remain relative to this skill directory, beside `SKILL.md`. "
            "Project patterns and the constitution win over template defaults.\n\n" + index + "\n")


def relocate_links(body):
    """The full guide moved one directory down; keep Markdown links clickable."""
    def replace(match):
        target = match[1]
        if target.startswith(("https:", "http:", "#", "/")):
            return match[0]
        if target.startswith("skills/"):
            target = "../../../" + target
        else:
            target = "../" + target
        return "](" + target + ")"
    return re.sub(r"\]\(([^\s)]+)\)", replace, body)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def render(output):
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("build destination must be empty")
    skill_names = [p.name for p in sorted((SOURCE / "skills").iterdir()) if p.is_dir()]
    for name in skill_names:
        target = output / "skills" / (PREFIX + name)
        shutil.copytree(SOURCE / "skills" / name, target)
        for path in target.rglob("*.md"):
            metadata, body = frontmatter(path.read_text())
            if path.name == "SKILL.md":
                override = ADAPTER / "skills" / name / "SKILL.md"
                if override.exists():
                    body = override.read_text()
                    if name == "team-coordination":
                        body = body.rstrip() + "\n\n" + BARE_METAL_COORDINATION
                    path.write_text(body)
                elif (SOURCE / "skills" / name / "references/skill-guide.md").is_file():
                    # Shared Claude skills already use progressive disclosure.
                    # Reuse their index; do not wrap or overwrite the full guide.
                    path.write_text(manifest(PREFIX + name,
                                             adapt(metadata["description"], skill_names),
                                             RUNTIME + adapt(body, skill_names)))
                else:
                    guide = adapt(body, skill_names)
                    write(target / "references/engineering-guide.md", relocate_links(guide))
                    path.write_text(manifest(PREFIX + name,
                                             adapt(metadata["description"], skill_names),
                                             compact_entry(guide)))
            else:
                path.write_text(adapt(path.read_text(), skill_names))

    agent_records = []
    for path in sorted((SOURCE / "agents").rglob("*.md")):
        metadata, body = frontmatter(path.read_text())
        relative = path.relative_to(SOURCE / "agents")
        if relative.parts[0] == "_core":
            if path.name == "orchestration.md":
                body = "# Codex orchestration\n\nUse `fullstack-agents-task-flow`. Keep bounded path lists, sequential workers by default, and Codex ownership of the final audit. Claude returns issues and scope through `scripts/handoff.py`.\n"
            write(output / "agents" / relative, RUNTIME + adapt(body, skill_names))
            continue
        name = PREFIX + metadata["name"]
        description = adapt(metadata["description"], skill_names)
        if path.stem == "fullstack-agent":
            # The entry point is the primary session, never a spawned lead.
            write(output / "agents" / relative, (ADAPTER / "AGENTS.md").read_text())
            continue
        body = RUNTIME + adapt(body, skill_names)
        write(output / "agents" / relative, body)
        instructions = (RUNTIME + f"Role: {description}\n\n"
                        f"Read `.codex/fullstack-agents/agents/{relative.as_posix()}` for the role's requirements, "
                        "using bounded ranges and only relevant examples. Work only on the parent's exact file list. "
                        "Return concise source evidence and saved check logs; do not take over planning or call the Claude auditor yourself.\n")
        role = {"name": name, "description": description, "developer_instructions": instructions}
        readonly = relative.parts[0] in {"review", "analyze"} or path.stem in {"bounded-extractor", "diff-reviewer"}
        if readonly:
            role["sandbox_mode"] = "read-only"
        # Test-runner writes only logs; it needs inherited workspace permissions.
        role_text = "\n".join(f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in role.items()) + "\n"
        write(output / "roles" / f"{name}.toml", role_text)
        agent_records.append({"name": name, "source": str(relative), "read_only": readonly})

    workflow_names = []
    for path in sorted((SOURCE / "commands").glob("*.md")):
        metadata, body = frontmatter(path.read_text())
        if path.stem == "dashboard":
            # The existing dashboard consumes Claude transcripts and is not ported.
            continue
        body = adapt(body, skill_names)
        body = re.sub(r"/(generate|review|analyze|scaffold|debug|optimize|validate|status)\b",
                      lambda match: "$" + PREFIX + match[1], body)
        body = body.replace("claude $fullstack-agents-validate --all --strict",
                            "bash scripts/validate.sh LANE SERVICE_ROOT")
        write(output / "commands" / path.name, RUNTIME + body)
        name = PREFIX + path.stem
        workflow_names.append(name)
        if path.stem in skill_names:
            # debug already has a discipline skill; retain it and attach the workflow.
            skill = output / "skills" / name / "SKILL.md"
            skill.write_text(skill.read_text() + "\n## Workflow reference\n\nFor the explicit debugging workflow, read `references/workflow.md`.\n")
            write(skill.parent / "references" / "workflow.md", RUNTIME + body)
        else:
            write(output / "skills" / name / "SKILL.md",
                  manifest(name, adapt(metadata["description"], skill_names),
                           RUNTIME + f"## Workflow\n\nRead `references/workflow.md` for this workflow. "
                           "Use bounded sections and only the relevant target role. The Codex lead owns planning, "
                           "verification and the Claude audit handoff.\n"))
            write(output / "skills" / name / "references/workflow.md", body)
    shutil.copy2(ADAPTER / "AGENTS.md", output / "AGENTS.md")
    shutil.copy2(ADAPTER / "config.toml.example", output / "config.toml.example")
    (output / "scripts").mkdir(exist_ok=True)
    for name in ("validate.sh", "hook.py", "handoff.py", "worker.py", "phase.py", "tasks.py"):
        shutil.copy2(ADAPTER / "scripts" / name, output / "scripts" / name)
    shutil.copy2(SOURCE / "scripts/lib/task_tracking.py", output / "scripts/task_tracking.py")
    for path in sorted((ADAPTER / "schemas").glob("*.json")):
        write(output / "schemas" / path.name, path.read_text())
    version = json.loads((SOURCE / ".claude-plugin/plugin.json").read_text())["version"]
    plugin = {"name": "fullstack-agents-codex", "version": version,
              "description": "Codex-led Python/Rust/Next.js workflows with progressive skill loading and bounded Claude audit handoffs.",
              "author": {"name": "Adel Abdelgawad"}, "license": "MIT",
              "skills": "./skills/", "hooks": "./hooks/hooks.json"}
    write(output / ".codex-plugin/plugin.json", json.dumps(plugin, indent=2) + "\n")
    hooks = {}
    for event, mode, matcher in (("SessionStart", "start", ""),
                                 ("UserPromptSubmit", "prompt", ""),
                                 ("PostToolUse", "post", "^apply_patch$")):
        group = {"hooks": [{"type": "command", "command": f'python3 "${{PLUGIN_ROOT}}/scripts/hook.py" {mode}',
                             "timeout": 30, "statusMessage": f"Fullstack Agents Codex: {mode}"}]}
        if matcher:
            group["matcher"] = matcher
        hooks[event] = [group]
    write(output / "hooks/hooks.json", json.dumps({"hooks": hooks}, indent=2) + "\n")
    inventory = {"edition": "codex-led-claude-audit", "skills": sorted(p.name for p in (output / "skills").iterdir()),
                 "workflows": workflow_names, "agents": agent_records,
                 "source_hashes": {str(p.relative_to(SOURCE)): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sorted(SOURCE.rglob("*")) if p.is_file()}}
    write(output / "inventory.json", json.dumps(inventory, indent=2) + "\n")
    # Normalize copied text so generated releases pass staged whitespace checks.
    for path in output.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".py", ".sh", ".toml", ".json"}:
            text = path.read_text()
            clean = "\n".join(line.rstrip() for line in text.splitlines()).rstrip() + "\n"
            if clean != text:
                path.write_text(clean)
    return inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        inventory = render(args.output)
        print(f"Rendered {len(inventory['skills'])} skills and {len(inventory['agents'])} native roles in {args.output}")
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, f"build failed: {error}\n")


if __name__ == "__main__":
    main()
