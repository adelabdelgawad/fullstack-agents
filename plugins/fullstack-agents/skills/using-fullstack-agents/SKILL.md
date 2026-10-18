---
name: using-fullstack-agents
description: Routing guide — which fullstack-agents skill to invoke before writing FastAPI, Rust or Next.js code.
---

# Using Fullstack Agents

Invoke `task-flow` before a source edit, delegation or wide scan; load the lane
skill before a root cause, plan or brief too. The prompt-scan routing line is an
instruction: name an irrelevant skill skipped and why. Project manuals and the
constitution win over defaults. Use the Skill tool; load once while in context.
Refine intent/scope/success criteria internally with `prompt-polish`; clear
requests pass through unchanged. Give workers the refined bounded task.

Claude remains the lead. It owns investigation, planning, audit and conclusion;
workers supply labour and evidence. Preserve configured implementer defaults.

## Gate and routing

DETECT → MATCH → REUSE → INVOKE → SCAN. Search before writing. Invoke
`codebase-scanning` before first generation and reuse its profile;
`senior-engineer` governs implementation. Generate → review patterns → fix →
language-matched validation → next steps. Route per service/file, never blend
Python/Rust idioms. Resolve an unspecified new service's language first.

| Work | Skills |
|---|---|
| Existing FastAPI / new Python DDD | fastapi / python-clean-architecture |
| Rust layout / Axum / SQLx | rust-clean-architecture / rust-axum-api / rust-sqlx |
| Rust correctness / tests / gates | rust-correctness / rust-testing / rust-quality-gates |
| Rust endpoint consumed by Next.js | rust-nextjs-contract plus generating skill |
| Next.js page / list page | nextjs / data-table |
| Fetch layers | fetch-architecture; fetch-plan/implement/validate as needed |
| Python WebSocket / background / scheduled | websocket / celery / tasks-management |
| Infrastructure | docker |
| Bug / multiple check failures | debug / batch-error-resolution plus lane skill |
| Ports / principles / costly trade-off | frontend-transformation, backend-migration-from-frontend / constitution / fusion-panel |
| Shared operations | team-coordination |

Command/agent mappings and unusual intents: read Routing Table in the guide.

## Token discipline

- Invoke each skill once while in context, never again just for a reminder.
- Read mandatory requirements and only relevant examples/guide sections.
- Cache one scan/profile per service; re-scan only changed assumptions.
- Search first, use bounded ranges, batch independent tools.
- Keep briefs short; pass known sites/ranges and example paths to workers.
- Fix multiple errors in one batch; validate affected surfaces once.
- Keep complete logs on disk; return result/failure lines and precise evidence.
- Delegate only when narrowed work remains too wide; honor concurrency rules.

Never cut lane rules, necessary dialogue, project confirmation rules, pattern
review, validation or required tests. Herdr workers require the user's request.

## Detailed guide

Complete rules/examples: [references/skill-guide.md](references/skill-guide.md).
Read shared requirements and relevant sections before acting. Use bounded reads
(200 lines by default, project limits win); do not load every example or reread
sections still in context. Prose/code paths resolve beside this `SKILL.md`;
Markdown links are relocated.

- Line 11: The Rule
- Line 15: You Are the Session Lead (always on)
- Line 28: Language Separation — Python vs Rust (HARD RULE)
- Line 68: Routing Table
- Line 118: Hard Gate — 5-Step Check Before ANY Code Generation
- Line 157: Senior Engineer Standard (always on)
- Line 177: Working Method (always on)
- Line 199: Rationalization Prevention
- Line 223: Automatic Chaining Rules
- Line 251: Codebase Scanning Mandate
- Line 259: Skill Priority
- Line 268: Token Discipline (efficiency without quality loss)
- Line 290: How to Access Skills
- Line 294: Skill Types

## Task progress

For multi-step work, follow `task-flow` task tracking: a dedicated repository Markdown file,
session registration and status updates reflected in the dashboard Tasks section. Workflow
phase reporting is separate from task completion.
