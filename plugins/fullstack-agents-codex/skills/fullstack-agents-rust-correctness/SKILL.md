---
name: fullstack-agents-rust-correctness
description: "Rust correctness — ownership, borrowing, lifetimes, async and Send/Sync hazards, error handling, compiler errors E0382/E0499/E0502/E0597. For any non-trivial Rust."
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

- Line 7: Ownership & Borrowing
- Line 21: Panic vs Result
- Line 29: Async Concurrency (Tokio)
- Line 43: Smart Pointer Selection
- Line 56: Lifetimes
- Line 63: Traits & Generics
- Line 71: Pattern Matching
- Line 78: Iterators & Collections
- Line 85: Unsafe
- Line 91: Compiler Error Quick-Route
