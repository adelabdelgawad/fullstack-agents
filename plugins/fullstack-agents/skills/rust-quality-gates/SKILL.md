---
name: rust-quality-gates
description: Non-skippable verification chain for Rust services — fmt, clippy with deny-warnings, cargo check, sqlx offline-cache drift, audit, migration safety, and the no-allow policy. Use after generating or modifying Rust code, before declaring any Rust work done, or when asked to gate or validate a Rust project. Do not use for Python validation (ruff/mypy are wired separately).
---

# Rust Quality Gates

The verify chain that runs after EVERY Rust change. The plugin's hooks enforce
the fast subset automatically (rustfmt on edit, fmt+clippy at stop); this skill
defines the full chain for post-generation and pre-commit.

## The Chain

| # | Gate | Command | Fails when |
|---|---|---|---|
| 1 | Format | `cargo fmt --all --check` | Any file unformatted |
| 2 | Lint | `cargo clippy --workspace --all-targets -- -D warnings` | Any warning (deny policy) |
| 3 | Compile | `cargo check --workspace` | Type errors |
| 4 | SQLx cache | `cargo sqlx prepare --check --workspace` | `.sqlx/` drifted from queries/schema |
| 5 | Audit | `cargo audit` | Known vulnerable dependency |
| 6 | Migration safety | grep migrations for DROP/TRUNCATE without `-- @destructive` | Unmarked destructive DDL |
| 7 | No-allow | grep `#[allow(` in crates/ and apps/ | Any silenced lint |
| 8 | Tests | `cargo test --workspace` | Any failure; coverage < 80% |

Run 1-3 after every change set; the full chain after generation and before
commit. Skip a gate ONLY when its tool is absent (e.g. no .sqlx/ in the
project, cargo-audit not installed) — say so explicitly, never silently.

## Order Matters

fmt → clippy → check → tests. Formatting noise hides real diffs; clippy
findings often change code that would invalidate test runs. Fix ALL errors from
a step before rerunning (batch-error-resolution — never fix-one-rebuild-loop).

## Justfile Integration

If the project has a justfile, prefer its recipes — they encode project-specific
crate lists and feature flags:

```makefile
check:
    cargo fmt --all --check
    cargo clippy --workspace --all-targets -- -D warnings
    cargo test --workspace

prepare:
    cargo sqlx prepare --workspace
```

## Workspace Policy (what the gates assume)

```toml
[workspace.lints.rust]
warnings = "deny"
[workspace.lints.clippy]
all = { level = "deny", priority = -1 }
```

- Warnings are errors — there is no warning backlog to triage later.
- `#[allow(...)]` is forbidden in crate/app code: fix the root cause. The ONLY
  exception is generated code, isolated in its own module and documented.
- Toolchain pinned in `rust-toolchain.toml` — gates run on the pinned version.

## CI Mirror

CI runs the same chain plus a fresh-database migration check:

```yaml
- run: cargo fmt --all --check
- run: cargo clippy --workspace --all-targets -- -D warnings
- run: sqlx migrate run --source migrations   # empty Postgres must migrate cleanly
- run: cargo test --workspace
```

If CI and local gates diverge, CI is the source of truth — update the justfile.

## Remediation Map

| Failure | Action |
|---|---|
| fmt | `cargo fmt --all` — never hand-format |
| clippy warning | Fix the code; if clippy is genuinely wrong, restructure so the lint doesn't fire — no `#[allow]` |
| sqlx prepare --check | `cargo sqlx prepare --workspace` and commit `.sqlx/` |
| audit vulnerability | Upgrade the dependency; if no fix released, document and pin the decision |
| unmarked destructive migration | Add `-- @destructive` + rollback plan, or rewrite non-destructively |
| coverage < 80% | Add tests at the cheapest layer (see rust-testing) |
