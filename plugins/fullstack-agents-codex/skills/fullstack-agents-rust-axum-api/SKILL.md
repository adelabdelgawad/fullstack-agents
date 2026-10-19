---
name: fullstack-agents-rust-axum-api
description: "Rust Axum 0.8 handlers, routers, extractors, middleware, error mapping, JWT auth, WebSocket and graceful shutdown."
---

## Codex runtime binding

Follow the bundle's `AGENTS.md` and `fullstack-agents-task-flow`: Codex leads,
Claude audits bounded diffs through `scripts/handoff.py`. Read only relevant
skill sections once. Existing user authorization wins over historical approval
steps. Native Codex roles replace Claude tools/dispatchers/hooks below. Bundle
paths resolve from the bundle; skill paths resolve beside `SKILL.md`. Validate
explicitly; do not assume historical hooks or dashboards are running.

## Engineering guide

The complete adapted rules are in [references/engineering-guide.md](references/engineering-guide.md). Before acting, read its relevant requirements/checklist sections and only the examples you need. Start with the section index below and read at most 200 lines per call. Load the complete guide only when the task spans all of it. Paths inside that guide remain relative to this skill directory, beside `SKILL.md`. Project patterns and the constitution win over template defaults.

- Line 7: Path Syntax — Axum 0.8 CRITICAL
- Line 19: Extractor Ordering
- Line 43: Error Mapping (IntoResponse)
- Line 73: Middleware
- Line 110: WebSocket
- Line 122: Graceful Shutdown
- Line 130: Forbidden Patterns
