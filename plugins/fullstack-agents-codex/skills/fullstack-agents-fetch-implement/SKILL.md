---
name: fullstack-agents-fetch-implement
description: "Scaffold fetch boilerplate for a new entity — generates server actions, API routes, and client call patterns following the correct architecture."
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

- Line 5: Usage
- Line 18: Prerequisites
- Line 27: Template: Server Actions
- Line 80: Template: API Route — Collection
- Line 104: Template: API Route — Resource
- Line 140: Template: API Route — Status Toggle
- Line 162: Template: API Route — Bulk Status
- Line 179: After Scaffolding
- Line 190: Automated Script
