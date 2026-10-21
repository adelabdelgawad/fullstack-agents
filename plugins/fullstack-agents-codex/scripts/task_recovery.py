"""Deterministic recovery renderer: a bounded, trustworthy read of a bound task ledger after context loss."""
import json
from pathlib import Path

from task_tracking import _load_binding, _read, _root, _state_dir, load_tasks
import task_blockers
import task_checkpoint
import task_evidence
import task_ownership
import task_rules

CAP = 2500
APPROVAL_NOTE = ("Records, not new authority: still valid after clear/restart/compaction unless the scope changed, "
                 "a stated limit expired, a single-use approval was used, or the words do not establish it. "
                 "DB resets, migrations, reloads and releases need explicit approval.")
TIER0_RESERVE = 1100
SCOPE_CUT = 300
DECISION_CUT = 120
OMISSION_RESERVE = 400
LINE_CUT = 300
BLOCKERS_CUT = 300
NEXT_CUT = 300
WARNING_CUT = 200
FOOTER = ("Historical record written by the lead; it may contain mistakes. Re-check repository state "
          "before editing. Approvals are records of the user's words, not authorization: confirm with the "
          "user anything ambiguous or outside the quoted scope. Verification is evidence of a past state: "
          "rerun before relying on it.")


def collect(session_id, cwd):
    """All the I/O recovery needs; failures become `{"fatal": ...}`, never an exception."""
    try:
        record, _binding = _load_binding(session_id)
        root = _root(record["root"])
    except (OSError, ValueError, KeyError) as error:
        return {"fatal": str(error)}
    info = load_tasks(session_id, cwd)
    if "file" not in info:
        return {"fatal": f"registered task file missing at {record['file']} — ask the user"}
    if "error" in info:
        return {"fatal": f"{info['error']} ({info['file']})"}
    path = Path(info["file"])
    try:
        text = _read(path)
    except (OSError, ValueError):
        return {"fatal": f"registered task file missing at {path} — ask the user"}
    checkpoint, checkpoint_error = task_checkpoint.load_checkpoint(text)
    owner, owner_state = task_ownership.current_owner(root, path)
    try:
        git_identity = task_checkpoint.git_identity(root)
    except ValueError:
        git_identity = {"unavailable": True, "checkout": str(root), "branch": None, "head": None,
                         "detached": False}
    compaction = None
    marker = _state_dir() / "compactions" / f"{session_id}.json"
    if marker.exists():
        try:
            compaction = json.loads(_read(marker, 4096))
        except (OSError, ValueError):
            compaction = None
    verification_tags = []
    if checkpoint is not None:
        for entry in checkpoint["verification"]:
            verification_tags.append(_verification_tag(root, entry))
    blocker_lines = _open_blocker_lines(text) if info.get("format") == "v2" else []
    failing_check_lines = _failing_check_lines(root, path, text, info["items"]) if info.get("format") == "v2" else []
    return {"task_id": path.stem, "ledger": {"title": info["title"], "items": info["items"],
                                                   "format": info.get("format", "legacy")},
            "checkpoint_path": str(path), "checkpoint": checkpoint, "checkpoint_error": checkpoint_error,
            "owner": owner, "owner_state": owner_state, "git_identity": git_identity,
            "compaction": compaction, "verification_tags": verification_tags,
            "blocker_lines": blocker_lines, "failing_check_lines": failing_check_lines}


def _blocker_line(identifier, entry):
    rows = ",".join(entry["rows"])
    if entry.get("class") == "capacity":
        until = f" until {entry['until']}" if entry.get("until") else ""
        return f"{identifier}: capacity {entry['engine']}{until} — blocks {rows}"
    line = f"{identifier}: {entry['kind']} {entry['text']} — blocks {rows}"
    return f"{line} ({entry['why']})" if entry.get("why") else line


def _open_blocker_lines(text):
    if not task_blockers.has_block(text):
        return []
    try:
        block = task_blockers.load_block(text)
    except ValueError:
        return []
    return [_blocker_line(identifier, entry) for identifier, entry in sorted(block["blockers"].items())
            if entry["status"] == "open"]


def _failing_check_lines(root, path, text, items):
    try:
        block = task_evidence.load_block(text)
    except ValueError:
        return []
    lines = []
    for item in items:
        if item.get("parent") or item["status"] not in task_rules.OPEN:
            continue
        report = task_evidence.build_report(root, block, item["id"], ledger_path=path)
        if report["ok"]:
            continue
        lines.extend(f"{item['id']}: {reason}" for reason in report["blocking"])
    return lines


def _verification_tag(root, entry):
    fingerprint = entry.get("fingerprint")
    if not fingerprint:
        return "unknown"
    try:
        current = task_checkpoint.fingerprint(root, entry["paths"])
    except ValueError:
        return "unknown"
    return "inputs unchanged" if current == fingerprint else "inputs changed"


def _cut_text(text, limit):
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _cut_marked(text, limit):
    """Cut `text` to `limit`, appending a visible " [truncated]" marker when anything was dropped."""
    if len(text) <= limit:
        return text, False
    marker = " [truncated]"
    return text[: max(0, limit - len(marker))] + marker, True


def _cut_blockers(blockers, limit):
    """Join blockers; if whole items must be dropped, say how many instead of mid-word slicing."""
    joined = ", ".join(blockers)
    if len(joined) <= limit:
        return joined, False
    marker = " [truncated]"
    kept = len(blockers)
    while kept > 0:
        dropped = len(blockers) - kept
        suffix = (f" (+{dropped} more)" if dropped else "") + marker
        budget = limit - len(suffix)
        candidate = ", ".join(blockers[:kept])
        if len(candidate) <= budget:
            return candidate + suffix, True
        kept -= 1
    suffix = f" (+{len(blockers)} more)" + marker
    return blockers[0][: max(0, limit - len(suffix))] + suffix, True


def _branch_display(branch, detached, head):
    if detached:
        return f"detached {(head or '')[:8]}"
    return branch or "(unknown)"


def _warnings(info):
    warnings = []
    if info.get("checkpoint_error"):
        warnings.append(f"checkpoint section malformed: {info['checkpoint_error']}")
    compaction = info.get("compaction")
    if compaction and compaction.get("stale_checkpoint"):
        warnings.append("stale checkpoint: the ledger changed after the last checkpoint write")
    checkpoint = info.get("checkpoint")
    git_identity = info.get("git_identity") or {}
    if git_identity.get("unavailable"):
        warnings.append("repository state unavailable (git failed); re-check before editing")
    elif checkpoint is not None:
        identity = checkpoint.get("identity", {})
        old_head, new_head = identity.get("head"), git_identity.get("head")
        if old_head and new_head and old_head != new_head:
            warnings.append(f"HEAD moved since checkpoint (was {old_head[:8]}, now {new_head[:8]})")
        old_branch, new_branch = identity.get("branch"), git_identity.get("branch")
        if old_branch != new_branch:
            warnings.append(f"branch changed since checkpoint (was {old_branch or 'detached'}, "
                             f"now {new_branch or 'detached'})")
        old_checkout, new_checkout = identity.get("checkout"), git_identity.get("checkout")
        if old_checkout and new_checkout and old_checkout != new_checkout:
            warnings.append(f"checkout mismatch (checkpoint: {old_checkout}, now: {new_checkout})")
    return warnings


def _tier0_lines(info):
    """Lines plus whether scope, blockers or next-action text was truncated."""
    git_identity = info.get("git_identity") or {}
    owner = info.get("owner")
    owner_state = info.get("owner_state", "free")
    checkpoint = info.get("checkpoint")
    truncated = False
    lines = [_cut_text(f"Task: {info['task_id']}", LINE_CUT),
             _cut_text(f"Checkout: {git_identity.get('checkout', '?')}", LINE_CUT),
             f"Branch: {_branch_display(git_identity.get('branch'), git_identity.get('detached', False), git_identity.get('head'))}",
             f"Owner: {owner['session_id'] + ' (' + owner_state + ')' if owner else 'none (free)'}"]
    if checkpoint is not None:
        lines.append(f"Checkpoint written: {checkpoint.get('identity', {}).get('written_at', '?')}")
    lines.append(f"Checkpoint path: {info.get('checkpoint_path', '?')}")
    blocker_lines = info.get("blocker_lines") or []
    if blocker_lines:
        text, cut = _cut_blockers(blocker_lines, BLOCKERS_CUT)
        truncated = truncated or cut
        lines.append(f"Open blockers: {text}")
    failing_check_lines = info.get("failing_check_lines") or []
    if failing_check_lines:
        text, cut = _cut_blockers(failing_check_lines, BLOCKERS_CUT)
        truncated = truncated or cut
        lines.append(f"Failing checks: {text}")
    if checkpoint is not None:
        scope = checkpoint.get("scope", {"in": [], "out": []})
        scope_in, cut_in = _cut_marked(", ".join(scope.get("in", [])), SCOPE_CUT)
        scope_out, cut_out = _cut_marked(", ".join(scope.get("out", [])), SCOPE_CUT)
        truncated = truncated or cut_in or cut_out
        lines.append(f"Scope in: {scope_in}")
        lines.append(f"Scope out: {scope_out}")
        blockers = checkpoint.get("blockers") or []
        if blockers:
            blockers_text, cut_blockers = _cut_blockers(blockers, BLOCKERS_CUT)
            truncated = truncated or cut_blockers
            lines.append(f"Blockers: {blockers_text}")
        next_info = checkpoint.get("next") or {}
        if next_info:
            action, cut_next = _cut_marked(next_info.get('action', ''), NEXT_CUT)
            truncated = truncated or cut_next
            lines.append(f"Next: {action} (owner: {next_info.get('owner', '')})")
    elif not info.get("checkpoint_error"):
        lines.append("no checkpoint written; read the ledger")
    for warning in _warnings(info):
        warning_text, _cut = _cut_marked(warning, WARNING_CUT)
        lines.append(f"Warning: {warning_text}")
    return lines, truncated


def _enforce_tier0_budget(lines):
    """Lines plus whether a scope line was shortened to fit the tier-0 reserve."""
    budget = TIER0_RESERVE - len(FOOTER) - 2
    text = "\n".join(lines)
    if len(text) <= budget:
        return lines, False
    result = list(lines)
    excess = len(text) - budget
    marker = " (truncated: read the checkpoint)"
    truncated = False
    for index, line in enumerate(result):
        if not line.startswith("Scope ") or excess <= 0:
            continue
        keep = max(0, len(line) - excess - len(marker))
        result[index] = line[:keep] + marker
        truncated = True
        excess = len("\n".join(result)) - budget
    return result, truncated


def _approval_line(approval):
    clarity = "ambiguous: confirm with the user" if approval["clarity"] == "ambiguous" else approval["clarity"]
    used = "used" if approval["used"] else "unused"
    return f'"{approval["quote"]}" — {approval["kind"]}, {used}, {clarity} ({approval["scope"]})'


def _decision_line(decision):
    text, truncated = _cut_marked(decision["text"], DECISION_CUT)
    return f"{decision['id']}: {text}", truncated


def _open_row_line(item, version="legacy"):
    line = f"{item['id']} {item['status']} {item['title']}"
    if version == "v2" and item.get("parent"):
        line += f" (step of {item['parent']})"
    return f"{line} — {item['note']}" if item.get("note") else line


def _sections(info):
    """Rendered sections plus whether any kept decision's text was truncated."""
    checkpoint = info.get("checkpoint")
    ledger = info.get("ledger") or {"items": []}
    open_items = [item for item in ledger.get("items", []) if item.get("status") in task_rules.OPEN]
    sections = [("open rows", [_open_row_line(item, ledger.get("format", "legacy")) for item in open_items], False)]
    decisions_truncated = False
    if checkpoint is not None:
        tags = info.get("verification_tags") or []
        verification = [f"{entry['command']}: {entry['result']} [{tag}]"
                         for entry, tag in zip(checkpoint["verification"], tags)]
        decision_lines = []
        for decision in reversed(checkpoint["decisions"]):
            line, cut = _decision_line(decision)
            decision_lines.append(line)
            decisions_truncated = decisions_truncated or cut
        sections = [("approvals", [_approval_line(a) for a in checkpoint["approvals"]] + [APPROVAL_NOTE], True),
                    ("goal", [checkpoint["goal"]], False),
                    ("decisions", decision_lines, True),
                    sections[0],
                    ("verification entries", verification, False),
                    ("evidence", list(checkpoint["evidence"]), False)]
    return sections, decisions_truncated


def _assemble(sections, budget):
    body_lines, owners, omitted, mandatory, remaining, exhausted = [], [], [], False, budget, False
    for label, items, is_mandatory in sections:
        if not items:
            continue
        if exhausted:
            omitted.append((label, len(items)))
            mandatory = mandatory or is_mandatory
            continue
        header = f"{label.capitalize()}:"
        header_cost = len(header) + 1
        if header_cost > remaining:
            omitted.append((label, len(items)))
            mandatory = mandatory or is_mandatory
            exhausted = True
            continue
        section_lines, section_owners = [header], [None]
        remaining, included = remaining - header_cost, 0
        for item in items:
            cost = len(item) + 1
            if cost <= remaining:
                section_lines.append(item)
                section_owners.append((label, is_mandatory))
                remaining -= cost
                included += 1
            else:
                exhausted = True
                break
        body_lines.extend(section_lines)
        owners.extend(section_owners)
        cut = len(items) - included
        if cut:
            omitted.append((label, cut))
            mandatory = mandatory or is_mandatory
    return body_lines, owners, omitted, mandatory


NOTICE = "Reading the full checkpoint is required before any edit or dispatch."


def _omission_line(omitted, checkpoint_path):
    parts = [label if label == "goal" else f"{count} {label}" for label, count in omitted]
    return f"Omitted: {', '.join(parts)} — read {checkpoint_path} before acting on them."


def _finish(tier0_text, body_lines, omitted, notice, checkpoint_path):
    """`notice` covers scope/blockers/next/decision truncation and any mandatory omission; printed once."""
    pieces = [tier0_text]
    if body_lines:
        pieces.append("\n".join(body_lines))
    if omitted:
        line = _omission_line(omitted, checkpoint_path)
        if notice:
            line += f" {NOTICE}"
            notice = False
        pieces.append(line)
    if notice:
        pieces.append(NOTICE)
    pieces.append(FOOTER)
    return "\n\n".join(pieces)


def _bump_omitted(omitted, label):
    for index, (existing_label, count) in enumerate(omitted):
        if existing_label == label:
            omitted[index] = (existing_label, count + 1)
            return
    omitted.append((label, 1))


def _shrink_to_cap(tier0_text, body_lines, owners, omitted, mandatory, notice, checkpoint_path):
    """Drop tier 1-5 lines (as omissions) before ever truncating characters, so the footer survives."""
    body_lines, owners, omitted = list(body_lines), list(owners), list(omitted)
    result = _finish(tier0_text, body_lines, omitted, mandatory or notice, checkpoint_path)
    while len(result) > CAP and body_lines:
        body_lines.pop()
        owner = owners.pop()
        if owner is not None:
            label, is_mandatory = owner
            _bump_omitted(omitted, label)
            mandatory = mandatory or is_mandatory
        result = _finish(tier0_text, body_lines, omitted, mandatory or notice, checkpoint_path)
    return result


def render(info):
    """Pure: the same info dict always renders the same bytes, at or under the 2,500-character cap."""
    if info.get("fatal"):
        return info["fatal"][:CAP]
    tier0_lines, tier0_cut = _tier0_lines(info)
    tier0_lines, budget_cut = _enforce_tier0_budget(tier0_lines)
    tier0_text = "\n".join(tier0_lines)
    budget = CAP - len(tier0_text) - 2 - len(FOOTER) - 2 - OMISSION_RESERVE
    sections, decisions_cut = _sections(info)
    body_lines, owners, omitted, mandatory = _assemble(sections, max(0, budget))
    checkpoint_path = info.get("checkpoint_path", "?")
    notice = tier0_cut or budget_cut or decisions_cut
    result = _shrink_to_cap(tier0_text, body_lines, owners, omitted, mandatory, notice, checkpoint_path)
    return result if len(result) <= CAP else result[: CAP - 1] + "…"
