---
name: fullstack-agents-rust-nextjs-contract
description: "Wire-contract parity for Rust APIs serving the shared Next.js frontend — camelCase JSON matching CamelModel output, limit/skip pagination, search and is_active filters, list envelopes with total, Bearer auth, and route prefixes, so Rust and FastAPI services are interchangeable behind the same frontend. Use when exposing ANY Rust endpoint that Next.js (or the existing fetch-architecture) will consume. Do not use for service-to-service-only APIs with their own contract."
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

- Line 11: JSON Casing — camelCase, always
- Line 36: Pagination — limit/skip query params
- Line 72: Filters
- Line 82: Auth & Headers
- Line 93: Routes & Mounting
- Line 111: Type Bindings (recommended)
- Line 118: Verification Checklist (per endpoint)
