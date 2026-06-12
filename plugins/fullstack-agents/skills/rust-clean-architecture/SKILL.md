---
name: rust-clean-architecture
description: Clean Architecture + DDD for Rust API microservices — Cargo workspace with domain/application/infrastructure/shared crates, ports and adapters, use-case-owned transactions, parse-don't-validate value objects, four-stage error model, and composition root. Use when creating or structuring a Rust service, deciding where Rust code belongs, or generating Rust entities end-to-end. Do not use for Python services (use python-clean-architecture) or frontend code. No Leptos — Rust serves JSON APIs only.
---

# Rust Clean Architecture + DDD

Pragmatic Clean Architecture for Rust API microservices. Crates ARE the layers —
the compiler enforces the dependency rule, not convention. The API serves JSON
(consumed by Next.js or other services); there is NO Rust frontend.

## Workspace Layout

```
my-service/
├── Cargo.toml              # virtual workspace: members = ["crates/*", "apps/*"]
├── rust-toolchain.toml     # pinned channel + clippy + rustfmt
├── justfile                # db / prepare / check / fmt recipes
├── migrations/             # single idempotent SQL timeline
├── crates/
│   ├── domain/             # entities, value objects, invariants — PURE
│   ├── application/        # use cases, ports (traits), DTO mapping, AppError
│   ├── infrastructure/     # SQLx repos, config, JWT/Argon2, telemetry
│   └── shared/             # wire DTOs (serde camelCase), pagination, wire errors
└── apps/
    ├── api/                # Axum host: routers, handlers, middleware, composition root
    └── worker/             # background jobs (advisory-lock singleton harness)
```

**Feature-first inside, layer-first outside.** Crates are layers (enforce the
rule); modules inside crates are features (`identity/`, `notes/`). Read a
feature top-to-bottom across layers, never a layer side-to-side.

## Layer Rules (compiler-enforced)

| Crate | Contains | FORBIDDEN dependencies |
|---|---|---|
| `domain` | Entities, value objects, domain services, `DomainError`, invariants | sqlx, axum, redis, serde, tokio — anything framework |
| `application` | Use cases, repository ports (traits), DTO↔entity mapping, `AppError`, transaction boundaries | axum, redis, infrastructure, hand-written SQL. Allowed: sqlx TYPES only (`PgPool`, `PgConnection`, `Transaction`) |
| `infrastructure` | SQLx repository impls, Argon2/JWT, Redis, config, telemetry | axum routers, depending on `apps/*` |
| `shared` | Wire DTOs, wire error enum, pagination types | domain, application, infrastructure, sqlx |
| `apps/api` | Axum routers/handlers/middleware, composition root | business logic (delegate to use cases) |
| `apps/worker` | Job harness + concrete jobs | axum |

Dependency edges (Cargo.toml):
```
apps/api    → application + infrastructure + shared
apps/worker → application + infrastructure + shared
application → domain + shared (+ sqlx types)
infrastructure → domain + application + shared
shared      → serde only
domain      → thiserror, uuid, chrono only
```

**The sole inversion seam:** repository ports are traits in `application`,
implemented in `infrastructure`. No Unit-of-Work — use cases open transactions
and thread `&mut PgConnection` through ports.

## DDD Building Blocks

- **Value objects** parse, don't validate — fallible constructor, then always valid:

```rust
// crates/domain/src/identity/value_objects.rs
pub struct Email(String);
impl Email {
    pub fn parse(raw: &str) -> Result<Self, DomainError> {
        let normalized = raw.trim().to_lowercase();
        let valid = match normalized.split_once('@') {
            Some((local, domain)) => !local.is_empty() && domain.contains('.'),
            None => false,
        };
        if !valid || normalized.len() > 254 {
            return Err(DomainError::Validation(format!("invalid email: {raw}")));
        }
        Ok(Self(normalized))
    }
    /// Only for rehydrating rows already validated at write time.
    pub fn from_trusted(value: impl Into<String>) -> Self { Self(value.into()) }
    pub fn as_str(&self) -> &str { &self.0 }
}

pub struct UserId(Uuid);   // newtype IDs — never pass raw Uuid across layers
impl UserId {
    pub fn generate() -> Self { Self(Uuid::new_v4()) }
    pub fn from_uuid(u: Uuid) -> Self { Self(u) }
    pub fn as_uuid(&self) -> Uuid { self.0 }
}
```

- **Entities** enforce invariants in constructors and expose intent-named behavior:

```rust
// crates/domain/src/identity/user.rs
impl User {
    pub fn create(username: Username, email: Email, password_hash: PasswordHash,
                  is_super_admin: bool, now: DateTime<Utc>) -> Self {
        Self { id: UserId::generate(), username, email, password_hash,
               is_super_admin, is_active: true, created_at: now, updated_at: None }
    }
    pub fn can_login(&self) -> bool { self.is_active }
}
```

- **Aggregates**: one entity owns the consistency boundary; repositories exist
  per aggregate root, not per table.
- **Ubiquitous language**: module, type, and use-case names mirror the business
  vocabulary (`can_login`, not `check_flag`).

## Four-Stage Error Model

Errors transform as they cross layers; internals never reach the wire.

```rust
// 1. DomainError (crates/domain) — business failures only
#[derive(Debug, thiserror::Error)]
pub enum DomainError {
    #[error("validation: {0}")] Validation(String),
    #[error("invariant violated: {0}")] Invariant(String),
}

// 2. RepoError (crates/application) — persistence failures, SQLSTATE-mapped
#[derive(Debug, thiserror::Error)]
pub enum RepoError {
    #[error("row not found")] NotFound,
    #[error("unique violation: {0}")] UniqueViolation(String),
    #[error("database error: {0}")] Database(String),
}
impl From<sqlx::Error> for RepoError {
    fn from(e: sqlx::Error) -> Self {
        match &e {
            sqlx::Error::RowNotFound => RepoError::NotFound,
            sqlx::Error::Database(db) => match db.code().as_deref() {
                Some("23505") => RepoError::UniqueViolation(db.message().to_owned()),
                _ => RepoError::Database(e.to_string()),
            },
            _ => RepoError::Database(e.to_string()),
        }
    }
}

// 3. AppError (crates/application) — the app's canonical Result type
#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error(transparent)] Domain(#[from] DomainError),
    #[error("not found")] NotFound,
    #[error("conflict: {0}")] Conflict(String),
    #[error("validation: {0}")] Validation(String),
    #[error("unauthorized")] Unauthorized,
    #[error("forbidden")] Forbidden,
    #[error("internal error")] Internal(String),  // logged, never exposed
}

// 4. Wire error (crates/shared) — client-safe, internal detail DROPPED
#[derive(Serialize, Deserialize)]
pub enum ApiError {
    Validation(String), NotFound, Conflict(String),
    Unauthorized, Forbidden, Unknown,
}
impl From<AppError> for ApiError {
    fn from(e: AppError) -> Self {
        match e {
            AppError::Internal(_) => ApiError::Unknown,   // detail hidden
            /* map the rest 1:1 */
            // ...
        }
    }
}
```

`IntoResponse` for `AppError` lives in `apps/api` (see rust-axum-api skill).

## Ports & Adapters

```rust
// PORT — crates/application/src/identity/ports.rs
#[async_trait]
pub trait UserRepository: Send + Sync {
    async fn insert(&self, conn: &mut PgConnection, user: &User) -> Result<(), RepoError>;
    async fn find_by_id(&self, conn: &mut PgConnection, id: UserId) -> Result<Option<User>, RepoError>;
}

// ADAPTER — crates/infrastructure/src/persistence/user_repo.rs
#[derive(FromRow)]
struct UserRow { id: Uuid, username: String, /* ... */ }
impl UserRow {
    fn into_domain(self) -> User {
        User { id: UserId::from_uuid(self.id),
               username: Username::from_trusted(self.username), /* ... */ }
    }
}
pub struct PgUserRepository;
#[async_trait]
impl UserRepository for PgUserRepository { /* SQLx queries, Row → domain */ }
```

Row types are private to infrastructure. Domain entities never derive `FromRow`
or `Serialize`. See rust-sqlx for query patterns.

## Use Cases Own Transactions

```rust
// crates/application/src/identity/use_cases.rs
pub async fn create_user(
    pool: &PgPool,
    users: &dyn UserRepository,
    hasher: &dyn PasswordHasher,
    input: CreateUserDto,
) -> Result<UserDto, AppError> {
    let username = Username::parse(&input.username)?;   // parse, don't validate
    let email = Email::parse(&input.email)?;
    let hash = hasher.hash(&input.password)?;
    let user = User::create(username, email, hash, input.is_super_admin, Utc::now());

    let mut tx = pool.begin().await?;                    // use case owns the tx
    users.insert(&mut tx, &user).await?;
    tx.commit().await?;

    Ok(user_dto(&user))                                  // DTO out, never the entity
}
```

DTO mapping is a free function in `application` (orphan-rule safe):

```rust
// crates/application/src/identity/dto_map.rs
pub fn user_dto(u: &User) -> UserDto {
    UserDto { id: u.id.as_uuid(), username: u.username.as_str().to_owned(), /* ... */ }
}
```

Wire DTOs live in `shared` with `#[serde(rename_all = "camelCase")]` — matching
the Next.js consumer's conventions. Optionally derive `specta::Type` and export
TypeScript bindings from a test for end-to-end type safety with the frontend.

## Composition Root

The ONLY place concrete implementations are wired:

```rust
// apps/api/src/state.rs
#[derive(Clone)]
pub struct AppState {
    pub pool: PgPool,
    pub config: AppConfig,
    pub users: Arc<dyn UserRepository>,     // ports as trait objects
    pub hasher: Arc<dyn PasswordHasher>,
    pub jwt: Arc<JwtTokenIssuer>,
}
// apps/api/src/main.rs:  config → pool → migrations → AppState::new() → router → serve
```

Config is typed and fail-fast — `AppConfig::from_env()` with `req()`/`opt()`
helpers; missing required vars abort startup, never default silently.

## Worker (background jobs)

Singleton election via Postgres advisory locks — exactly one replica runs each job:

```rust
#[async_trait]
pub trait ManagedWorker: Send + Sync + 'static {
    fn name(&self) -> &'static str;
    fn interval(&self) -> Duration;
    async fn tick(&self, pool: &PgPool) -> anyhow::Result<()>;
}
// harness: pg_try_advisory_lock(hash(name)) → tokio::select! { ticker | shutdown }
```

## New Entity Checklist (end-to-end)

For entity `project`, in dependency order:

1. `crates/domain/src/projects.rs` — `Project` entity, `ProjectId` newtype, value objects, invariants, unit tests; register in `lib.rs`
2. `crates/application/src/projects/ports.rs` — `ProjectRepository` trait
3. `crates/shared/src/projects.rs` — `ProjectDto`, `CreateProjectDto`, `UpdateProjectDto` (serde camelCase)
4. `crates/application/src/projects/use_cases.rs` — create/get/list/update/delete, each owning its transaction
5. `crates/application/src/projects/dto_map.rs` — `project_dto()`
6. `migrations/NNNN_projects.sql` — `CREATE TABLE IF NOT EXISTS`, indexes, constraints
7. `crates/infrastructure/src/persistence/project_repo.rs` — `ProjectRow` + `into_domain()` + `PgProjectRepository`
8. `apps/api/src/routes/projects.rs` — Axum handlers delegating to use cases; register router
9. `apps/api/src/state.rs` — wire `Arc<PgProjectRepository>`

## Tooling (non-negotiable)

```toml
# rust-toolchain.toml — pin the toolchain
[toolchain]
channel = "1.83.0"
components = ["clippy", "rustfmt"]

# workspace Cargo.toml — deny warnings, centralize versions
[workspace.lints.rust]
warnings = "deny"
[workspace.lints.clippy]
all = { level = "deny", priority = -1 }
[workspace.dependencies]   # single source of truth; members use { workspace = true }
```

- `#[allow(...)]` is FORBIDDEN in crate/app code — fix the issue, don't silence it.
- `justfile` recipes: `db` (compose up + migrate), `prepare` (sqlx offline cache),
  `check` (fmt --check, clippy -D warnings, test), `fmt`.
- CI: fmt → clippy → fresh-migrate against empty Postgres → test
  (see rust-quality-gates for the full chain).

## Forbidden Patterns

| Pattern | Why |
|---|---|
| `sqlx`/`axum` import in `domain` | Breaks layer purity — domain compiles without frameworks |
| Entity derives `Serialize`/`FromRow` | Domain leaks to wire/DB; use shared DTOs and private Rows |
| Repository trait in `infrastructure` | Inverts the inversion — ports belong to `application` |
| Transaction opened inside a repository | Use cases own transaction boundaries |
| Raw `Uuid`/`String` IDs across layers | Use newtype IDs (`UserId`) — the compiler catches mix-ups |
| `AppError::Internal` detail on the wire | Map to `Unknown`; log server-side |
| Business logic in Axum handlers | Handlers extract, call ONE use case, map the error |
| `#[allow(...)]` anywhere | No-allow policy; fix root cause |
| Pydantic/FastAPI idioms transplanted | This is Rust — see Language Separation in using-fullstack-agents |
