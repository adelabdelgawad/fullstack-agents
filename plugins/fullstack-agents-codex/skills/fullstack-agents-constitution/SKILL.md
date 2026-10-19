---
name: fullstack-agents-constitution
description: "Create, update or check a project constitution — the versioned principles file (layers, language lanes, wire contract, quality limits) that gates check against."
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

- Line 7: Location (search order)
- Line 15: Precedence
- Line 28: Template
- Line 39: Architecture
- Line 47: Language Lanes
- Line 53: Wire Contract
- Line 60: Quality
- Line 67: Non-Negotiables
- Line 75: History
- Line 80: Maintaining
