---
name: rust-nextjs-contract
description: Wire-contract parity for Rust APIs serving the shared Next.js frontend — camelCase JSON matching CamelModel output, limit/skip pagination, search and is_active filters, list envelopes with total, Bearer auth, and route prefixes, so Rust and FastAPI services are interchangeable behind the same frontend. Use when exposing ANY Rust endpoint that Next.js (or the existing fetch-architecture) will consume. Do not use for service-to-service-only APIs with their own contract.
---

# Rust ↔ Next.js Wire Contract

The Next.js frontend (fetch-architecture + data-table skills) was built against
the FastAPI conventions. A Rust service MUST speak the exact same wire dialect —
the frontend must not know or care which language serves an endpoint.

**The contract source of truth is the existing FastAPI service.** Before
exposing a Rust endpoint, read one real FastAPI response for the equivalent
shape (or the frontend's `lib/types/api/*.ts`) and match it field-for-field.

## JSON Casing — camelCase, always

FastAPI's CamelModel emits camelCase. Rust DTOs in `crates/shared` mirror it:

```rust
#[derive(Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]      // MANDATORY on every wire DTO
pub struct UserDto {
    pub id: Uuid,
    pub name_en: String,                 // → "nameEn"  (bilingual pair)
    pub name_ar: String,                 // → "nameAr"
    pub is_active: bool,                 // → "isActive" (soft delete flag)
    pub created_at: DateTime<Utc>,       // → "createdAt" (audit fields)
    pub updated_at: Option<DateTime<Utc>>,
}
```

- Bilingual fields (`nameEn`/`nameAr`), soft delete (`isActive`), and audit
  fields (`createdAt`/`updatedAt`) follow the FastAPI model conventions when
  the entity exists on both sides.
- Dates: ISO-8601 strings with timezone (`chrono` serializes `DateTime<Utc>`
  correctly by default).
- IDs: serialize newtype IDs as their inner value
  (`#[serde(transparent)]` on newtypes, or map in `dto_map`).

## Pagination — limit/skip query params

The frontend sends `limit` and `skip` (it computes `skip = (page - 1) * limit`
from its `page`/`limit` URL params):

```rust
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListParams {
    #[serde(default = "default_limit")] pub limit: i64,    // default 10
    #[serde(default)] pub skip: i64,
    pub search: Option<String>,            // free-text search filter
    pub is_active: Option<bool>,           // status filter ("is_active" param)
}
```

List responses MUST carry the total row count (the frontend's pagination and
`totalCount` displays depend on it). Match the FastAPI envelope for the
equivalent endpoint exactly — typically items plus `total`:

```rust
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Page<T> {
    pub items: Vec<T>,
    pub total: i64,
}
```

If the existing FastAPI endpoint nests differently (e.g. entity-named key or a
`success/data/error` envelope), replicate THAT — verify, don't assume.

## Filters

- `search` — case-insensitive match over the entity's display fields
  (`ILIKE '%' || $n || '%'` across `name_en`, `name_ar`, etc. — same fields
  the FastAPI service searches).
- `is_active` — tri-state: absent = all, `true`/`false` = filtered.
- Filter param NAMES stay snake_case in the query string (`is_active`, not
  `isActive`) — that is what the frontend sends today; only JSON BODIES are
  camelCase.

## Auth & Headers

- `Authorization: Bearer <token>` — the frontend's `backendFetch`/
  `directBackendFetch` attach it; the Rust JWT middleware must accept the SAME
  tokens (same secret/issuer/audience or shared JWKS) as the FastAPI services.
- CSRF: mutations receive the CSRF header the frontend forwards — validate it
  the same way the FastAPI side does, or exempt Bearer-authenticated routes
  consistently across BOTH backends (never one behavior per language).
- 401 (not authenticated) vs 403 (not authorized) must match FastAPI behavior —
  the frontend's pre-emptive token refresh keys off 401.

## Routes & Mounting

The frontend prefixes `/backend/...` and the proxy strips it; backends mount
the SAME logical paths FastAPI uses (`/setting/{entity}`,
`/management/{entity}`, ...). REST shape parity:

| Operation | Method + path | Status |
|---|---|---|
| List | `GET /setting/products` (limit/skip/search/is_active) | 200 |
| Get | `GET /setting/products/{id}` | 200 / 404 |
| Create | `POST /setting/products` | 201 |
| Update | `PUT /setting/products/{id}` | 200 |
| Delete (soft) | `DELETE /setting/products/{id}` | 200/204 — match FastAPI |

Error bodies follow the wire error enum mapped from `AppError`
(rust-clean-architecture) with the SAME status mapping FastAPI uses:
422 validation, 404 not found, 409 conflict, 401/403 auth.

## Type Bindings (recommended)

Derive `specta::Type` on shared DTOs and export TypeScript bindings from a test
(`crates/shared/tests/export_bindings.rs` → `dist/bindings.d.ts`). The Next.js
app imports the generated types instead of hand-writing `lib/types/api/*.ts`
for Rust-served entities — drift becomes a CI failure, not a runtime bug.

## Verification Checklist (per endpoint)

- [ ] JSON keys camelCase; query param names snake_case
- [ ] List response carries `total` and matches the FastAPI envelope verbatim
- [ ] `limit`/`skip` honored with the same defaults as FastAPI
- [ ] `search` and `is_active` filter the same fields/semantics
- [ ] Same status codes per operation and per error class
- [ ] Bearer token from the shared issuer validates
- [ ] Compared against a REAL FastAPI response or the frontend types, not memory
