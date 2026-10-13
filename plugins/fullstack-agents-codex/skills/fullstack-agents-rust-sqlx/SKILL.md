---
name: fullstack-agents-rust-sqlx
description: "SQLx + PostgreSQL patterns for Rust services — compile-time-verified query macros, Executor-generic repository functions, FromRow type mapping, pool configuration, migration discipline, offline cache for CI, and SQLSTATE error mapping. Use when writing Rust database code, repositories, migrations, or queries. Do not use for SQLAlchemy/Python data access (use fastapi or python-clean-architecture)."
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

- Line 7: Query Macro Selection
- Line 35: Executor-Generic Functions
- Line 53: Type Mapping
- Line 68: Transactions
- Line 79: Pool Configuration
- Line 91: Migrations
- Line 101: Offline Cache (CI without a database)
- Line 110: Error Mapping (SQLSTATE)
- Line 122: Forbidden Patterns
