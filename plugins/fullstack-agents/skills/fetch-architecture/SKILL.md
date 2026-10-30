---
name: fetch-architecture
description: Next.js fetch layer — plan, scaffold or validate an entity's server actions, API routes and client calls; backend calls, API-route proxying and auth refresh.
---

# Fetch architecture

Server actions/SSR call the backend directly; browser calls use `api` through
Next.js API routes. API-route mutations use `backendFetch` from `backend.ts`
with `(token, forwardHeaders)`, preserving CSRF/auth headers and token refresh.
Do not add a server-action → API-route → backend hop or replace shared `api`
with ad hoc helpers. Reuse detected utilities and match backend wire contracts.
Per entity: plan with [references/plan.md](references/plan.md), scaffold with
[references/implement.md](references/implement.md), audit compliance with
[references/validate.md](references/validate.md). Read applicable anti-patterns before examples.

## Detailed guide

Complete rules/examples: [references/skill-guide.md](references/skill-guide.md).
Read shared requirements and relevant sections before acting. Use bounded reads
(200 lines by default, project limits win); do not load every example or reread
sections still in context. Prose/code paths resolve beside this `SKILL.md`;
Markdown links are relocated.

- Line 5: When to Use This Skill
- Line 14: Architecture Overview
- Line 60: Anti-Patterns (NEVER DO)
- Line 82: Directory Structure
- Line 103: Core Files
- Line 578: Request Flow
- Line 598: Client-Side State Management
- Line 633: Key Patterns
