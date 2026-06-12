---
name: rust-sqlx
description: SQLx + PostgreSQL patterns for Rust services — compile-time-verified query macros, Executor-generic repository functions, FromRow type mapping, pool configuration, migration discipline, offline cache for CI, and SQLSTATE error mapping. Use when writing Rust database code, repositories, migrations, or queries. Do not use for SQLAlchemy/Python data access (use fastapi or python-clean-architecture).
---

# SQLx + PostgreSQL Patterns

Data access for Rust services. Repository implementations live in
`infrastructure` and receive `&mut PgConnection` from use cases that own the
transaction (see rust-clean-architecture).

## Query Macro Selection

| Macro | Returns | Use for |
|---|---|---|
| `query!` | anonymous record | one-off reads/writes |
| `query_as!(T, ...)` | named struct | mapping into Row types |
| `query_scalar!` | single column | counts, EXISTS, single values |
| `query_file!` | from .sql file | long/shared SQL |

Macros verify SQL against the schema AT COMPILE TIME — wrong column names are
compile errors. Prefer macros; runtime `query()`/`query_as::<_, T>()` is
acceptable when the template's runtime-query style is already established
(detected by codebase-scanning) or for dynamic SQL with bound parameters.

```rust
let user = sqlx::query_as!(UserRow,
    "SELECT id, username, email FROM users WHERE id = $1", id)
    .fetch_optional(&mut *conn)
    .await?;
```

- `fetch_optional` for lookups that may miss — NEVER `fetch_one` (turns a
  missing row into an error you must untangle).
- `fetch_one` only when absence is a bug (e.g. RETURNING after INSERT).
- SQLx 0.9 note: runtime `query()` requires `&'static str` or an
  `AssertSqlSafe` wrapper — user input must NEVER be interpolated into SQL
  text; it goes in `$n` bind parameters.

## Executor-Generic Functions

One signature serves pool, connection, and transaction:

```rust
pub async fn find_user<'e, E>(executor: E, id: Uuid) -> sqlx::Result<Option<UserRow>>
where E: Executor<'e, Database = Postgres>,
{
    sqlx::query_as!(UserRow, "SELECT * FROM users WHERE id = $1", id)
        .fetch_optional(executor).await
}
// call with &pool, &mut conn, or &mut *tx
```

For port traits (which must be object-safe for `Arc<dyn ...>`), use
`&mut PgConnection` parameters instead — both pool connections and
transactions deref to it.

## Type Mapping

| Rust | PostgreSQL |
|---|---|
| `uuid::Uuid` | UUID |
| `chrono::DateTime<Utc>` | TIMESTAMPTZ |
| `rust_decimal::Decimal` | NUMERIC |
| `Option<T>` | NULLABLE column |
| `serde_json::Value` / `#[sqlx(json)]` | JSONB |
| `i64` / `i32` | BIGINT / INTEGER |

`FromRow` attributes: `#[sqlx(rename = "...")]`, `#[sqlx(default)]`,
`#[sqlx(json)]`, `#[sqlx(flatten)]`. Row structs are `pub(crate)` in
infrastructure — never exported, never serialized to the wire.

## Transactions

```rust
let mut tx = pool.begin().await?;          // use case owns this
repo_a.insert(&mut tx, &a).await?;
repo_b.insert(&mut tx, &b).await?;
tx.commit().await?;                        // explicit; drop = rollback
```

Savepoints: `tx.begin().await?` inside a transaction nests one.

## Pool Configuration

```rust
PgPoolOptions::new()
    .max_connections(config.db_max_conn)   // from config, not hardcoded
    .acquire_timeout(Duration::from_secs(5))
    .connect(&config.database_url).await?
```

Never hold a connection across an `.await` on unrelated work; acquire late,
release early. Tests use transactional fixtures (`#[sqlx::test]`) for isolation.

## Migrations

- Filename: `NNNN_snake_case.sql` or `YYYYMMDDHHMMSS_snake_case.sql` — pick the
  project's existing convention (codebase-scanning detects it) and stay consistent.
- Idempotent DDL: `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`.
- Destructive statements (DROP/TRUNCATE/column drops) require an explicit
  `-- @destructive` marker comment and a stated rollback plan.
- `sqlx migrate run` at service startup (`run_migrations(&pool)`), and fresh-DB
  migration must succeed end-to-end in CI.

## Offline Cache (CI without a database)

```bash
cargo sqlx prepare --workspace     # writes .sqlx/ — COMMIT IT
```

CI builds use the cache; no DATABASE_URL needed. Regenerate after ANY schema or
query change — `cargo sqlx prepare --check` in the quality gate catches drift.

## Error Mapping (SQLSTATE)

Map at the RepoError boundary; never let `sqlx::Error` escape infrastructure:

| SQLSTATE | Meaning | RepoError | AppError |
|---|---|---|---|
| — RowNotFound | missing row | `NotFound` | `NotFound` |
| 23505 | unique violation | `UniqueViolation` | `Conflict` |
| 23514 | check violation | `CheckViolation` | `Validation` |
| 23503 | FK violation | `ForeignKeyViolation` | `Conflict` |
| other | infrastructure | `Database(msg)` | `Internal` (logged, hidden) |

## Forbidden Patterns

| Pattern | Why |
|---|---|
| String interpolation of user input into SQL | Injection — bind with `$n` always |
| `fetch_one` for nullable lookups | Use `fetch_optional` + `ok_or(NotFound)` |
| `sqlx::Error` in port signatures or responses | Map to `RepoError` at the adapter |
| Transaction opened inside a repository | Use cases own transactions |
| Row structs exported or serialized | Private to infrastructure; DTOs are separate |
| Stale `.sqlx/` cache committed | `cargo sqlx prepare --check` in the gate |
| Unbounded pool / hardcoded connection limits | Configure from `AppConfig` |
