---
name: fullstack-agents-scaffold
description: "Scaffold new projects or modules"
---

## Codex runtime binding

Follow the bundle's `AGENTS.md` and `fullstack-agents-task-flow`: Codex leads,
Claude audits bounded diffs through `scripts/handoff.py`. Read only relevant
skill sections once. Existing user authorization wins over historical approval
steps. Native Codex roles replace Claude tools/dispatchers/hooks below. Bundle
paths resolve from the bundle; skill paths resolve beside `SKILL.md`. Validate
explicitly; do not assume historical hooks or dashboards are running.

## Workflow

Read `references/workflow.md` for this workflow. Use bounded sections and only the relevant target role. The Codex lead owns planning, verification and the Claude audit handoff.
