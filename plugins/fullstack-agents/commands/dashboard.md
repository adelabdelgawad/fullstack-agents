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

The session Information view includes a **Tasks** section when the lead registers a task
Markdown file with `scripts/fsa-task`. It updates from that file and links to its source;
see the task-flow skill task-tracking reference.

The Agents view lists orchestrators in a left sidebar and as cards (stage, branch, plan, workers,
cost, context); clicking one opens its details beside the cards. Fleet tiles cover sessions,
waiting, workers, context blowouts, Claude and Codex plan usage and tokens per minute; the navbar
holds Activity, the Wall mode switch and the theme. Each card shows its context fill, compactions (`N×`) and estimated cost, and a square per worker
coloured by model. History lists the last 48 hours of sessions with tokens and cost. Press `w`
for wall mode. Costs are estimates from transcript token counts and a price table; override it
in `~/.config/fullstack-agents/prices.json` (or `FSA_PRICES`) as
`{"model-prefix": {"input": $/MTok, "output": $/MTok, "cache_read": $/MTok, "window": tokens}}`.
Common secret patterns (API keys, bearer tokens, JWTs, private keys, URL passwords, password and
token fields) are redacted from JSON and text responses; the live terminal is not.
Plan tiles show subscription usage per window (5 h, week): Claude from the signed-in account's usage
endpoint (the token stays on the server, polled at most once a minute), Codex from its newest
rollout's rate limits. `scripts/fsa-usage` prints the current session's context fill, estimated
cost and both plans' usage.
