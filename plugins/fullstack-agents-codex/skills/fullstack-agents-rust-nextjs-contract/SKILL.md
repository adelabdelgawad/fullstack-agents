---
name: fullstack-agents-rust-nextjs-contract
description: "Wire contract for Rust endpoints consumed by Next.js — camelCase JSON, pagination, filters, list envelopes, auth, route prefixes and OpenAPI."
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
