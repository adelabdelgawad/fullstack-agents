---
name: backend-migration-from-frontend
description: Migrate a backend to a new framework by reverse-engineering behavior from the frontend — trace every UI request down through router, controller, middleware, service, repository, DB, jobs, events, and side effects, then reproduce equivalent behavior (validation, permissions, transactions, responses, status codes, logging, caching, events) in the target. Use when porting/rewriting a backend and behavioral equivalence with the existing app matters. Do not use for greenfield backends (use fastapi / python-clean-architecture / rust-clean-architecture) or pure frontend migrations (use frontend-transformation).
---

# Backend Migration Driven by Frontend Analysis

## Objective

**The frontend is the source of truth.** Every backend implementation must be
derived by understanding how the frontend actually behaves.

Do NOT rewrite the backend endpoint-by-endpoint. Instead, reverse-engineer the
entire application behavior starting from the UI. Implementation begins only
after the original backend behavior is fully understood.

**Behavioral equivalence is more important than framework equivalence.**

**This skill is RIGID.** Investigation precedes implementation; the validation
and completion criteria are non-negotiable.

## When to Use This Skill

Use this skill when asked to:
- Port / rewrite / migrate a backend to another framework or language
- Reproduce an existing API's behavior in a new stack (e.g. Express → FastAPI,
  Django → Axum) while keeping the frontend working unchanged
- Reconstruct backend behavior from an app whose UI is the reliable reference

Do **not** use it for greenfield backends (use `fastapi`,
`python-clean-architecture`, or `rust-clean-architecture`) or for pure frontend
migrations (use `frontend-transformation`).

## How This Fits the Plugin

- **Pick the target lane first.** The *new* backend is written using the
  plugin's lane skills: Python → `fastapi` or `python-clean-architecture`;
  Rust → `rust-clean-architecture` + `rust-axum-api` + `rust-sqlx`. This skill
  governs *what behavior to reproduce*; the lane skills govern *how to write it*.
- **Preserve the wire contract.** Any endpoint the Next.js frontend consumes must
  keep camelCase JSON, `limit`/`skip` pagination, and `total` list envelopes —
  see `rust-nextjs-contract`. The frontend adapts to nothing.
- **Scan and reuse.** Run `codebase-scanning` on the target; apply the
  `senior-engineer` discipline — but never drop original behavior in the name of
  a cleaner design.

## Investigation Phase

For every frontend page, identify every: API request · websocket connection ·
upload · download · polling request · realtime subscription · authentication
request.

For every request, locate the backend endpoint — and do NOT stop there.

## Recursive Backend Discovery

Starting from the endpoint, recursively trace execution until every executed
path is understood:

```
Frontend → HTTP Request → Router → Controller → Middleware → Authentication →
Authorization → Validation → Service → Domain Services → Repositories →
Database → External Services → Background Jobs → Events → Notifications →
Logging → Caching → Response
```

**Never stop after locating the controller.** Continue tracing until every path
is understood.

## Build a Complete Mental Model

Before implementing anything, identify: business rules · validation rules ·
permission rules · role restrictions · ownership checks · transactions ·
concurrency handling · database constraints · error handling · retry logic ·
caching · Redis usage · events · message queues · notifications · audit logs ·
file storage · external integrations · feature flags · configuration · scheduled
jobs · side effects — everything executed directly or indirectly.

## Never Guess

If a function calls another helper: **open it.** If that helper calls another
helper: **open it.** Repeat until behavior is completely understood.

Never assume. Never infer. Never approximate.

## Cross References

Trace the full chain that affects each request:

```
Frontend → Backend → Database → Shared DTOs → Shared Models → Enums →
Constants → Configuration → Permissions → Utilities → Middleware
```

Everything affecting the request must be understood.

## Migration Rules

Only after understanding the original implementation should the new backend be
written. It must preserve: business behavior · validation · permissions ·
transactions · error responses · logging · caching · events · performance
characteristics · response formats · status codes · pagination · filtering ·
sorting · search behavior · side effects.

**Framework translation only.** Translate framework-specific concepts; do NOT
redesign architecture unless explicitly requested. Preserve business logic
exactly.

## Missing Logic Policy

Never ignore logic because it appears unrelated. All side effects must be
preserved — including: audit logging · cache invalidation · email sending ·
realtime notifications · metrics · analytics · permissions · rate limiting ·
feature flags · background jobs.

## Validation Before Completion

For every frontend request, verify all of:

✓ Request payload matches · validation matches
✓ Authentication matches · authorization matches
✓ Database behavior matches · response payload matches
✓ Status codes match · side effects match · error responses match
✓ Logging matches · notifications matches · events match
✓ Background processing matches

## Completion Criteria

The migration is NOT complete because the API compiles. It is complete only when
**every frontend interaction produces behavior equivalent to the original
application.**

Never declare success until every frontend feature has been verified against the
original implementation.
