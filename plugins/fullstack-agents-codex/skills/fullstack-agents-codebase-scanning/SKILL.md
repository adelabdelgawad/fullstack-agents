---
name: fullstack-agents-codebase-scanning
description: "Detect the project's patterns and coding style before generating code. Mandatory before the first generation in a session."
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

- Line 5: When to Use
- Line 19: Phase 0: Constitution Load (~2 seconds)
- Line 39: Phase 1: Structure Detection (~5 seconds)
- Line 64: Phase 2: Pattern Extraction (~10 seconds)
- Line 104: Phase 3: Style Profile Construction
- Line 133: Priority Rule
- Line 146: Output
