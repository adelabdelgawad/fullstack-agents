---
name: using-fullstack-agents
description: Auto-triggering guide for fullstack-agents — ensures Claude automatically invokes the right code generation, review, and debugging skills before writing any FastAPI or Next.js code.
---

<EXTREMELY-IMPORTANT>
If you are about to write, modify, or generate ANY code in a FastAPI backend or Next.js frontend, you MUST consult fullstack-agents skills first.

This is not negotiable. This is not optional. You cannot rationalize your way out of this.

IF A FULLSTACK-AGENTS SKILL APPLIES TO YOUR TASK, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT.
</EXTREMELY-IMPORTANT>

# Using Fullstack Agents

## The Rule

**Before writing ANY backend or frontend code, check if a fullstack-agents skill covers it.** Even a 1% chance means invoke the skill. If it turns out to be wrong for the situation, you don't need to follow it — but you MUST check first.

## Language Separation — Python vs Rust (HARD RULE)

This plugin serves polyglot microservices: Python (FastAPI) and Rust (Axum)
backends behind ONE Next.js frontend. Skills are language-scoped and MUST NOT
cross:

```
LANGUAGE LANE DETECTION (before any routing):
  Cargo.toml / *.rs / migrations next to a Cargo workspace  → RUST lane
  pyproject.toml / requirements.txt / *.py                  → PYTHON lane
  package.json + next / *.ts / *.tsx                        → FRONTEND lane
  Both Cargo.toml and pyproject.toml in the repo            → route PER FILE/SERVICE,
                                                              never blend idioms
```

- RUST lane skills: `rust-clean-architecture`, `rust-axum-api`, `rust-sqlx`,
  `rust-correctness`, `rust-testing`, `rust-quality-gates`, `rust-nextjs-contract`.
- PYTHON lane skills: `fastapi` (existing simplified pattern),
  `python-clean-architecture` (new DDD microservices), `celery`,
  `tasks-management`. Within Python: codebase-scanning decides — existing
  simplified-pattern services stay on `fastapi`; NEW microservices use
  `python-clean-architecture`.
- NEVER transplant idioms across lanes: no Pydantic/CamelModel concepts in Rust
  code, no thiserror/ownership patterns in Python, no SQLAlchemy patterns in
  SQLx code or vice versa. The CONCEPTS align (same clean-architecture layers,
  same four-stage error model, same wire contract) — the idioms never do.
- ANY Rust endpoint consumed by Next.js must follow `rust-nextjs-contract` so
  Rust and FastAPI services are interchangeable behind the same frontend.

**When to choose which language (new services):** Rust for performance-critical,
high-throughput, or long-lived always-on services; Python for ML/data-heavy
work, rapid iteration, and extending the existing FastAPI estate. If the user
hasn't specified, ask — never guess the lane for a NEW service.

## Routing Table

When you detect the user's intent, route to the correct skill or agent. Two kinds of targets:

- **Skill** — invoke with the `Skill` tool using the exact name shown (e.g. `fullstack-agents:fastapi`).
- **Agent** — launch as a subagent using the exact agent name shown (the user-facing equivalent is the slash command in parentheses).

| User Intent Pattern | Target |
|---|---|
| "create entity", "add model", "CRUD", "backend API for X" | Skill `fullstack-agents:fastapi` (agent: `generate-fastapi-entity`, `/generate entity`) |
| "data table", "management page", "list page with CRUD" | Skill `fullstack-agents:data-table` (agent: `generate-nextjs-data-table`, `/generate data-table`) |
| "create page", "new page", "frontend page" | Skill `fullstack-agents:nextjs` (agent: `generate-nextjs-page`, `/generate page`) |
| "API route", "proxy route", "Next.js API" | Skill `fullstack-agents:fetch-architecture` (agent: `generate-api-route`, `/generate api-route`) |
| "celery task", "background task", "async task" | Skill `fullstack-agents:celery` (agent: `generate-celery-task`, `/generate task`) |
| "scheduled job", "cron job", "periodic task" | Skill `fullstack-agents:tasks-management` (agent: `generate-scheduled-job`, `/generate job`) |
| "docker service", "add container", "compose setup" | Skill `fullstack-agents:docker` (agent: `generate-docker-service`, `/generate docker-service`) |
| "websocket", "real-time", "live updates" | Skill `fullstack-agents:websocket` |
| "fullstack feature", "create X end-to-end" | `/generate fullstack` orchestration (fastapi → fetch → data-table skills in sequence) |
| "debug", "error", "fix", "broken", "not working" | Skill `fullstack-agents:debug` |
| build/tests/lint failing with MULTIPLE errors | Skill `fullstack-agents:batch-error-resolution` |
| "review", "check quality", "audit" | Agent `review-code-quality` (`/review quality`) |
| "security review", "security audit" | Agent `review-security` (`/review security`) |
| "performance review", "slow", "optimize" | Agent `review-performance` or `optimize-performance` (`/review performance`, `/optimize`) |
| "check patterns", "validate patterns" | Agent `review-patterns-compliance` (`/review patterns`) |
| "analyze codebase", "architecture review" | Agent `analyze-codebase` or `analyze-architecture` (`/analyze`) |
| "scaffold project", "new project", "bootstrap" | Agent `scaffold-project-fastapi` / `scaffold-project-nextjs` (`/scaffold`) |
| "validate entity", "check entity compliance" | `/validate` command |
| "validate fetch", "check fetch patterns", "fetch audit" | Skill `fullstack-agents:fetch-validate` |
| "plan fetch", "fetch layers for X" | Skill `fullstack-agents:fetch-plan` |
| "scaffold fetch", "generate fetch boilerplate" | Skill `fullstack-agents:fetch-implement` |
| "refactor", "clean up", "reduce duplication", "extract shared logic" | Skill `fullstack-agents:senior-engineer` (agent: `optimize-refactoring`, `/optimize`) |
| ANY implementation work (standing discipline, see gate step 3) | Skill `fullstack-agents:senior-engineer` |
| **RUST LANE** (Cargo.toml / *.rs detected) | |
| "rust service", "rust microservice", "structure rust", "rust entity", "where does this go (rust)" | Skill `fullstack-agents:rust-clean-architecture` (agent: `generate-rust-entity`) |
| "axum handler", "rust endpoint", "rust route", "rust middleware", "rust websocket" | Skill `fullstack-agents:rust-axum-api` |
| "sqlx", "rust query", "rust migration", "rust repository" | Skill `fullstack-agents:rust-sqlx` |
| borrow checker / lifetime / Send/Sync / E0382-E0599 errors | Skill `fullstack-agents:rust-correctness` |
| "rust test", cargo test failures | Skill `fullstack-agents:rust-testing` |
| "validate rust", "gate rust", post-Rust-generation verify | Skill `fullstack-agents:rust-quality-gates` |
| Rust endpoint that Next.js will consume | Skill `fullstack-agents:rust-nextjs-contract` (ALWAYS, with the generating skill) |
| **PYTHON LANE** (pyproject.toml / *.py detected) | |
| "new python microservice", "python DDD", "python clean architecture" | Skill `fullstack-agents:python-clean-architecture` |
| existing simplified-pattern FastAPI work | Skill `fullstack-agents:fastapi` (codebase-scanning decides) |

## Hard Gate — 5-Step Check Before ANY Code Generation

Before writing ANY code that touches FastAPI or Next.js, run this mental gate:

```
1. DETECT  → What type of code is being requested?
             (model, schema, router, page, component, API route, task, etc.)

2. MATCH   → Does a fullstack-agents skill cover this?
             (Check the routing table above)

3. REUSE   → Does this functionality (or something close) already exist?
             Search the codebase for existing implementations, helpers,
             utilities, hooks, and components BEFORE writing new code.
             Never knowingly duplicate business logic — reuse, extend, or
             extract a shared abstraction instead.
             (Discipline: fullstack-agents:senior-engineer)

4. INVOKE  → If a skill matched: invoke it BEFORE writing any code
             If NO match: proceed normally but still respect codebase
             patterns and the senior-engineer discipline

5. SCAN    → Has codebase-scanning run this session?
             If NO: invoke fullstack-agents:codebase-scanning first
             If YES: use the detected style profile
```

**Do NOT skip to step 4.** Detection, matching, and the reuse search must happen first.

## Senior Engineer Standard (always on)

The `fullstack-agents:senior-engineer` skill governs ALL implementation work —
generation, modification, and bug fixes alike. Its non-negotiables:

- **Search before implement** — find existing implementations before writing new ones.
- **No knowing duplication** — reuse, extend, or extract; never fork business logic.
- **Hard limits** — functions < 50 lines, files < 800 lines, nesting <= 4 levels
  (the Stop hook blocks sessions that grow files past 800 lines).
- **Right layer** — presentation, business logic, domain, and data access stay
  separated; dependencies point inward.
- **Leave it cleaner** — when touching existing code, improve naming, control flow,
  and boundaries in the code you touch.

For the full workflow, search recipe, and definition of done, invoke
`fullstack-agents:senior-engineer` via the Skill tool.

## Rationalization Prevention

These thoughts mean STOP — you're rationalizing skipping the skill:

| Thought | Reality |
|---|---|
| "This is just a simple endpoint" | Simple endpoints still need pattern compliance (CamelModel, session handling, response schemas). |
| "I'll just add one field to the model" | Model changes cascade to schemas, routers, and frontend types. Check the skill. |
| "It's only a small component" | Small components still need to follow existing naming, import, and state patterns. |
| "I know how FastAPI works" | Knowing FastAPI ≠ knowing THIS project's FastAPI patterns. Invoke the skill. |
| "I know how Next.js works" | Knowing Next.js ≠ knowing THIS project's data-fetching and state patterns. |
| "The user said to do it quickly" | Fast AND correct > fast AND wrong. Skills prevent rework. |
| "This is a trivial change" | Trivial changes with wrong patterns create tech debt. Check first. |
| "I'll fix the patterns later" | Later never comes. Get it right the first time. |
| "This doesn't need a full generation" | Even partial generation benefits from pattern detection. |
| "I remember the patterns from earlier" | Patterns evolve. Skills have the current reference. Re-read. |
| "Let me just scaffold this by hand" | The generate agents handle scaffolding WITH pattern compliance. |
| "It's just a type definition" | Types must match CamelModel conventions and API contracts. |
| "It's faster to copy that existing function" | Copying forks the logic forever. Reuse or extract — never duplicate. |
| "I'll extract the duplication later" | Later never comes. Extract NOW, while both copies are in context. |
| "A small private helper here won't hurt" | Three private helpers in three files IS the duplication problem. Search first. |
| "Rust and Python are similar enough here" | Same concepts, different idioms. Wrong-lane patterns are bugs (e.g. `:id` routes, Pydantic-style DTOs in Rust). |
| "The frontend will adapt to my response shape" | The frontend adapts to NOTHING. Match the FastAPI wire contract exactly (rust-nextjs-contract). |

## Automatic Chaining Rules

After ANY code generation completes, the following chain fires **automatically**:

```
GENERATE → REVIEW PATTERNS → FIX VIOLATIONS → VALIDATE → PRESENT NEXT STEPS
```

Specifically:

1. **Generate** — the agent produces code
2. **Review patterns** — automatically run pattern compliance review on generated code (equivalent to `/review patterns {entity}`)
3. **Fix violations** — if any violations found, fix them immediately
4. **Validate** — run type check + lint verification from the DETECTED project roots
   (repo root for flat layouts; `src/backend/` / `src/frontend/` for nested layouts —
   use whatever codebase-scanning detected, never assume the nested layout),
   matched to the LANGUAGE LANE of the generated code:
   - Python backend: `uv run mypy . && uv run ruff check .`
   - Rust backend: `cargo fmt --all --check && cargo clippy --workspace --all-targets -- -D warnings && cargo test --workspace` (full chain: rust-quality-gates)
   - Frontend: `npx tsc --noEmit && npm run lint`

   A PostToolUse hook also runs `ruff` on edited Python files and `rustfmt` on
   edited Rust files, and a Stop hook re-validates session-modified files (ruff /
   cargo fmt+clippy / tsc) — if a hook reports violations, fix them immediately;
   they are the same gate enforced by the harness.
5. **Present next steps** — only THEN show the user what was created and suggest follow-up actions

**Do NOT ask the user's permission between steps 1-4. They are mandatory.**

## Codebase Scanning Mandate

On the **first code generation** in any session:
- You MUST invoke the `fullstack-agents:codebase-scanning` skill BEFORE generating code
- This detects project structure, naming conventions, and existing patterns
- The detected style profile overrides any reference patterns in the skills
- Subsequent generations in the same session can reuse the cached profile

## Skill Priority

When both `superpowers` and `fullstack-agents` apply:

- **superpowers** handles workflow orchestration (brainstorm → plan → execute)
- **fullstack-agents** handles code generation specifics (pattern detection, generation, review)

They complement each other. Use superpowers for the workflow, fullstack-agents for the code.

## How to Access Skills

Use the `Skill` tool to invoke any fullstack-agents skill. When you invoke a skill, its content is loaded and presented to you — follow it directly. Never use the Read tool on skill files.

## Skill Types

**Rigid** (generate agents, review agents): Follow the agent lifecycle exactly. Don't skip phases.

**Flexible** (analyze, optimize): Adapt the approach to the specific situation.

The skill/agent itself tells you which type it is.
