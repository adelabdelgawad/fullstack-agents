# Fullstack Agents

Unified fullstack development plugin with **29 specialized AI agents** and **29 skill domains** for intelligent code generation, review, analysis, scaffolding, debugging, and optimization across **Python (FastAPI) and Rust (Axum) microservices** behind one Next.js frontend. **Auto-triggers** on FastAPI/Rust/Next.js projects via SessionStart hook, with **enforced validation gates** via a PostToolUse hook and **strict language-lane separation** between Python and Rust skills.

## Features

- **Auto-Triggering** - SessionStart hook detects FastAPI/Next.js projects and injects routing context. Claude automatically invokes the right skill before writing any backend or frontend code — no manual commands needed.
- **Smart Code Generation** - Not static templates. Agents analyze existing code, ask clarifying questions, and generate context-aware code that matches your patterns.
- **Codebase Scanning** - Before first generation, scans your project to build a style profile (session patterns, schema bases, naming conventions, etc.) ensuring generated code matches exactly.
- **Interactive Dialogue** - Agents detect your codebase patterns, ask about relationships and edge cases, confirm before generating, and suggest next steps.
- **Mandatory Post-Generation Review** - After every generation, pattern compliance review + type check + lint runs automatically. No manual step needed.
- **Enforced Validation Gates** - Not just prompts: a PostToolUse hook runs `ruff` on every edited Python file (violations are fed back and must be fixed) and auto-formats edited Rust files with `rustfmt`. Whole-project `clippy`/`tsc` stay your call before shipping.
- **Senior Engineer Discipline** - The `senior-engineer` skill enforces search-before-implement, duplication prevention, SOLID layer boundaries, and complexity limits on ALL implementation work — wired into the hard gate (step 3: REUSE) and the agent lifecycle (Phase 3 reuse search).
- **Rust Microservices (Clean Architecture + DDD)** - Seven Rust skills (`rust-clean-architecture`, `rust-axum-api`, `rust-sqlx`, `rust-correctness`, `rust-testing`, `rust-quality-gates`, `rust-nextjs-contract`) codify a workspace-per-layer architecture (domain/application/infrastructure/shared + apps/api/worker), Axum 0.8 + SQLx patterns, and exact wire-contract parity with FastAPI so Rust and Python services are interchangeable behind the same Next.js frontend. No Leptos — Rust serves JSON only.
- **Python Clean Architecture + DDD** - `python-clean-architecture` mirrors the same layer rules for new FastAPI microservices (ports as Protocols, use-case-owned transactions, four-stage error model), while the existing `fastapi` skill keeps serving simplified-pattern services.
- **Language-Lane Separation** - Rust and Python skills never cross: lane detection (Cargo.toml vs pyproject.toml) routes per file/service, hooks validate per language (ruff vs rustfmt/clippy), and idiom transplants are explicitly forbidden.
- **Project Constitution (spec-kit compatible)** - The `constitution` skill creates a versioned, per-project principles file (searched at `.specify/memory/constitution.md`, repo root, or `.claude/`). Codebase-scanning loads it with precedence constitution > codebase patterns > skill defaults; every hook surfaces it. Closes the enforcement gap spec-kit leaves open: spec-kit plans, these hooks police.
- **Multi-Agent Orchestration** - Chain agents together for fullstack feature generation (backend + frontend + docker).
- **Pattern Detection** - Automatically detects your coding style, naming conventions, and architectural patterns.

## Supported Technologies

| Category | Technologies |
|----------|-------------|
| Backend (Python) | FastAPI, SQLAlchemy 2.0, Pydantic, Celery, APScheduler |
| Backend (Rust) | Axum 0.8, SQLx, Tokio, thiserror, Argon2/JWT |
| Frontend | Next.js 15+, React, TanStack Table, SWR |
| Infrastructure | Docker, Docker Compose, Nginx, PostgreSQL, Redis |

## Agent Categories

### Review (4 agents)
- `code-quality` - Code quality review
- `security` - Security audit
- `performance` - Performance review
- `patterns-compliance` - Architecture pattern validation

### Generate (7 agents)
- `fastapi-entity` - FastAPI CRUD entity generation
- `nextjs-page` - Next.js page generation
- `nextjs-data-table` - Data table page generation
- `api-route` - Next.js API route generation
- `celery-task` - Celery task generation
- `scheduled-job` - APScheduler job generation
- `docker-service` - Docker service generation

### Analyze (4 agents)
- `codebase` - Full codebase analysis
- `architecture` - Architecture review
- `dependencies` - Dependency analysis
- `patterns` - Pattern detection

### Scaffold (5 agents)
- `project-fastapi` - FastAPI project scaffolding
- `project-nextjs` - Next.js project scaffolding
- `module-backend` - Backend module scaffolding
- `module-frontend` - Frontend module scaffolding
- `docker-infrastructure` - Docker infrastructure scaffolding

### Debug (4 agents)
- `error-diagnosis` - Error analysis
- `log-analysis` - Log pattern analysis
- `performance-profiling` - Performance bottleneck detection
- `api-debugging` - API request/response debugging

### Optimize (4 agents)
- `performance` - Performance optimization
- `code-cleanup` - Dead code removal
- `refactoring` - Code refactoring
- `query-optimization` - Database query optimization

## Commands

| Command | Description |
|---------|-------------|
| `/analyze [target]` | Analyze codebase, architecture, dependencies, or patterns |
| `/generate [type] [name]` | Generate entities, pages, components with dialogue |
| `/scaffold [type]` | Scaffold new projects or modules |
| `/review [type] [target]` | Review code quality, security, performance, patterns |
| `/debug [type]` | Debug errors, analyze logs, profile performance |
| `/optimize [type] [target]` | Optimize performance, cleanup, refactor, queries |
| `/validate [entity]` | Validate entity follows architecture patterns |
| `/status` | Show project detection status and available actions |

## Quick Start

### Generate a FastAPI Entity

```bash
/generate entity product
```

The agent will:
1. Detect your project structure and patterns
2. Ask about entity fields, relationships, and features
3. Show you a generation plan for confirmation
4. Generate model, schema, repository, service, and router
5. Suggest next steps (migrations, frontend page, tests)

### Generate Fullstack Feature

```bash
/generate fullstack order
```

Orchestrates multiple agents to create:
1. FastAPI backend (model, schema, repo, service, router)
2. Next.js API routes (proxy to backend)
3. Next.js data table page (with CRUD operations)

### Review Patterns

```bash
/review patterns product
```

Validates that your entity follows architecture patterns:
- Single-session-per-request flow
- Repository pattern compliance
- Schema inheritance
- SSR + SWR hybrid pattern

## Auto-Triggering (SessionStart Hook)

When installed, the plugin automatically:

1. **Detects** your project type on session start (FastAPI, Next.js, Docker)
2. **Injects** routing context so Claude knows which skill to invoke for each request
3. **Scans** your codebase patterns before the first code generation
4. **Reviews** generated code automatically after every generation (pattern compliance + type check + lint)

No manual `/generate entity` commands needed — just say "create a Product entity" and the plugin activates.

Manual commands (`/generate entity`, `/review patterns`, etc.) still work exactly as before for explicit invocation.

On `resume`/`compact` the hook injects only a short reminder instead of the full guide, and projects with no FastAPI/Rust/Next.js markers get a 2-line notice instead of the full doctrine — token-efficient by design, with the quality floor (dialogue, confirmation, pattern review, validation, tests) never cut. The `using-fullstack-agents` skill carries an explicit Token Discipline section (scan once, skills load once, batch error fixes, parallel tool calls, targeted reads).

## Enforced Validation Gates (PostToolUse Hook)

The generate → review → validate chain is enforced by the harness, not just by prompt instructions:

| Hook | Trigger | What it does |
|------|---------|--------------|
| `prompt-polish` | Every user prompt | Injects a directive to refine the raw request into a precise spec (intent / scope / success criteria / constraints) before acting and before delegating to worker subagents — full directive once per session, one-line reminder afterward; pure control replies (yes/continue) are skipped |
| `prompt-scan` | Every user prompt | Detects stack-related prompts (Python/Rust/Next.js keywords), classifies lane + intent, and re-arms the routing mandate — full block once per session, one-line reminder afterward (token-efficient; the pre-edit gate enforces deterministically regardless) |
| `pre-edit-gate` | Before every `Write`/`Edit` to `.py`/`.rs`/`.ts`/`.tsx` | BLOCKS the edit (in governed projects) until `codebase-scanning` AND a lane-relevant skill have actually been invoked this session — verified against the transcript, not promised. Override: `FSA_SKIP_GATE=1` |
| `post-edit-validate` | After every `Write`/`Edit` | Runs `ruff check` on edited Python files (violations block and feed back); auto-formats edited Rust files with `rustfmt` |

These hooks degrade gracefully: they act only on the file just edited, and skip silently when tooling is unavailable (`ruff` is resolved from PATH → `uv run` → `uvx`). Whole-project checks (`cargo fmt --check` + `clippy -D warnings`, `tsc --noEmit`) are left to you to run before shipping.

## Agent Lifecycle

All agents follow this lifecycle:

```
0. BOOTSTRAPPING  -> Verify codebase-scanning has run, load style profile
1. DETECTION      -> Detect project type, existing patterns, new vs existing
2. DIALOGUE       -> Ask clarifying questions based on detection
3. ANALYSIS       -> Analyze existing code to match style
4. CONFIRMATION   -> Present plan, get user approval
5. EXECUTION      -> Generate/modify code
6. NEXT STEPS     -> Suggest related actions, offer to continue
```

## Installation

Add the plugin to your Claude Code configuration:

```bash
cd your-project
claude plugin add fullstack-agents
```

## License

MIT
