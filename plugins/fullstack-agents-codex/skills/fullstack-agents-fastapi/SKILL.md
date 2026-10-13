---
name: fullstack-agents-fastapi
description: "Generate production-ready FastAPI CRUD modules — SQLAlchemy model, Pydantic schemas, CRUD helpers, and routers following the simplified architecture. Use when creating or extending backend entities, models, or REST endpoints with SQLAlchemy and Pydantic. Do not use for Next.js frontend code (use nextjs or data-table)."
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
- Line 13: Architecture Overview
- Line 61: File Structure
- Line 90: Core Principles
- Line 144: Generation Order
- Line 154: Quick Reference
- Line 178: References
