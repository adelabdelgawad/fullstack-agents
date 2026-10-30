---
name: fullstack-agents-nextjs
description: "Next.js pages, layouts, router, Link prefetch, server actions, data refresh after mutations or live events, and slow navigation, skeletons or frozen pages."
---

## Codex runtime binding

Follow the bundle's `AGENTS.md` and `fullstack-agents-task-flow`: Codex leads,
Claude audits bounded diffs through `scripts/handoff.py`. Read only relevant
skill sections once. Existing user authorization wins over historical approval
steps. Native Codex roles replace Claude tools/dispatchers/hooks below. Bundle
paths resolve from the bundle; skill paths resolve beside `SKILL.md`. Validate
explicitly; do not assume historical hooks or dashboards are running.

# Next.js

Use detected project layout and shared components. Server pages seed primary
content; server actions call the backend directly. Client mutations use the
server's returned record; never invent page-slice counts or blindly insert into
sorted/paged lists. Default to simple state; use SWR/streams only when needed.
One coordinator owns refresh. Debounce free-text search, not every control.
Required: relevant [data-freshness](references/data-freshness.md) and
[client-performance](references/client-performance.md) rules; for streams also
[live-updates](references/live-updates.md). For list pages load `data-table`. A new or redesigned
page follows [page-composition](references/page-composition.md).

## Detailed guide

Complete rules/examples: [references/skill-guide.md](references/skill-guide.md).
Read shared requirements and relevant sections before acting. Use bounded reads
(200 lines by default, project limits win); do not load every example or reread
sections still in context. Prose/code paths resolve beside this `SKILL.md`;
Markdown links are relocated.

- Line 5: When to Use This Skill
- Line 13: Architecture Overview
- Line 46: File Structure
- Line 89: Core Principles
- Line 289: Generation Order
- Line 300: Quick Reference
- Line 325: References
