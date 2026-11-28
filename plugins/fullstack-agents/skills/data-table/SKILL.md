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

## Page contract (always applies)

Every list or CRUD page follows this contract unless the user states otherwise. A page,
sheet or table that breaks one rule is not done. Copy the applicable bullets into briefs.

**List page**
- The server page renders the first rows, total and facet counts (SSR); the client makes no
  request for primary content after hydration.
- One controller toolbar above the table: search on the left; on the right the filter toggle
  (with active-filter count and clear-all), column toggle, refresh, then the primary Create
  button (privilege-gated). Bulk actions appear in the toolbar only while rows are selected.
- Filters beyond search live in the collapsible filter pane opened by the toggle, side by side;
  URL params hold search, filters, sort and page.
- Build from the project's shared table, toolbar, filter, pagination and sheet components; never
  a hand-rolled table or native `<select>`. Narrow screens render each row as a card.
- Empty, loading and error states are explicit; an error offers Retry.

**Row actions**
- View (eye icon) first: opens the read-only View sheet. Edit (pencil icon), shown only with the
  edit privilege, opens the Edit sheet prefilled. Secondary actions (enable/disable, duplicate,
  delete with confirmation) follow, in a menu when there are more than two.
- Fetch-then-open: the row action loads the complete record by id (row data is partial) with a
  spinner on the button, then opens the sheet ready. A failed load shows the error with Retry and
  does not open an empty sheet.

**View sheet (read-only)**
- Shows every stored field and every child item of the record (its attributes, lines, members,
  rules) with their values, as text in titled groups, the field the user opened it for first.
- No inputs, no Add, no Save; the footer holds Close and, with the privilege, an Edit button that
  switches to the Edit sheet.
- A field without a value says so in words ("Not set"), never a bare dash.

**Edit and Create sheets (one form)**
- Create and Edit render the same form component: the parent fields plus the full list of child
  items as editable rows, each with its value and a remove control, and an inline Add control
  that appends a new row. Create starts empty (defaults filled); Edit starts with every stored
  non-secret value prefilled. Secrets are write-only with a "saved, leave blank to keep" hint.
- Exactly one commit point: the footer Save/Cancel. No section, child row or nested sheet saves on
  its own or calls a write API on add, remove or toggle; all of it is a draft until Save.
- Closing with unsaved changes (X, Escape, overlay, Cancel) asks for confirmation.
- Save validates first and shows field errors inline. On success the sheet closes and the list
  updates that row from the record the server returned (insert on create per current sort/filter);
  never an optimistic merge. On failure the sheet stays open with the error.

**Wording**
- Titles, labels, buttons and messages use the user's domain words for the entity and its parts,
  never internal model, table or type names; every string comes from the locale files.

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
