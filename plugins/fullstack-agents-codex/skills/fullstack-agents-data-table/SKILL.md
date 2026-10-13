---
name: fullstack-agents-data-table
description: "Create Next.js data table pages with SSR initial load, simplified state management, and server-response-based UI updates. Use when asked to create, change, review or diagnose a data table page, entity management page, CRUD table, admin list view, table columns or cell links. Generates page.tsx (SSR), table components, columns, context, actions, and API routes following a proven architecture with centralized reusable data-table component. Do not use for non-table pages (use nextjs) or backend code (use fastapi)."
---

## Codex runtime binding

Follow the bundle's `AGENTS.md` and `fullstack-agents-task-flow`: Codex leads,
Claude audits bounded diffs through `scripts/handoff.py`. Read only relevant
skill sections once. Existing user authorization wins over historical approval
steps. Native Codex roles replace Claude tools/dispatchers/hooks below. Bundle
paths resolve from the bundle; skill paths resolve beside `SKILL.md`. Validate
explicitly; do not assume historical hooks or dashboards are running.

# Data tables

Reuse the project's table library and shared controls. Server-render rows and
total first; costly counts get a separate request, large options use server
search, paged sorts have a unique tie-breaker. Preserve permission/filter parity
and the wire contract. Default to simple state unless data changes independently.
Use server records for mutations and honor current sort/filter/page rules;
never infer global counts from visible rows. One coordinator owns refresh.
Required: [list-loading](references/list-loading.md),
[data-freshness](../fullstack-agents-nextjs/references/data-freshness.md) and relevant
[client-performance](../fullstack-agents-nextjs/references/client-performance.md) rules.
For forms also read [sheet rules](references/edit-sheet-pattern.md).

## Detailed guide

Complete rules/examples: [references/skill-guide.md](references/skill-guide.md).
Read shared requirements and relevant sections before acting. Use bounded reads
(200 lines by default, project limits win); do not load every example or reread
sections still in context. Prose/code paths resolve beside this `SKILL.md`;
Markdown links are relocated.

- Line 11: Reusable Data-Table Component Library
- Line 225: Data Fetching Strategy
- Line 252: Architecture Overview
- Line 277: Quick Start
- Line 283: File Generation Order
- Line 354: Core Principles
- Line 433: Reference Implementations
- Line 438: Required Dependencies
- Line 445: Checklist
- Line 462: References
