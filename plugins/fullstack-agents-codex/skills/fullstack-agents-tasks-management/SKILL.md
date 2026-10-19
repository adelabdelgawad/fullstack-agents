---
name: fullstack-agents-tasks-management
description: "Python scheduled and periodic jobs — APScheduler with Celery execution, job endpoints, execution tracking and distributed locking."
---

## Codex runtime binding

Follow the bundle's `AGENTS.md` and `fullstack-agents-task-flow`: Codex leads,
Claude audits bounded diffs through `scripts/handoff.py`. Read only relevant
skill sections once. Existing user authorization wins over historical approval
steps. Native Codex roles replace Claude tools/dispatchers/hooks below. Bundle
paths resolve from the bundle; skill paths resolve beside `SKILL.md`. Validate
explicitly; do not assume historical hooks or dashboards are running.

# Scheduled task management

Detect existing scheduler, task model and registration conventions. Reuse the
APScheduler integration and match persistence/schedule/execution behavior.
Read Key Patterns before edits; load only relevant scheduler, task-definition
or API examples. Preserve project timezone, concurrency, retry and shutdown
rules. Celery worker tasks use `celery`; keep Python and Rust lanes separate.

## Detailed guide

Complete rules/examples: [references/skill-guide.md](references/skill-guide.md).
Read shared requirements and relevant sections before acting. Use bounded reads
(200 lines by default, project limits win); do not load every example or reread
sections still in context. Prose/code paths resolve beside this `SKILL.md`;
Markdown links are relocated.

- Line 5: When to Use This Skill
- Line 14: Architecture Overview
- Line 54: Directory Structure
- Line 79: Core Components
- Line 343: Key Patterns
- Line 363: References
