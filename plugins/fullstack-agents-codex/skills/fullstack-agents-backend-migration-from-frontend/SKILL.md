---
name: fullstack-agents-backend-migration-from-frontend
description: "Migrate a backend to a new framework by reverse-engineering behavior from the frontend — trace every UI request down through router, controller, middleware, service, repository, DB, jobs, events, and side effects, then reproduce equivalent behavior (validation, permissions, transactions, responses, status codes, logging, caching, events) in the target. Use when porting/rewriting a backend and behavioral equivalence with the existing app matters. Do not use for greenfield backends (use fastapi / python-clean-architecture / rust-clean-architecture) or pure frontend migrations (use frontend-transformation)."
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

- Line 3: Objective
- Line 17: When to Use This Skill
- Line 29: How This Fits the Plugin
- Line 42: Investigation Phase
- Line 50: Recursive Backend Discovery
- Line 65: Build a Complete Mental Model
- Line 74: Never Guess
- Line 81: Cross References
- Line 92: Migration Rules
- Line 104: Missing Logic Policy
- Line 111: Validation Before Completion
- Line 122: Completion Criteria
