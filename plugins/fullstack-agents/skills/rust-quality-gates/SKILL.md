---
name: rust-quality-gates
description: Rust verification chain — fmt, clippy deny-warnings, cargo check, sqlx offline cache, audit, migration safety. Before declaring Rust work done.
---

# Rust Quality Gates

Which Rust checks run, when, and on what. **The project's own bindings (`CLAUDE.md`, `AGENTS.md`, justfile) come first**:
their commands, crate scopes, features, environment and test runners replace every generic command below. Use the
generic forms only where the project names nothing.

## Per change set (fast, scoped to the touched crates)

| Gate | Generic command | Notes |
|---|---|---|
| Format | `rustfmt --edition <edition> <changed files>` | only the files you changed; `cargo fmt --all` only when the project declares its tree rustfmt-clean |
| Lint + compile | `cargo clippy -p <touched crates> --all-targets -- -D warnings` (plus the project's required env/features, e.g. `SQLX_OFFLINE=true`) | clippy performs the full type-check, so no separate `cargo check` for the same configuration |
| Other configurations | one extra `cargo check` per configuration clippy did not exercise (another feature set, `--no-default-features`, another target or profile, live SQLx validation) | list them in the project binding; skip when there are none |

The implementer runs the lint + compile gate before returning. The lead runs it **once on the integrated state** (after
all units of the deliverable landed), not again merely because work changed hands; rerun only after a later change.

## Tests (through the project's runner)

- Run tests only through the project's designated runner and only against **isolated test infrastructure** (a
  disposable database, fixtures, a test container). Never against a production database, a production
  `DATABASE_URL`, or shared live services, during development or release. If the runner cannot prove isolation, do not
  run the tests: report the gap.
- Affected test targets first; one whole-crate run per deliverable at the end.
- Split a run expected to exceed ~8 minutes into target groups, each its own command with its own log, run one after
  another (never two Cargo jobs on one build directory at once). A group that timed out or did not run is not a pass;
  report which groups completed.
- Add tests at the cheapest layer that proves the behaviour (see rust-testing). There is no coverage percentage gate.

## Release only

Workspace-wide clippy, `cargo audit`, `cargo sqlx prepare --check --workspace`, and any whole-workspace test run — each
only with isolated test infrastructure as above.

## Always

- Warnings are errors; no `#[allow(...)]` in crate/app code: fix the root cause (generated code in its own module is the
  only exception).
- Destructive migrations (`DROP`, `TRUNCATE`) are marked `-- @destructive` with a rollback plan, or rewritten.
- Fix all errors from one gate before rerunning it (batch-error-resolution), in the order fmt → clippy → tests.
- No hook runs these gates for you: the plugin's edit hook formats changed Rust files only where the project allows it.

## Remediation

| Failure | Action |
|---|---|
| fmt | format only the changed files; never hand-format |
| clippy | fix the code; if clippy is genuinely wrong, restructure so the lint does not fire |
| sqlx offline cache drift | `cargo sqlx prepare` for the touched crates against the isolated database, commit `.sqlx/` |
| audit | upgrade the dependency; if no fix exists, document and pin the decision |
| destructive migration | add `-- @destructive` and a rollback plan, or rewrite non-destructively |
