---
name: fullstack-agents-rust-axum-api
description: "Axum 0.8 API patterns — curly-brace path syntax, extractor ordering, State via FromRef, IntoResponse error mapping, Tower middleware ordering, JWT auth middleware, WebSocket, and graceful shutdown. Use when writing or reviewing Axum handlers, routers, middleware, or HTTP-layer code in a Rust service. Do not use for FastAPI/Python endpoints (use fastapi or python-clean-architecture) or for business logic (handlers delegate to use cases — see rust-clean-architecture)."
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
