"""Parse an implementer brief into a completion-evidence spec payload, and merge repair briefs.

See plugins/fullstack-agents/skills/task-flow/references/skill-guide.md "Briefs" (the ACCEPTANCE
syntax) and docs/TASK_LIFECYCLE_DESIGN.md §14.6 item 8.
"""
import re

TAG_LINE = re.compile(r"^([A-Z][A-Z_]*):(.*)$")
LIST_TAGS = ("ALLOWED_PATHS", "AFFECTED_TESTS", "DEPENDS", "INPUTS", "ENV")
ITEM_LINE = re.compile(r"^(\d+)\.\s*(.*)$")
TAG_SPLIT = re.compile(r"\b(check|review|inspection|document|analysis):")
ITEM_SPLIT = re.compile(r";\s*(?=(?:check|review|inspection|document|analysis):)")
NONE_REASON = re.compile(r"^none\s*\((.*)\)\s*$")
BUILD_SILENT_REASON = "compile/lint success is silent"


def _collect_list(lines, index, inline):
    if inline.strip():
        return [inline.strip()], index + 1
    values = []
    index += 1
    while index < len(lines) and lines[index].strip() and not TAG_LINE.match(lines[index]):
        values.append(lines[index].strip())
        index += 1
    return values, index


def _collect_text(lines, index, inline):
    parts = [inline.strip()] if inline.strip() else []
    index += 1
    while index < len(lines) and lines[index].strip() and not TAG_LINE.match(lines[index]):
        parts.append(lines[index].strip())
        index += 1
    return " ".join(parts), index


def _parse_tags(text):
    lines = text.splitlines()
    tags, acceptance = {}, []
    index = 0
    while index < len(lines):
        match = TAG_LINE.match(lines[index])
        if not match:
            index += 1
            continue
        name, inline = match.group(1), match.group(2)
        if name == "ACCEPTANCE":
            if inline.strip():
                acceptance.append(inline.strip())
            index += 1
            while index < len(lines) and not TAG_LINE.match(lines[index]):
                if lines[index].strip():
                    acceptance.append(lines[index].strip())
                index += 1
            continue
        if name in LIST_TAGS:
            tags[name], index = _collect_list(lines, index, inline)
        else:
            tags[name], index = _collect_text(lines, index, inline)
    return tags, acceptance


def _split_dependencies(values):
    if len(values) == 1 and (match := NONE_REASON.match(values[0])):
        return [], match.group(1).strip()
    return values, None


def _rightmost_outside_quotes(text, tag):
    """Last " tag:" that isn't inside a '...' or "..." span, or -1 if there is none."""
    needle, quote, last = f" {tag}:", None, -1
    for index, char in enumerate(text):
        if quote:
            quote = None if char == quote else quote
        elif char in "\"'":
            quote = char
        elif text.startswith(needle, index):
            last = index
    return last


def _split_check_chunk(chunk):
    expect_at = _rightmost_outside_quotes(chunk, "expect")
    if expect_at == -1:
        raise ValueError(f"command check needs expect: {chunk.strip()}")
    command = chunk[:expect_at].strip()
    rest = chunk[expect_at + len(" expect:"):].strip()
    cwd = None
    cwd_at = _rightmost_outside_quotes(rest, "cwd")
    if cwd_at != -1:
        cwd = rest[cwd_at + len(" cwd:"):].strip()
        rest = rest[:cwd_at].strip()
    if (match := NONE_REASON.match(rest)):
        expect = {"none": match.group(1).strip()}
    else:
        expect = {"patterns": [rest]}
    check = {"method": "command", "command": command, "expect": expect}
    if cwd:
        check["cwd"] = cwd
    return check


def _parse_acceptance(acceptance_lines):
    criteria, checks = [], {}
    command_n, other_n = 0, 0
    item_number, item_text = None, []
    items = []
    for line in acceptance_lines:
        match = ITEM_LINE.match(line)
        if match:
            if item_number is not None:
                items.append((item_number, " ".join(item_text)))
            item_number, item_text = match.group(1), [match.group(2)]
        elif item_number is not None:
            item_text.append(line)
    if item_number is not None:
        items.append((item_number, " ".join(item_text)))
    for number, full_text in items:
        tag_match = TAG_SPLIT.search(full_text)
        if not tag_match:
            raise ValueError(f"ACCEPTANCE item {number} has no verification tag: {full_text}")
        text = full_text[:tag_match.start()].rstrip(" -—:;")
        check_ids = []
        for chunk in ITEM_SPLIT.split(full_text[tag_match.start():]):
            chunk = chunk.strip()
            method_match = TAG_SPLIT.match(chunk)
            if not method_match:
                raise ValueError(f"ACCEPTANCE item {number} has an unrecognised tag: {chunk}")
            method = method_match.group(1)
            rest = chunk[method_match.end():]
            if method == "check":
                command_n += 1
                check_id = f"C{command_n}"
                checks[check_id] = _split_check_chunk(rest)
            else:
                other_n += 1
                check_id = f"R{other_n}"
                checks[check_id] = {"method": method}
            check_ids.append(check_id)
        criteria.append({"id": number, "text": text, "checks": check_ids})
    return criteria, checks


def parse_brief(text):
    """Parse a brief's ALLOWED_PATHS/ACCEPTANCE/DEPENDS/... tags into a `task_evidence._build_spec` payload."""
    tags, acceptance_lines = _parse_tags(text)
    criteria, checks = _parse_acceptance(acceptance_lines)
    if "BUILD" in tags:
        expect = {"patterns": [tags["BUILD_EXPECT"]]} if tags.get("BUILD_EXPECT") else {"none": BUILD_SILENT_REASON}
        checks["BUILD"] = {"method": "command", "command": tags["BUILD"], "expect": expect}
        criteria.append({"id": "BUILD", "text": "BUILD passes", "checks": ["BUILD"]})
    if not tags.get("SCOPE_WHY", "").strip():
        raise ValueError("Brief is missing SCOPE_WHY")
    dependencies, dependencies_none = _split_dependencies(tags.get("DEPENDS", []))
    scope = {"paths": sorted(set(tags.get("ALLOWED_PATHS", [])) | set(tags.get("AFFECTED_TESTS", []))),
             "dependencies": dependencies, "inputs": tags.get("INPUTS", []), "env": tags.get("ENV", []),
             "rationale": tags["SCOPE_WHY"]}
    if dependencies_none is not None:
        scope["dependencies_none"] = dependencies_none
    return {"kind": tags.get("KIND", "code").strip() or "code", "scope": scope, "criteria": criteria, "checks": checks}


def _merge_scope(existing, new):
    merged = {
        "paths": sorted(set(existing.get("paths", [])) | set(new.get("paths", []))),
        "dependencies": sorted(set(existing.get("dependencies", [])) | set(new.get("dependencies", []))),
        "inputs": sorted(set(existing.get("inputs", [])) | set(new.get("inputs", []))),
        "env": sorted(set(existing.get("env", [])) | set(new.get("env", []))),
        "rationale": new.get("rationale") or existing.get("rationale"),
    }
    dependencies_none = new.get("dependencies_none", existing.get("dependencies_none"))
    if dependencies_none is not None:
        merged["dependencies_none"] = dependencies_none
    return merged


def _merge_criteria(existing, new):
    by_id = {criterion["id"]: criterion for criterion in existing}
    order = [criterion["id"] for criterion in existing]
    for criterion in new:
        if criterion["id"] not in by_id:
            order.append(criterion["id"])
        by_id[criterion["id"]] = criterion
    return [by_id[identifier] for identifier in order]


def merge_spec(existing, new):
    """Union scope lists, replace/add criteria and checks by id, keep what the new brief omits."""
    return {"kind": new["kind"], "scope": _merge_scope(existing["scope"], new["scope"]),
            "automated_waiver": new.get("automated_waiver", existing.get("automated_waiver")),
            "criteria": _merge_criteria(existing["criteria"], new["criteria"]),
            "checks": {**existing["checks"], **new["checks"]}}
