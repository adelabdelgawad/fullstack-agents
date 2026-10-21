"""Ledger version upgrade/downgrade commands, split out of task_tracking."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import task_tracking
import task_rules


def _cmd_upgrade(args, root, path):
    with task_tracking._lock(root, path):
        path, text = task_tracking._owned_text(args, root, path)
        items, start, end = task_tracking._parse(text)
        version, width = task_tracking._format(text)
        if version == "v2":
            raise ValueError("Ledger is already v2")
        line = task_rules.log_line("", "upgrade", **{"from": width})
        changed = text[:start] + task_tracking._render(items, "v2") + text[end:]
        if changed.count(task_tracking.LOG_START) == changed.count(task_tracking.LOG_END) == 1:
            changed = task_tracking._append_log(changed, line)
        else:
            changed += f"\n\n## Task log\n{task_tracking.LOG_START}\n{line}{task_tracking.LOG_END}\n"
        if len(changed.encode()) > task_tracking.MAX_BYTES:
            raise ValueError("ledger too large: close or split it")
        task_tracking._parse(changed)
        path = task_tracking._file(root, args.file)
        task_tracking._atomic(path, changed)
    return {"file": str(path), "updated": path.stat().st_mtime}


def _upgrade_width(text):
    body = text[text.index(task_tracking.LOG_START) + len(task_tracking.LOG_START):text.index(task_tracking.LOG_END)]
    matches = re.findall(r' upgrade from="([47])"(?:\s|$)', body)
    if not matches:
        raise ValueError("v2 ledger has no valid upgrade width")
    return int(matches[-1])


def _cmd_downgrade(args, root, path):
    with task_tracking._lock(root, path):
        path, text = task_tracking._owned_text(args, root, path)
        items, start, end = task_tracking._parse(text)
        version, _width = task_tracking._format(text)
        if version != "v2":
            raise ValueError("downgrade requires a v2 ledger")
        import task_evidence
        if task_evidence.has_block(text):
            raise ValueError("Cannot downgrade; an evidence block exists (run fsa-task verify to inspect it)")
        verifying = [item["id"] for item in items if item["status"] == "verifying"]
        parented = [item["id"] for item in items if item["parent"]]
        if verifying or parented:
            details = ([f"verifying: {', '.join(verifying)}"] if verifying else []) + ([f"parented: {', '.join(parented)}"] if parented else [])
            raise ValueError("Cannot downgrade; " + "; ".join(details))
        width = _upgrade_width(text)
        if width == 4 and any(item[key] for item in items for key in ("owner", "activity", "active_until")):
            width = 7
        changed = task_tracking._mutated(text, items, start, end, "legacy", [task_rules.log_line("", "downgrade", to=width)], width)
        path = task_tracking._file(root, args.file)
        task_tracking._atomic(path, changed)
    return {"file": str(path), "updated": path.stat().st_mtime}
