---
name: rust-axum-api
description: Axum 0.8 API patterns — curly-brace path syntax, extractor ordering, State via FromRef, IntoResponse error mapping, Tower middleware ordering, JWT auth middleware, WebSocket, and graceful shutdown. Use when writing or reviewing Axum handlers, routers, middleware, or HTTP-layer code in a Rust service. Do not use for FastAPI/Python endpoints (use fastapi or python-clean-architecture) or for business logic (handlers delegate to use cases — see rust-clean-architecture).
---

# Axum 0.8 API Patterns

The HTTP layer of a Rust service. Handlers are THIN: extract, call one use
case, map the result. Business logic lives in `application` (see
rust-clean-architecture).

## Path Syntax — Axum 0.8 CRITICAL

```rust
Router::new()
    .route("/users/{id}", get(get_user))          // {id} — Axum 0.8+
    .route("/files/{*path}", get(serve_file))     // wildcard
// .route("/users/:id", ...)                      // FORBIDDEN: panics AT RUNTIME
```

`:id` does not fail at compile time — it panics when the router is built.
This is the #1 Axum migration foot-gun. Always `{name}`.

## Extractor Ordering

Extractors implementing `FromRequestParts` (State, Path, Query, headers) can go
in any position. Body-consuming extractors (`Json`, `Form`, `Bytes`, `String`)
must be LAST — there is only one body.

```rust
async fn create_user(
    State(state): State<AppState>,       // app state — any position
    Path(id): Path<Uuid>,                // params — any position
    Json(payload): Json<CreateUserDto>,  // body consumer — ALWAYS LAST
) -> Result<Json<UserDto>, ApiFailure> {
    let dto = application::identity::use_cases::create_user(
        &state.pool, state.users.as_ref(), state.hasher.as_ref(), payload,
    ).await?;
    Ok(Json(dto))
}
```

- `State<T>` for application state (pools, ports, config) — composes via `FromRef`
  for sub-states. `Extension<T>` ONLY for per-request data injected by middleware
  (e.g. authenticated `Claims`). Never `Extension` for app state.
- `TypedHeader` lives in `axum-extra`, not `axum`.

## Error Mapping (IntoResponse)

One newtype wraps `AppError` at the HTTP boundary:

```rust
// apps/api/src/error.rs
pub struct ApiFailure(pub AppError);
impl From<AppError> for ApiFailure { fn from(e: AppError) -> Self { Self(e) } }

impl IntoResponse for ApiFailure {
    fn into_response(self) -> Response {
        let status = match &self.0 {
            AppError::NotFound => StatusCode::NOT_FOUND,
            AppError::Validation(_) | AppError::Domain(_) => StatusCode::UNPROCESSABLE_ENTITY,
            AppError::Conflict(_) => StatusCode::CONFLICT,
            AppError::Unauthorized => StatusCode::UNAUTHORIZED,
            AppError::Forbidden => StatusCode::FORBIDDEN,
            AppError::Internal(detail) => {
                tracing::error!(%detail, "internal error");   // log detail
                StatusCode::INTERNAL_SERVER_ERROR             // hide detail
            }
        };
        (status, Json(shared::ApiError::from(self.0))).into_response()
    }
}
```

Never `unwrap()`/`expect()` in handlers — `?` with `ApiFailure`. Never leak
`sqlx::Error` or internal messages in responses.

## Middleware

```rust
let app = Router::new()
    .route("/users/{id}", get(get_user))
    .route_layer(middleware::from_fn_with_state(state.clone(), require_auth))
    .route("/healthz", get(|| async { "ok" }))            // outside auth
    .layer(ServiceBuilder::new()
        .layer(TraceLayer::new_for_http())
        .layer(TimeoutLayer::new(Duration::from_secs(30)))
        .layer(CompressionLayer::new()))
    .with_state(state);
```

- `route_layer` applies only to routes registered SO FAR (unmatched paths still
  404 without running it); `layer` wraps everything including fallback. Auth
  goes on `route_layer` of protected routes; tracing/timeout on outer `layer`.
- `ServiceBuilder` order: first listed = outermost.
- Never block in middleware — `spawn_blocking` for CPU-bound work.

### JWT auth middleware (cookie or bearer)

```rust
pub async fn require_auth(
    State(state): State<AppState>,
    mut req: Request, next: Next,
) -> Result<Response, ApiFailure> {
    let token = extract_token(&req).ok_or(AppError::Unauthorized)?;
    let claims = state.jwt.verify(&token)?;        // AppError::Unauthorized on fail
    req.extensions_mut().insert(claims);           // Extension<Claims> downstream
    Ok(next.run(req).await)
}
```

Claims carry identity only (`sub`, `jti`, `exp`, `iat`, `iss`, `aud`) — never
roles or business fields; authorization is resolved server-side per request.

## WebSocket

```rust
async fn ws_handler(ws: WebSocketUpgrade, State(state): State<AppState>) -> Response {
    ws.on_upgrade(|socket| handle_socket(socket, state))
}
```

- Rooms via `tokio::sync::broadcast` channels.
- Heartbeat: server pings on an interval; drop the connection on missed pongs.
- Handle `Message::Close` explicitly — never ignore close frames.

## Graceful Shutdown

```rust
axum::serve(listener, app.into_make_service())
    .with_graceful_shutdown(async { tokio::signal::ctrl_c().await.ok(); })
    .await?;
```

## Forbidden Patterns

| Pattern | Why |
|---|---|
| `:id` path syntax | Runtime panic in Axum 0.8 — use `{id}` |
| Body extractor not last | Compiles in some orders, breaks — keep `Json`/`Form` last |
| `Extension` for app state | `State` + `FromRef` is type-checked at router build |
| `unwrap`/`expect` in handlers | Propagate with `?` into `ApiFailure` |
| Business logic in handlers | Extract → one use case → map; nothing else |
| `sqlx::Error` in response types | Map through `RepoError → AppError → ApiError` |
| Blocking calls in handlers/middleware | `tokio::task::spawn_blocking` |
| Missing WebSocket heartbeat | Proxies kill idle connections silently |
