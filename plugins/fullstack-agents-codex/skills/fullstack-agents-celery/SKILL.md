---
name: fullstack-agents-celery
description: "Production-ready Celery worker configuration for distributed background task processing — task queues, routing, retry strategies, and worker performance tuning. Use when configuring Celery workers, creating background or async tasks, or debugging Celery issues. Do not use for cron-style scheduled jobs (use tasks-management for APScheduler scheduling)."
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
- Line 14: Architecture Overview
- Line 43: Celery App Configuration
- Line 95: Task Definition Pattern
- Line 113: Worker Commands
- Line 129: Queue Routing
- Line 145: Key Patterns
