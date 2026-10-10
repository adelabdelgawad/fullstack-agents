---
description: Start, stop or show the host-level agent dashboard (survives session close)
argument-hint: start | stop | status
allowed-tools: Bash
---

# Dashboard Command

Run the dashboard control script for the current repository and print its output verbatim.
The server is detached from the session; only `stop` ends it.

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/fsa-dashboard" ${ARGUMENTS:-status}
```

Valid arguments: `start` (prints the URL), `stop`, `status` (URL or "not running").
Any other argument is refused; do not pass `serve` or `state`.
