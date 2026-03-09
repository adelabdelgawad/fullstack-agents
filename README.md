# Fullstack Agents

A Claude Code plugin that brings intelligent, pattern-aware code generation to fullstack projects. Instead of static templates, it reads your codebase, asks the right questions, and generates code that fits—first time.

## Installation

```bash
/plugin marketplace add https://github.com/adelabdelgawad/fullstack-agents
/plugin install fullstack-agents
```

## What You Get

- **28 specialized agents** across generation, review, analysis, scaffolding, debug, and optimization
- **8 slash commands** for common workflows (`/generate`, `/review`, `/analyze`, `/scaffold`, `/debug`, `/optimize`, `/validate`, `/status`)
- **9 skill domains** covering FastAPI, Next.js, TanStack Table, Celery, Docker, WebSocket, and more
- **Multi-agent orchestration** — `/generate fullstack order` coordinates backend, API routes, and frontend in one shot
- **Pattern detection** — agents read your existing code before generating anything

## Quick Start

```bash
/status                          # Detect your stack and available actions
/generate entity product         # Generate FastAPI entity with full CRUD
/generate data-table products    # Generate Next.js management table
/generate fullstack order        # Generate complete fullstack feature
/review patterns src/            # Validate code follows your architecture
/analyze codebase                # Get a full project health overview
```

## How It Works

Agents follow a structured lifecycle: they detect your project type and existing patterns, ask clarifying questions, show a plan for approval, then generate. Every output is grounded in your actual codebase—not assumptions.

```
/generate entity product

> Analyzing codebase...
> Detected: bilingual fields (name_en/name_ar), soft delete (is_active), audit fields
>
> What relationships should this entity have?
```

## Supported Stack

| Layer | Technologies |
|-------|-------------|
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic, Celery, APScheduler |
| Frontend | Next.js 15+, React 19, TanStack Table, SWR, Tailwind |
| Infrastructure | Docker, Docker Compose, PostgreSQL, Redis, Nginx |

## Skill Domains

- **FastAPI** — model, schema, repository, service, router patterns
- **Next.js** — pages, server components, server actions, SSR+SWR strategy
- **Data Table** — TanStack Table with filtering, sorting, bulk actions, CRUD
- **Fetch Architecture** — client/server fetch utilities and API-route-only pattern
- **Celery** — background task patterns with retry and monitoring
- **Tasks Management** — APScheduler jobs with database persistence
- **Docker** — service configuration and infrastructure composition
- **WebSocket** — connection manager, rooms, and message protocol patterns
- **Batch Error Resolution** — disciplined collect → analyze → resolve → verify workflow

## Philosophy

> **Compounding Engineering**: each unit of work should make the next unit easier.

This plugin embodies that by detecting your patterns, building on existing work instead of replacing it, and suggesting what to do next after every generation.

## Links

- [Agents Reference](docs/agents.md)
- [Commands Reference](docs/commands.md)
- [Skills Reference](docs/skills.md)
- [Getting Started](docs/getting-started.md)
- **Author**: [Adel Abdelgawad](https://github.com/adelabdelgawad)

## License

MIT
