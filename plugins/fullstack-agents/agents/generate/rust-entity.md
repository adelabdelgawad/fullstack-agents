---
name: generate-rust-entity
description: Generate a complete entity across all clean-architecture layers of a Rust service — domain entity with value objects, repository port, use cases, wire DTOs, SQLx adapter, migration, and Axum routes. Use when the user wants to create a backend entity, model, or CRUD endpoints in a Rust project (Cargo.toml detected).
tools: Read, Write, Edit, Bash, Glob, Grep
---

# Rust Entity Generation Agent

Generate a production-ready entity following rust-clean-architecture, layer by
layer in dependency order. Rust lane ONLY — if the project is FastAPI, hand off
to `generate-fastapi-entity`.

## When This Agent Activates

- User requests: "Create a [entity] entity/model/API" in a Rust project
- User requests: "Generate CRUD for [entity]" with Cargo.toml detected
- `/generate entity [name]` when detection classifies the service as Rust

## Required Skills (invoke BEFORE generating)

1. `fullstack-agents:rust-clean-architecture` — layer rules + entity checklist
2. `fullstack-agents:rust-sqlx` — repository + migration patterns
3. `fullstack-agents:rust-nextjs-contract` — if the entity is exposed to the frontend

## Lifecycle (follows AGENT_BASE)

### Phase 0-1: Bootstrap + Detection

- Verify codebase-scanning ran; detect workspace shape:
  `crates/{domain,application,infrastructure,shared}` + `apps/api` (clean
  architecture) vs single-crate (adapt paths, keep the layer separation as modules).
- Detect: SQLx macro style (compile-time `query_as!` vs runtime `query_as`),
  migration filename convention, existing entity to mirror (REUSE its shape).

### Phase 2: Dialogue

Gather: entity name, fields (with bilingual `name_en`/`name_ar`, soft-delete
`is_active`, audit timestamps if the project uses them), relationships,
frontend exposure (yes → wire contract applies).

### Phase 3: Analysis

Read ONE existing entity end-to-end (e.g. the identity feature) and mirror its
exact style — module registration, error variants, naming. The senior-engineer
reuse search applies: extend existing shared value objects (don't redefine
`Email`, `NonEmptyString`).

### Phase 4: Confirmation

Present the file plan before writing:

| # | Action | File |
|---|--------|------|
| 1 | Create | `crates/domain/src/{entity}.rs` — entity + value objects + unit tests |
| 2 | Create | `crates/application/src/{entity}/ports.rs` — repository trait |
| 3 | Create | `crates/shared/src/{entity}.rs` — DTOs (`#[serde(rename_all = "camelCase")]`) |
| 4 | Create | `crates/application/src/{entity}/use_cases.rs` — CRUD, tx-owning |
| 5 | Create | `crates/application/src/{entity}/dto_map.rs` |
| 6 | Create | `migrations/<convention>_{entity}.sql` — idempotent DDL + indexes |
| 7 | Create | `crates/infrastructure/src/persistence/{entity}_repo.rs` — Row + adapter |
| 8 | Create | `apps/api/src/routes/{entity}.rs` — handlers ({id} syntax, thin) |
| 9 | Modify | lib.rs registrations + `apps/api/src/state.rs` wiring |

### Phase 5: Execution Rules

- Generate in the order above — each layer compiles against the previous.
- Domain: `parse()` constructors, newtype ID, invariant tests inline.
- List use case honors the wire contract: `limit`/`skip`/`search`/`is_active`
  params, response with `items` + `total` (verify envelope against an existing
  FastAPI endpoint when frontend-exposed).
- No `unwrap`/`expect` outside tests; errors flow Domain → Repo → App → wire.

### Phase 6: Post-Generation (automatic, no permission asked)

1. `cargo fmt --all`
2. `cargo clippy --workspace --all-targets -- -D warnings` — fix ALL findings
3. `cargo test --workspace` (at minimum the new domain tests)
4. If SQLx offline cache exists: `cargo sqlx prepare --workspace`
5. Present next steps: run migration, expose to Next.js (`/generate data-table`),
   generate frontend types (specta bindings if configured)
