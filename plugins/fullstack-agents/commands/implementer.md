---
description: Show or switch this session's implementer - claude (claude-sonnet-5-5) or codex (gpt-6.1-sol)
argument-hint: claude | codex
allowed-tools: Bash
---

# Implementer Command

Show or switch the implementer engine that `scripts/codex-task.sh` dispatches through for the CURRENT session,
and print the script's output verbatim. With no argument it only shows the current setting.

```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/lib/agent_config.py" implementer ${ARGUMENTS}
```

Valid arguments: `claude` (implement model `claude-sonnet-5-5`) or `codex` (implement model `gpt-6.1-sol`).
Any other argument is refused by the script; do not retry with another value.

The switch writes the session's agent settings (`~/.claude/fullstack-agents/agents/session-<sid>.json`), the
same file and the same `agent_config.set_implementer` call as the Office's Agent settings Implementer control;
every other setting is kept. The session is the one named by `FSA_SESSION_PIN` (what the dispatcher reads),
else `CLAUDE_CODE_SESSION_ID`. It takes effect from the next dispatch; a brief's `IMPLEMENTER:` line still wins
for that brief.
