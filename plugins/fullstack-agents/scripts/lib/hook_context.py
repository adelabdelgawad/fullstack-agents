#!/usr/bin/env python3
"""Emit hook context for Claude Code without silent truncation.

Claude Code caps each hook's additionalContext (and plain stdout) at 10,000 characters; a longer string reaches the
model only as a 2,000-character preview with no instruction to read the rest. This helper keeps every emitted string
under FSA_HOOK_CONTEXT_MAX characters (default 9,000). When the text is longer, the full text goes to a readable
file and the model receives its leading `--keep` characters (the essential part, placed first by the caller) plus a
notice naming that file.

    printf '%s' "$text" | python3 -I hook_context.py emit --event SessionStart --name core --session "$id" [--keep N]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

DEFAULT_MAX = 9000
SPILL_RETENTION_S = 14 * 86400


def state_home():
    base = os.environ.get("FSA_STATE_HOME")
    if base:
        return Path(base)
    config = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return Path(config) / "fullstack-agents"


def spill(text, name, session):
    directory = state_home() / "context"
    directory.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for old in directory.glob("*.md"):
        try:
            if now - old.stat().st_mtime > SPILL_RETENTION_S:
                old.unlink()
        except OSError:
            pass
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in f"{session or 'nosession'}-{name}")
    path = directory / f"{safe}.md"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return path


def fit(text, name, session, keep, limit):
    if len(text) <= limit:
        return text
    path = spill(text, name, session)
    notice = (f"\n\n[fullstack-agents] CONTEXT INCOMPLETE: the {name} context is {len(text)} characters, over the "
              f"{limit}-character hook limit. Read the complete text now with the Read tool: {path}")
    head = text[:max(0, min(keep, limit - len(notice)))]
    return head + notice


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    emit = sub.add_parser("emit")
    emit.add_argument("--event", required=True)
    emit.add_argument("--name", required=True)
    emit.add_argument("--session", default="")
    emit.add_argument("--keep", type=int, default=2000)
    args = ap.parse_args()
    limit = int(os.environ.get("FSA_HOOK_CONTEXT_MAX", DEFAULT_MAX))
    text = sys.stdin.read()
    if not text.strip():
        return 0
    text = fit(text, args.name, args.session, args.keep, limit)
    # Cursor reads additional_context; Claude Code reads hookSpecificOutput.additionalContext.
    json.dump({"additional_context": text,
               "hookSpecificOutput": {"hookEventName": args.event, "additionalContext": text}}, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
