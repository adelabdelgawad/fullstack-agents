---
name: data-table
description: Next.js data-table and list pages — SSR first load, columns, cell links, filters, facets, CRUD tables and list endpoints; create, change, review or diagnose. Other pages use nextjs.
---

# Data tables

Reuse the project's table library and shared controls. Server-render rows and
total first; costly counts get a separate request, large options use server
search, paged sorts have a unique tie-breaker. Preserve permission/filter parity
and the wire contract. Default to simple state unless data changes independently.
Use server records for mutations and honor current sort/filter/page rules;
never infer global counts from visible rows. One coordinator owns refresh.
Required: [list-loading](references/list-loading.md),
[data-freshness](../nextjs/references/data-freshness.md) and relevant
[client-performance](../nextjs/references/client-performance.md) rules.
For forms also read [sheet rules](references/edit-sheet-pattern.md); an edit sheet has one
commit point, its footer Save/Cancel: no section saves on its own.

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
