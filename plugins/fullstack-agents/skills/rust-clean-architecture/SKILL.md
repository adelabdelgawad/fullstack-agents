---
name: rust-clean-architecture
description: Rust service structure — workspace crates, domain boundaries, ports and adapters, use-case transactions, and where Rust code belongs.
---

# Rust Clean Architecture + DDD

Crates are layers, modules are features. Domain stays pure/framework-free.
Application owns repository traits and use-case transactions; infrastructure
implements ports. Thread `&mut PgConnection` through ports; no Unit-of-Work or
business logic in Axum handlers. Shared DTOs have no domain/application/infra
dependencies. Parse value objects fallibly; errors map through four stages.
Read Layer Rules, transaction/error requirements before relevant examples.
Rust serves JSON, never a frontend. Next.js consumers also need
`rust-nextjs-contract`. Keep Python idioms out.

## Detailed guide

Complete rules/examples: [references/skill-guide.md](references/skill-guide.md).
Read shared requirements and relevant sections before acting. Use bounded reads
(200 lines by default, project limits win); do not load every example or reread
sections still in context. Prose/code paths resolve beside this `SKILL.md`;
Markdown links are relocated.

- Line 7: Workspace Layout
- Line 29: Layer Rules (compiler-enforced)
- Line 54: DDD Building Blocks
- Line 105: Four-Stage Error Model
- Line 168: Ports & Adapters
- Line 195: Use Cases Own Transactions
- Line 231: Composition Root
- Line 251: Worker (background jobs)
- Line 265: New Entity Checklist (end-to-end)
- Line 279: Tooling (non-negotiable)
- Line 301: Forbidden Patterns
