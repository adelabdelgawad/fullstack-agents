---
name: python-clean-architecture
description: Clean Architecture and DDD for a new Python (FastAPI) microservice — domain, use cases, repository ports, SQLAlchemy adapters. Existing simplified FastAPI uses fastapi.
---

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
