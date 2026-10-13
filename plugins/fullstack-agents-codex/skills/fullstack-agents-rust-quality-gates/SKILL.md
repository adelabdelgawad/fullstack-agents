---
name: fullstack-agents-rust-quality-gates
description: "Non-skippable verification chain for Rust services — fmt, clippy with deny-warnings, cargo check, sqlx offline-cache drift, audit, migration safety, and the no-allow policy. Use after generating or modifying Rust code, before declaring any Rust work done, or when asked to gate or validate a Rust project. Do not use for Python validation (ruff/mypy are wired separately)."
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

- Line 7: The Chain
- Line 24: Order Matters
- Line 30: Justfile Integration
- Line 45: Workspace Policy (what the gates assume)
- Line 59: CI Mirror
- Line 72: Remediation Map
