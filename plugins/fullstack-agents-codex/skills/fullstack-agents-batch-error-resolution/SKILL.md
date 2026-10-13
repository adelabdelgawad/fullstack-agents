---
name: fullstack-agents-batch-error-resolution
description: "Resolve multiple build, compile, test, lint, or type-check errors as one batch operation — fix all errors first, then verify once. Use when a build, test suite, linter, or type checker reports several failures at the same time. Do not use for a single isolated error that can be fixed and verified immediately."
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

- Line 5: When to Use This Skill
- Line 16: Core Principle
- Line 22: The Process
- Line 55: Strict Rules
- Line 77: Error Collection Format
- Line 82: Collected Errors (7 total)
- Line 101: Resolution Strategies
- Line 139: Quick Reference
- Line 148: Common Mistakes
- Line 157: Benefits
