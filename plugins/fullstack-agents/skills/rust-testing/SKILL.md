---
name: rust-testing
description: Testing strategy for Rust clean-architecture services — domain unit tests, use-case tests with hand-rolled fakes, repository integration tests with #[sqlx::test], HTTP tests with tower oneshot, and TDD flow. Use when writing or fixing Rust tests or setting up test infrastructure. Do not use for pytest/Python testing.
---

# Rust Testing

Test pyramid mapped to the clean-architecture layers. Each layer tests at the
cheapest level that proves its contract.

| Level | Scope | Tool | Location |
|---|---|---|---|
| Unit (domain) | Entities, value objects, invariants | `#[test]` | `crates/domain/src/**` in `#[cfg(test)] mod tests` |
| Unit (application) | Use-case orchestration with fakes | `#[tokio::test]` + hand fakes/mockall | `crates/application/src/**` |
| Integration (repository) | Real SQL vs live Postgres | `#[sqlx::test]` | `crates/infrastructure/tests/` |
| Integration (HTTP) | Router + handler + middleware | `tower::ServiceExt::oneshot` | `apps/api/tests/` |
| E2E | Critical flows | Playwright (via Next.js frontend) | `e2e/` |

## Domain Unit Tests (cheapest, most numerous)

Pure functions — no async, no mocks, no IO. Fixed timestamps for determinism:

```rust
#[cfg(test)]
mod tests {
    use super::*;
    fn ts() -> DateTime<Utc> { DateTime::from_timestamp(1_700_000_000, 0).expect("valid") }

    #[test]
    fn create_rejects_empty_title() {
        let err = Note::create(UserId::generate(), "   ", "body", ts()).unwrap_err();
        assert!(matches!(err, DomainError::Validation(_)));
    }

    #[test]
    fn edit_updates_timestamp() {
        let mut note = Note::create(UserId::generate(), "first", "b", ts()).expect("valid");
        note.edit("second", "b2", ts()).expect("valid");
        assert_eq!(note.updated_at, Some(ts()));
    }
}
```

Every value object's `parse()` gets reject + accept + boundary cases.

## Use-Case Tests with Fakes

Ports are traits — fake them in-memory; no database needed:

```rust
struct FakeUserRepo(Mutex<Vec<User>>);

#[async_trait]
impl UserRepository for FakeUserRepo {
    async fn insert(&self, _conn: &mut PgConnection, user: &User) -> Result<(), RepoError> {
        let mut users = self.0.lock().expect("test lock");
        if users.iter().any(|u| u.email.as_str() == user.email.as_str()) {
            return Err(RepoError::UniqueViolation("email".into()));
        }
        users.push(user.clone());
        Ok(())
    }
    // ...
}

#[tokio::test]
async fn create_user_rejects_short_password() {
    // Arrange / Act / Assert — validation fails before any port is touched
    let result = create_user(&pool_stub(), &FakeUserRepo::default(),
                             &FakeHasher, short_password_input()).await;
    assert!(matches!(result, Err(AppError::Validation(_))));
}
```

Hand-rolled fakes over mockall by default — simpler, no macro magic; mockall
when you must assert call sequences.

## Repository Integration Tests

`#[sqlx::test]` provisions an isolated database per test and rolls back:

```rust
#[sqlx::test(migrations = "../../migrations")]
async fn insert_then_find_roundtrips(pool: PgPool) -> sqlx::Result<()> {
    let repo = PgUserRepository;
    let user = valid_user();
    let mut conn = pool.acquire().await?;
    repo.insert(&mut conn, &user).await.expect("insert");
    let found = repo.find_by_id(&mut conn, user.id).await.expect("find");
    assert_eq!(found.expect("present").email.as_str(), user.email.as_str());
    Ok(())
}
```

Test the SQLSTATE mapping explicitly: duplicate insert →
`RepoError::UniqueViolation`.

## HTTP Tests (tower oneshot)

```rust
#[tokio::test]
async fn missing_token_returns_401() {
    let app = build_router(test_state());
    let res = app.oneshot(
        Request::get("/users/00000000-0000-0000-0000-000000000000")
            .body(Body::empty()).expect("request"),
    ).await.expect("response");
    assert_eq!(res.status(), StatusCode::UNAUTHORIZED);
}
```

Cover: auth rejection, validation → 422 with wire-safe body, not-found → 404,
conflict → 409, and that internal errors NEVER leak detail.

## TDD Flow

1. RED — write the failing test at the cheapest layer that captures the behavior
2. GREEN — minimal implementation
3. IMPROVE — refactor with the test as the safety net
4. Coverage target: 80%+ (cargo-llvm-cov), domain near 100%

## Conventions

- AAA structure (Arrange / Act / Assert) with blank-line separation.
- Names state behavior: `fn create_rejects_empty_title()`, not `fn test_create()`.
- `expect("why")` in tests, never bare `unwrap()` — failures should read well.
- No sleeps; no real clocks (inject timestamps); no network in unit tests.
- One behavior per test.
