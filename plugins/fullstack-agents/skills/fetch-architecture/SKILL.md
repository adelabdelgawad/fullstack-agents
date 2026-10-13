---
name: fetch-architecture
description: Client and server-side fetch utilities for Next.js — direct backend calls from server code and API route proxying with auth refresh for client code. Use when setting up fetch utilities, configuring client-side API calls, or implementing server-side data fetching. Do not use to scaffold per-entity fetch code (use fetch-plan then fetch-implement).
---

# Fetch architecture

Server actions/SSR call the backend directly; browser calls use `api` through
Next.js API routes. API-route mutations use `backendFetch` from `backend.ts`
with `(token, forwardHeaders)`, preserving CSRF/auth headers and token refresh.
Do not add a server-action → API-route → backend hop or replace shared `api`
with ad hoc helpers. Reuse detected utilities and match backend wire contracts.
Per-entity scaffolding uses `fetch-plan` then `fetch-implement`; compliance uses
`fetch-validate`. Read applicable anti-patterns before examples.

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
