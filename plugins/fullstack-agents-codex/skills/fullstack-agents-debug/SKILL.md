---
name: fullstack-agents-debug
description: "Use when encountering any bug, error, unexpected behavior, slow page, long loading skeleton or latency complaint in a fullstack project — enforces root-cause-first debugging discipline before any fix attempts"
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
- Line 89: Common Rationalizations
- Line 101: Quick Reference
- Line 110: Impact

## Workflow reference

For the explicit debugging workflow, read `references/workflow.md`.
