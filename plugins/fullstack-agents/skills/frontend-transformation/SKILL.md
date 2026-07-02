---
name: frontend-transformation
description: Migrate an existing React (or other framework) frontend to a target framework (e.g. Next.js App Router) at 1:1 fidelity — same pages, routes, layouts, components, styling, state, and interactions, with nothing redesigned or reimplemented. Use when asked to port, migrate, convert, or transform a frontend to another framework while preserving it exactly. Do not use for greenfield pages (use nextjs / data-table) or backend migrations (use backend-migration-from-frontend).
---

# Frontend Transformation

## Objective

Transform an existing frontend application into the target framework
(default: **Next.js App Router**) while preserving the application as close to
**1:1** as technically possible.

This is **NOT** a redesign, modernization, refactor, or reimplementation. It is
a **framework migration only**. Replicate exactly what already exists.

**This skill is RIGID.** The investigation phase runs before any code is
written, and the completion criteria are non-negotiable.

## When to Use This Skill

Use this skill when asked to:
- Port / migrate / convert a React app to Next.js (or another target framework)
- Move from React Router to the Next.js App Router while keeping the UI identical
- "Transform", "recreate", or "rebuild in framework X" an existing frontend
- Reproduce an existing UI 1:1 in a new stack

Do **not** use it for building new pages from scratch (use `nextjs` or
`data-table`) or for backend work (use `backend-migration-from-frontend`).

## How This Fits the Plugin

- **Language lane:** FRONTEND. The target patterns (server components, App
  Router, server actions, fetch architecture) come from the `nextjs`,
  `data-table`, and `fetch-architecture` skills — invoke those for the *target*
  idioms while this skill governs *fidelity to the source*.
- **Scan first:** run `codebase-scanning` on BOTH the source and target projects
  before generating, so the migration matches the target project's conventions.
- **Senior-engineer discipline still applies** to the code you write in the
  target — but never at the cost of changing what the UI does. Fidelity to the
  source outranks refactoring instinct here.

## Core Principle — Preserve Everything

The migrated application must be visually and functionally indistinguishable
from the original.

Do **NOT**:
- Improve the UI · simplify layouts · reorganize the design
- Replace components because they "look similar" · remove wrappers
- Modernize the code · introduce your own architecture · change UX decisions
- Change spacing · typography · colors · animations

Instead: **replicate exactly what already exists.**

## Required Investigation Phase (before any code)

Fully inspect the source project and document every one of:

- Every page · route · layout · nested layout
- Every component · dialog · drawer · modal · popover · menu
- Every table · form · chart · dashboard widget
- Every loading state · skeleton · empty state · error state
- Every responsive breakpoint · animation · transition
- Every CSS source · Tailwind class · global style · font
- Every asset · icon · image · localization file

**Do not start implementation until the application structure is fully
understood.** Produce a written inventory first.

## Component Preservation

Component hierarchy must remain identical whenever possible.

Do NOT flatten, merge, split, or rewrite component structure because it is
"cleaner." If React contains:

```
A
 └── B
      └── C
```

the migrated version must preserve the same hierarchy.

## Styling Preservation

Copy styling **exactly**. Never recreate styles from memory; never approximate.

Preserve: Tailwind classes · CSS Modules · SCSS · CSS variables · fonts ·
shadows · borders · radius · colors · opacity · gradients · spacing · responsive
behavior · hover / focus / disabled / active states.

## UI Library

If both projects use the same UI library (e.g. shadcn/ui), reuse equivalent
components whenever possible. Do not replace `Card`, `Button`, `Dialog`,
`Popover`, `Table`, `Badge`, etc. with custom implementations unless absolutely
necessary.

## What Actually Gets Migrated

Only framework-specific concerns change:

- **Routing** — React Router → Next.js App Router. Preserve route hierarchy,
  nested layouts, route names, dynamic routes, query parameters, and navigation
  behavior.
- **State management** — preserve existing behavior. Do not migrate to another
  state library unless explicitly requested.
- **Forms** — preserve validation, error messages, submission flow, disabled
  logic, and loading indicators.
- **API calls** — do NOT redesign API communication. Preserve request timing,
  parameters, payloads, error handling, and retry behavior. Adapt only the
  framework-specific code (e.g. move fetches into server components / route
  handlers per `fetch-architecture`).

## Missing Code Policy

Never invent missing components. Never create placeholders. Never silently
remove features.

If something cannot be migrated: **STOP and explain exactly why.**

## Completion Criteria

The task is NOT complete until every one of these exists and matches:

✓ Every page · route · component · interaction · animation
✓ Every responsive behavior · dialog · menu · table
✓ Every loading state · empty state · error state
✓ Every visual detail

## Final Verification

Perform a complete comparison between the original and migrated applications.
Identify every difference:

- Missing pages · components · dialogs · routes · assets · CSS · icons
- Layout · spacing · typography · responsive · animation · interaction differences

**Do not finish until every discrepancy is resolved or explicitly documented.**
