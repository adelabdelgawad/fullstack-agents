---
name: fullstack-agents-senior-engineer
description: "Senior-engineer discipline for architecture, modularity, and duplication prevention with YAGNI — search-before-implement, build only what is asked, composition over monoliths, SOLID boundaries, aggressive complexity reduction, and leave-it-cleaner refactoring. Use before writing, modifying, or refactoring ANY application code, and when asked to refactor, clean up, reduce duplication, or extract shared logic. Do not use for docs-only, config-only, or dependency-bump changes."
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
- Line 9: Required Workflow Before Any Implementation
- Line 47: Core Principles
- Line 155: Rationalization Prevention
- Line 173: Definition of Done (per change)
- Line 186: Expected Outcomes
