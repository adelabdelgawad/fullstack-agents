---
name: fullstack-agents-using-fullstack-agents
description: Bootstrap the standalone Codex-led Fullstack Agents workflow for Python/FastAPI, Rust/Axum and Next.js projects, using Claude only for bounded audits.
---

# Using Fullstack Agents in Codex

Read the bundle's `AGENTS.md` and `fullstack-agents-task-flow` at intake. Codex
leads; Claude returns read-only audit issues and scope. Read skills with the
available tools, once per context. Use the project constitution and detected
patterns before defaults. Follow existing authorization without extra approval
steps. Do not assume Claude hooks or tools are active.

| Work | Skills (prefix every name with `fullstack-agents-`) |
|---|---|
| Source generation/refactoring | codebase-scanning, senior-engineer, lane skills |
| Existing FastAPI CRUD | fastapi |
| New Python DDD service | python-clean-architecture |
| Rust structure/entity | rust-clean-architecture |
| Axum HTTP | rust-axum-api |
| SQLx/persistence/migrations | rust-sqlx |
| Rust correctness/tests/gates | rust-correctness, rust-testing, rust-quality-gates |
| Rust consumed by Next.js | rust-nextjs-contract, plus the generating skill |
| Next.js page/rendering | nextjs |
| Management/data table page | data-table, nextjs |
| Fetch/server action/API proxy | fetch-architecture; fetch-plan/implement/validate as needed |
| Background/scheduled work | celery / tasks-management |
| Python WebSocket | websocket |
| Browser live updates | nextjs, skills/fullstack-agents-nextjs/references/live-updates.md |
| Infrastructure | docker |
| Bugs/latency | debug, applicable lane skill |
| Multiple check failures | batch-error-resolution |
| Frontend/backend port | frontend-transformation / backend-migration-from-frontend |
| Project principles | constitution |
| High-stakes decision | fusion-panel |
| Shared operational surface | team-coordination |
| Work spanning two hosts of one repository | cross-host-coordination |

Route by the file/service: Cargo.toml and `.rs` mean Rust; pyproject.toml,
requirements.txt and `.py` mean Python; Next.js package.json and `.tsx` mean
frontend. Never blend Python and Rust idioms. Ask for the language of a new
service only if it is unspecified and changes the outcome.

Workflow skills: `$fullstack-agents-generate`, `$fullstack-agents-review`,
`$fullstack-agents-analyze`, `$fullstack-agents-scaffold`,
`$fullstack-agents-debug` (also the debugging discipline),
`$fullstack-agents-optimize`, `$fullstack-agents-validate`,
`$fullstack-agents-status`. Their command references and native agent roles
retain the existing engineering patterns, with Codex runtime bindings.

Generate → pattern review → fix → validation → Claude audit → scoped repair.
Use targeted checks and retain full logs on disk. Report missing tooling.
