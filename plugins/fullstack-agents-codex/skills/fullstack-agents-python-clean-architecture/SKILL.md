---
name: fullstack-agents-python-clean-architecture
description: "Clean Architecture + DDD for Python (FastAPI) microservices — pure domain layer with value objects and entities, application use cases owning transactions, repository ports as Protocols, SQLAlchemy adapters in infrastructure, and a four-stage error model. Use when creating or structuring a NEW Python microservice or applying DDD to Python. Do not use for the existing simplified FastAPI pattern (use fastapi — codebase-scanning decides which applies) and never for Rust services (use rust-clean-architecture)."
---

## Codex runtime binding

Follow the bundle's `AGENTS.md` and `fullstack-agents-task-flow`: Codex leads,
Claude audits bounded diffs through `scripts/handoff.py`. Read only relevant
skill sections once. Existing user authorization wins over historical approval
steps. Native Codex roles replace Claude tools/dispatchers/hooks below. Bundle
paths resolve from the bundle; skill paths resolve beside `SKILL.md`. Validate
explicitly; do not assume historical hooks or dashboards are running.

# Python Clean Architecture + DDD

New Python microservices use these rules; existing simplified services retain
`fastapi`. Dependencies point inward; domain stays framework-free. Application
ports are Protocols implemented in infrastructure. Use cases own transactions;
repositories receive sessions rather than independently opening/committing them.
Use fallible value objects and four-stage errors; preserve API wire contracts.
Read Layer Rules, transaction/error requirements before relevant examples.
Never copy Rust idioms.

## Detailed guide

Complete rules/examples: [references/skill-guide.md](references/skill-guide.md).
Read shared requirements and relevant sections before acting. Use bounded reads
(200 lines by default, project limits win); do not load every example or reread
sections still in context. Prose/code paths resolve beside this `SKILL.md`;
Markdown links are relocated.

- Line 12: Service Layout
- Line 42: Layer Rules
- Line 56: DDD Building Blocks
- Line 115: Ports as Protocols
- Line 141: Use Cases Own Transactions
- Line 165: Four-Stage Error Model
- Line 192: Composition Root
- Line 217: Testing (mirrors rust-testing)
- Line 228: Forbidden Patterns
