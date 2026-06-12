# Fullstack Agents

A Claude Code plugin that brings intelligent, pattern-aware code generation to polyglot fullstack projects — **Python (FastAPI) and Rust (Axum) microservices behind one Next.js frontend**. Instead of static templates, it reads your codebase, asks the right questions, and generates code that fits—first time. And instead of trusting the model to follow the rules, it enforces them with hooks.

## Installation

```bash
/plugin marketplace add https://github.com/adelabdelgawad/fullstack-agents
/plugin install fullstack-agents
```

## What You Get

- **29 specialized agents** across generation, review, analysis, scaffolding, debug, and optimization
- **8 slash commands** for common workflows (`/generate`, `/review`, `/analyze`, `/scaffold`, `/debug`, `/optimize`, `/validate`, `/status`)
- **25 skill domains** covering FastAPI, Rust/Axum, Next.js, clean architecture + DDD in both backend languages, TanStack Table, Celery, Docker, WebSocket, debugging discipline, and more
- **Hard enforcement hooks** — the routing gate is re-armed on every prompt, code-file edits are blocked until the right skills were consulted, and every change is validated with real tooling (ruff, rustfmt, clippy, tsc) before the session can end
- **Language-lane separation** — Rust and Python skills never cross; lane detection routes per file/service, and idiom transplants are forbidden
- **Wire-contract parity** — Rust and FastAPI services speak the same dialect (camelCase JSON, limit/skip pagination, shared auth), interchangeable behind the same frontend
- **Project constitutions** (spec-kit compatible) — versioned, per-project principles files that scanning loads, gates check, and whose machine-readable limits override hook thresholds
- **Senior-engineer discipline** — search-before-implement, duplication prevention, and complexity limits enforced on all implementation work
- **Multi-agent orchestration** — `/generate fullstack order` coordinates backend, API routes, and frontend in one shot

## Quick Start

```bash
/status                          # Detect your stack and available actions
/generate entity product         # Generate entity with full CRUD (FastAPI or Rust — lane auto-detected)
/generate data-table products    # Generate Next.js management table
/generate fullstack order        # Generate complete fullstack feature
/review patterns src/            # Validate code follows your architecture
/analyze codebase                # Get a full project health overview
```

## How It Works

Agents follow a structured lifecycle: they detect your project type and existing patterns (including your constitution, if present), ask clarifying questions, show a plan for approval, then generate. Every output is grounded in your actual codebase—not assumptions.

```
/generate entity product

> Analyzing codebase...
> Detected: bilingual fields (name_en/name_ar), soft delete (is_active), audit fields
>
> What relationships should this entity have?
```

After generation, the chain `REVIEW PATTERNS → FIX → VALIDATE` runs automatically — and the hooks make it non-optional: edits to `.py`/`.rs`/`.ts` files are blocked until the codebase scan and a lane-relevant skill have actually been invoked, and the session cannot end while session-modified files fail ruff, clippy, tsc, or the file-size limit.

## Supported Stack

| Layer | Technologies |
|-------|-------------|
| Backend (Python) | FastAPI, SQLAlchemy 2.0, Pydantic, Celery, APScheduler |
| Backend (Rust) | Axum 0.8, SQLx, Tokio, thiserror, Argon2/JWT |
| Frontend | Next.js 15+, React 19, TanStack Table, SWR, Tailwind |
| Infrastructure | Docker, Docker Compose, PostgreSQL, Redis, Nginx |

## Skill Domains

**Python lane**
- **FastAPI** — the simplified pattern: model, schema, CRUD helpers, router
- **Python Clean Architecture** — DDD for new microservices: pure domain, ports as Protocols, use-case-owned transactions, four-stage errors
- **Celery** — background task patterns with retry and monitoring
- **Tasks Management** — APScheduler jobs with database persistence

**Rust lane**
- **Rust Clean Architecture** — workspace-per-layer (domain/application/infrastructure/shared + apps/api/worker), ports & adapters, parse-don't-validate value objects
- **Rust Axum API** — Axum 0.8 handlers, extractors, middleware, JWT auth, WebSocket
- **Rust SQLx** — compile-time-verified queries, migrations, offline cache, SQLSTATE mapping
- **Rust Correctness** — ownership, lifetimes, async Send/Sync hazards, panic-vs-Result
- **Rust Testing** — layer-mapped pyramid with fakes, `#[sqlx::test]`, tower oneshot
- **Rust Quality Gates** — fmt/clippy-deny/audit/no-allow verification chain
- **Rust ↔ Next.js Contract** — wire parity with FastAPI so backends are interchangeable

**Frontend lane**
- **Next.js** — pages, server components, server actions, SSR strategy
- **Data Table** — TanStack Table with filtering, sorting, bulk actions, CRUD
- **Fetch Architecture** — client/server fetch utilities and API-route-only pattern

**Cross-cutting**
- **Senior Engineer** — architecture, modularity, and duplication prevention on all work
- **Constitution** — per-project normative principles (spec-kit compatible)
- **Codebase Scanning** — constitution + style profile detection before generation
- **Docker** — service configuration and infrastructure composition
- **WebSocket** — connection manager, rooms, and message protocol patterns
- **Batch Error Resolution** — fix all errors first, verify once
- **Debug** — root-cause-first discipline: reproduce → investigate → fix → verify

## Enforcement (not just guidance)

| Hook | When | What it enforces |
|------|------|------------------|
| `session-start` | Session start | Detects your stack + constitution, injects the routing doctrine |
| `prompt-scan` | Every prompt | Re-arms the 5-step gate with lane + intent classification |
| `pre-edit-gate` | Before code edits | Blocks until codebase-scanning + a lane-relevant skill were invoked |
| `post-edit-validate` | After code edits | ruff on Python, rustfmt on Rust |
| `stop-validate` | Session end | ruff / cargo fmt+clippy / tsc on session-modified files, file-size limits (constitution-overridable) |

## Philosophy

> **Compounding Engineering**: each unit of work should make the next unit easier.

This plugin embodies that by detecting your patterns, building on existing work instead of replacing it, enforcing the rules with the harness rather than hoping the model remembers them, and suggesting what to do next after every generation.

## Links

- [Agents Reference](docs/agents.md)
- [Commands Reference](docs/commands.md)
- [Skills Reference](docs/skills.md)
- [Getting Started](docs/getting-started.md)
- **Author**: [Adel Abdelgawad](https://github.com/adelabdelgawad)

## License

MIT
