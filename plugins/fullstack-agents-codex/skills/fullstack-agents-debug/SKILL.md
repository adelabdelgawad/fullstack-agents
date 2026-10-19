---
name: fullstack-agents-debug
description: "Any bug, error, unexpected behavior, slow page, long loading skeleton or latency complaint — establish the root cause before any fix."
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

- Line 3: The Iron Law
- Line 9: When to Use
- Line 17: The Process
- Line 76: Red Flags — STOP and Return to Phase 1
- Line 91: Common Rationalizations
- Line 105: Quick Reference
- Line 114: Impact

## Workflow reference

For the explicit debugging workflow, read `references/workflow.md`.
