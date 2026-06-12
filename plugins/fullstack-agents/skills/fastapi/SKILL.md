---
name: fastapi
description: Generate production-ready FastAPI CRUD modules — SQLAlchemy model, Pydantic schemas, CRUD helpers, and routers following the simplified architecture. Use when creating or extending backend entities, models, or REST endpoints with SQLAlchemy and Pydantic. Do not use for Next.js frontend code (use nextjs or data-table).
---

# FastAPI Template Skill

Generate production-ready FastAPI CRUD modules following a simplified architecture with CRUD helpers.

## When to Use This Skill

Use this skill when asked to:
- Create a new FastAPI entity/module (router, CRUD helpers, schemas)
- Add CRUD endpoints to an existing FastAPI application
- Generate reusable query functions following the CRUD helper pattern
- Build REST APIs with SQLAlchemy and Pydantic

## Architecture Overview

```
Primary Pattern (most endpoints):
┌─────────────────────────────────────────────────────────────┐
│                    HTTP Request                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Router (api/routers/setting/{entity}_router.py)            │
│  • Endpoint definitions                                      │
│  • Request/Response validation                               │
│  • session: SessionDep                                       │
│  • Delegates to Service/Controller for most operations       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Service/Controller (api/services/ or api/controllers/)      │
│  • Business logic, validation, orchestration                 │
│  • External integrations (AD/LDAP, email, Redis, SMS)       │
│  • Cross-cutting concerns (audit, notifications)             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  CRUD Helper (api/crud/{entity}.py) — reusable queries       │
│  • Plain async functions (no classes)                        │
│  • Session as first parameter                                │
│  • flush() not commit()                                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Model (db/model.py) + Schemas                               │
│  • SQLModel ORM models                                       │
│  • api/schemas/ (domain) + api/http_schema/ (request/resp)   │
│  • Pydantic DTOs with CamelModel                             │
└─────────────────────────────────────────────────────────────┘

Secondary Pattern (simple entities like schedulers, OUs, domain-users):
┌─────────────────────────────────────────────────────────────┐
│  Router → CRUD helper / Direct queries → Model               │
│  Use only for simple entities with no business logic         │
└─────────────────────────────────────────────────────────────┘
```

## File Structure

```
api/
├── routers/
│   └── setting/
│       └── {entity}_router.py      # Router with endpoints
├── crud/
│   ├── __init__.py                  # Re-exports all CRUD helpers
│   └── {entity}.py                  # Reusable query functions (3+ uses)
├── services/
│   └── {entity}_service.py          # ONLY for external integrations
├── schemas/
│   ├── _base.py                     # CamelModel base class
│   └── {entity}_schema.py           # Domain schemas
└── http_schema/
    └── {entity}_schema.py           # Request/response Pydantic DTOs

db/
└── model.py                         # SQLModel ORM models

core/
├── dependencies.py                  # SessionDep, CurrentUserDep
├── app_setup/
│   └── routers_group/
│       └── setting_routers.py       # Router registration
└── exceptions.py                    # DetailedHTTPException
```

## Core Principles

### 1. Single Session Per Request

Every request uses exactly ONE database session via typed dependency:

```python
@router.post("/items")
async def create_item(
    item_create: ItemCreate,
    session: SessionDep,  # Typed dependency - NOT Depends(get_session)
):
    item = Item(**item_create.model_dump())
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item
```

### 2. Session Flow

```
Simple:
Endpoint (SessionDep) → Direct query OR CRUD helper → Database

Complex:
Endpoint (SessionDep) → Service (receives session) → CRUD helper → Database
```

### 3. CamelModel for API Responses

All schemas inherit from CamelModel for automatic snake_case to camelCase conversion:

```python
class ItemResponse(CamelModel):
    item_id: int        # Python: snake_case
    created_at: datetime
    # JSON output: {"itemId": 1, "createdAt": "..."}
```

### 4. Domain Exceptions

Use `DetailedHTTPException` for errors:

```python
from api.exceptions import DetailedHTTPException
from fastapi import status

raise DetailedHTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail=f"Item not found with ID: {item_id}",
)
```

## Generation Order

When creating a new entity, generate files in this order:

1. **Model** (`db/model.py`) - Add SQLModel model
2. **Schemas** (`api/schemas/{entity}_schema.py` + `api/http_schema/{entity}_schema.py`) - Pydantic DTOs
3. **CRUD helpers** (`api/crud/{entity}.py`) - Only if queries are reused 3+ times
4. **Router** (`api/routers/setting/{entity}_router.py`) - API endpoints
5. **Register router** in `core/app_setup/routers_group/setting_routers.py`

## Quick Reference

### CRUD Helper Pattern
- Plain async functions (no classes)
- Session as first parameter
- `flush()` not `commit()` - caller commits
- Only create when query is reused 3+ times
- Import as: `from api.crud import items as items_crud`

### Service/Controller Pattern (Primary)
- Most routers delegate to a Service or Controller class
- Business logic, validation, orchestration
- External integrations (AD, email, Redis, SMS)
- Uses CRUD helpers for database access (not repositories)
- Session passed as parameter

### Router Pattern
- Use `SessionDep` typed dependency
- Most routers delegate to Service/Controller
- Direct queries only for simple entities (schedulers, OUs, domain-users)
- Import CRUD helpers for reusable queries
- Path: `api/routers/setting/{entity}_router.py`
- Registration: `core/app_setup/routers_group/setting_routers.py`

## References

See the `references/` directory for detailed patterns:

### Core Patterns
- `model-pattern.md` - SQLAlchemy models
- `schema-pattern.md` - Pydantic DTO patterns
- `crud-helper-pattern.md` - Reusable query functions (replaces repository pattern)
- `service-pattern.md` - External integrations and complex orchestration
- `router-pattern.md` - API endpoints with SessionDep

### Advanced Patterns
- `file-upload-pattern.md` - File uploads with UploadFile, validation, S3
- `testing-pattern.md` - pytest fixtures, async tests, dependency overrides
- `response-types-pattern.md` - HTML, file downloads, streaming, redirects
- `middleware-pattern.md` - Security headers, correlation ID, timing, logging
- `form-data-pattern.md` - Form handling, OAuth2 password flow, headers, cookies
