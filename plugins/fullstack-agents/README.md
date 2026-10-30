# Fullstack Agents

Unified fullstack development plugin with **29 specialized AI agents** and **30 skill domains** for intelligent code generation, review, analysis, scaffolding, debugging, and optimization across **Python (FastAPI) and Rust (Axum) microservices** behind one Next.js frontend. **Auto-triggers** on FastAPI/Rust/Next.js projects via SessionStart hook, with **enforced validation gates** via a PostToolUse hook and **strict language-lane separation** between Python and Rust skills.

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

Every session source (startup, resume, clear, compact) gets the same compact doctrine, so a compaction never loses it; the policy profile arrives as a separate block from `session-policy`. Projects with no FastAPI/Rust/Next.js markers get a 2-line notice instead of the full doctrine — token-efficient by design, with the quality floor (dialogue, confirmation, pattern review, validation, tests) never cut. The `using-fullstack-agents` skill carries an explicit Token Discipline section (scan once, skills load once, batch error fixes, parallel tool calls, targeted reads).

## Where rules live

Each rule has one home; the others point to it. Precedence, highest first: the user's explicit instruction, the
project's `CLAUDE.md` / `AGENTS.md`, the lead prompt, the `task-flow` skill, then the policy profile and other skills.

| Rule | Home | Reaches the model through |
|---|---|---|
| Ownership: who decides, evidence handling, precedence, engineering standard | `agents/lead/fullstack-agent.md` | the lead agent's system prompt |
| How work runs: light and full paths, briefs, audit, retries, verification | `skills/task-flow/` | the skill, loaded on demand |
| Summary for sessions whose main agent is not the lead | `hooks/session-doctrine.md` | `session-start`, skipped when `agent_type` is the lead |
| Reusable conventions a project opts into | `policies/<profile>.md` | `session-policy` (own context block) and implementer prompts |
| Project hard rails, development mode, bindings | the project's `AGENTS.md` / `CLAUDE.md` | Claude Code's project memory; engines natively |

## Enforced Validation Gates (PostToolUse Hook)

The generate → review → validate chain is enforced by the harness, not just by prompt instructions:

| Hook | Trigger | What it does |
|------|---------|--------------|
| `prompt-polish` | Every user prompt | Injects a directive to refine the raw request into a precise spec (intent / scope / success criteria / constraints) before acting and before delegating to worker subagents — full directive once per session, one-line reminder afterward; pure control replies (yes/continue) are skipped |
| `reply-classify` | Every finished reply (async) | Haiku marks the session as waiting on the user (`team-board wait`) when the reply asks for approval, a decision, an answer or an action; `FSA_WAIT_CLASSIFIER=off` disables it |
| `context-handoff` | After every tool call | Injects `HANDOFF:` once per compaction cycle when the lead's context reaches 200k tokens (`FSA_HANDOFF_TOKENS`) or 85% of the smallest size the session was compacted at, so the lead writes the checkpoint and hands over through a plan approval the user can accept with "Yes, clear context" (needs the Claude Code setting `showClearContextOnPlanAccept: true`) before automatic compaction; reads only new transcript bytes, skips subagents and implementer runs; `FSA_CONTEXT_HANDOFF=off` disables it |
| `auto-handoff` | Before `ExitPlanMode` | In a herdr pane, after `HANDOFF:` fired this cycle at a threshold of at least 100k tokens, waits for the plan-approval card and selects "Yes, clear context" when the plan file's first line is `# HANDOFF RESUME`, so the session hands over with no click; logs each outcome to `auto-handoff.log` in the state directory; `FSA_AUTO_HANDOFF=off` disables it |
| `prompt-scan` | Every user prompt | Classifies intent, lanes and skills with keyword rules, falling back to Haiku (`scripts/fsa-classify`, about 5 s) only for unmatched prompts of `FSA_ROUTER_MIN_WORDS` (6) or more words; `FSA_ROUTER=haiku` always uses Haiku, `FSA_ROUTER=regex` never does. Re-arms the routing mandate — full block once per session, one-line reminder afterward (token-efficient; the pre-edit gate enforces deterministically regardless) |
| `skill-gate` | Before every `Write`/`Edit`, and before writing a brief (any file with an `ALLOWED_PATHS:` block) | BLOCKS until every lane skill the paths map to has been invoked this session (a real Skill call, not a hint that names it). The map is `scripts/fsa-skill-map`, shared with the skills `codex-task.sh` attaches to implementer runs (a `SKILLS:` line only adds). A project may bind a document to a skill in `.claude/fsa-skill-docs` (`<skill> <path>` per line); a brief needing that skill must cite the path. Skipped inside implementer runs (`FSA_IMPLEMENTER_RUN`). Override: `FSA_SKIP_SKILL_GATE=1` |
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

## Scripts

The plugin ships its worker tooling in `scripts/`; the SessionStart hook prints their installed
path, so they work on any host with the plugin installed. Requires `git` and `jq`; herdr modes also
need a Herdr-managed pane (`HERDR_ENV=1`).

| Script | Purpose |
|---|---|
| `codex-task.sh [--herdr] investigate\|plan\|implement <brief>` | Dispatch one implementer unit (headless Claude Sonnet by default, Grok through `opencode` with `FSA_IMPLEMENTER=grok`, Codex with `FSA_IMPLEMENTER=codex`); validates the brief (`PLAN:`/`ALLOWED_PATHS:`, at most `FSA_MAX_ALLOWED_PATHS` paths, default 8; or `FILES:`/`REPORT:`), restricts the Claude and Grok engines' edit and write tools to `ALLOWED_PATHS`, flags other changed paths as `STATUS=OUT_OF_SCOPE`, prefixes the lane's skill files, snapshots touched paths, prints a manifest. `--herdr` runs it in a visible grid pane. |
| `herdr-watch.sh <transcript> [label]` | Read-only live view of a background worker's transcript in a grid pane; no model reads it. |

Optional environment: `FSA_CODEX_ROOT` (repository root, default the current git toplevel),
`FSA_CODEX_RUNS_DIR` (else `runs_dir=` in the project's `.claude/fsa-team.conf`, else `~/.codex/fsa-runs`; readers also scan `legacy_runs_dirs=`), `FSA_DISPATCH_EXIT` (`legacy`, the default, exits 0; `strict` maps the terminal state in `<run>.result.json` to exit codes 10-14, 130 when cancelled), `FSA_CANCEL_WAIT_S` (seconds to wait for a cancelled run's processes, default 10), `FSA_ACCEPT_PLUGIN_CHANGE=1` (dev mode only: dispatch although the plugin source changed since the session pin), `FSA_IMPLEMENTER` (`claude`, the default, `grok` or `codex`; a brief's `IMPLEMENTER:` line overrides it for that task),
`FSA_CLAUDE_MODEL_IMPLEMENT` (default `claude-sonnet-5`; the Claude engine only implements),
`FSA_GROK_MODEL_INVESTIGATE|IMPLEMENT` (opencode `provider/model`, default `xai/grok-4.7`; Grok has no plan mode because Claude plans),
`FSA_GROK_VARIANT` (opencode `--variant` reasoning effort such as `minimal`, `low`, `high`, `max`; unset keeps the model default; a brief's `EFFORT:` line overrides it for that task) and
`FSA_CODEX_MODEL_INVESTIGATE|PLAN|IMPLEMENT`. `FSA_CODEX_ADD_DIRS` (colon-separated) adds writable directories to Codex implement runs, for example a build cache outside the repository; without it the workspace-write sandbox cannot compile there. The Claude engine runs `cc -p` (the user's `cc` alias, resolved by `scripts/lib/claude_cli.py`; dispatch is refused without it) with project settings only (the user-scope plugin lead never
loads), a `--settings` PreToolUse fence (`scripts/lib/allowed-paths-fence`) that blocks `Edit`/`Write` outside the `ALLOWED_PATHS` entries even with permissions bypassed, test runners
denied, and `FSA_IMPLEMENTER_RUN=<run id>` exported for project edit gates; its structured output is
the result file. The Grok engine needs the `opencode` CLI and `XAI_API_KEY`;
investigate runs (opt-in with `FSA_GROK_INVESTIGATE=1`; wide scans default to the Haiku bounded-extractor) deny opencode edits and shell, implement runs allow both and are told to read by grep and line range, lane skills are trimmed to what the brief's paths need (a `SKILLS:` line overrides), and the final answer's
fenced JSON is extracted into the same result file Codex writes.
A project may keep a thin wrapper that sets these and `exec`s the plugin script.
Optional gates driven by `.claude/fsa-team.conf` (parsed by `scripts/lib/team_conf.py`, never sourced): `edit-budget-gate`
(`edit_budget` — recommended 5 — counts only gated files the current session edited successfully and has not committed, recorded per session id by its PostToolUse `record` mode, so other sessions' dirty files never spend it; `carve_outs`, `gated_extensions`), `read-guard` (`read_range_max`), `write-guard` (`gated_extensions`) and `scan-gate`
(`scan_gate=on`), each with its own `FSA_SKIP_*` flag; `generated_globs` (e.g. `.agent-cargo-cache/*`) keeps untracked generated output out of a run's out-of-scope report, listed instead as an informational `GENERATED:` count, while tracked files under those globs are still scope-checked; `runs_keep_days`/`runs_keep_failed_days`/`runs_keep_last` set `scripts/fsa-runs prune` retention (preview unless `--apply`); `policy_profile=engineering-conventions` enables the optional conventions profile
for the lead and every implementer. The `run-owner-gate` hook blocks hand edits to paths a live or uncertain implementer run owns, in any repository
(`FSA_SKIP_RUN_GATE=1` overrides on the user's word). A project's `AGENTS.md` reaches every engine: natively for Codex and
opencode, appended to the Claude implementer's system prompt unless `CLAUDE.md` imports it with `@AGENTS.md`.
`codex-task.sh release <run-id> [--confirm]` frees a run's paths only when `scripts/lib/liveness.py` finds no process that can still
edit for it. `scripts/fsa-release export <ref>` and `verify <dir>` build and check immutable, read-only plugin releases.

## License

MIT
