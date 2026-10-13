---
name: fullstack-agents-frontend-transformation
description: "Migrate an existing React (or other framework) frontend to a target framework (e.g. Next.js App Router) at 1:1 fidelity — same pages, routes, layouts, components, styling, state, and interactions, with nothing redesigned or reimplemented. Use when asked to port, migrate, convert, or transform a frontend to another framework while preserving it exactly. Do not use for greenfield pages (use nextjs / data-table) or backend migrations (use backend-migration-from-frontend)."
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
- Line 15: When to Use This Skill
- Line 26: How This Fits the Plugin
- Line 38: Core Principle — Preserve Everything
- Line 51: Required Investigation Phase (before any code)
- Line 66: Component Preservation
- Line 81: Styling Preservation
- Line 89: UI Library
- Line 96: What Actually Gets Migrated
- Line 112: Missing Code Policy
- Line 119: Completion Criteria
- Line 128: Final Verification
