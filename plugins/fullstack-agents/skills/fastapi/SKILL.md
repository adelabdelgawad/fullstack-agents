# FastAPI Template Skill

Generate production-ready FastAPI CRUD modules following a proven single-session-per-request architecture.

## When to Use This Skill

Use this skill when asked to:
- Create a new FastAPI entity/module (router, service, repository, schemas)
- Add CRUD endpoints to an existing FastAPI application
- Generate data access layers following the repository pattern
- Build REST APIs with SQLAlchemy and Pydantic

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    HTTP Request                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Router (api/v1/{entity}.py)                                │
│  • Endpoint definitions                                      │
│  • Request/Response validation                               │
│  • session: AsyncSession = Depends(get_session)             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Service (api/services/{entity}_service.py)                 │
│  • Business logic                                            │
│  • Validation rules                                          │
│  • Orchestrates repositories                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Repository (api/repositories/{entity}_repository.py)       │
│  • Data access                                               │
│  • SQLAlchemy queries                                        │
│  • No business logic                                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Model (db/models.py) + Schema (api/schemas/{entity}.py)    │
│  • SQLAlchemy ORM models                                     │
│  • Pydantic DTOs with CamelModel                            │
└─────────────────────────────────────────────────────────────┘
```

## File Structure

```
api/
├── v1/
│   └── {entity}.py              # Router with endpoints
├── services/
│   └── {entity}_service.py      # Business logic
├── repositories/
│   └── {entity}_repository.py   # Data access layer
└── schemas/
    ├── _base.py                 # CamelModel base class
    └── {entity}_schemas.py      # Pydantic DTOs

db/
└── models.py                    # SQLAlchemy models

core/
├── exceptions.py                # Domain exceptions
└── pagination.py                # Pagination utilities
```

## Core Principles

### 1. Single Session Per Request

Every request uses exactly ONE database session:

```python
@router.post("/items")
async def create_item(
    item_create: ItemCreate,
    session: AsyncSession = Depends(get_session),  # Session injected here
):
    service = ItemService()
    return await service.create_item(session, item_create)  # Passed to service
```

### 2. Session Flow

```
Endpoint (session created)
    → Service (receives session as param)
        → Repository (receives session as param)
            → Database operations
```

### 3. CamelModel for API Responses

All schemas inherit from CamelModel for automatic snake_case → camelCase conversion:

```python
class ItemResponse(CamelModel):
    item_id: int        # Python: snake_case
    created_at: datetime
    # JSON output: {"itemId": 1, "createdAt": "..."}
```

### 4. Domain Exceptions

Use typed exceptions that map to HTTP status codes:

| Exception | HTTP Status |
|-----------|-------------|
| NotFoundError | 404 |
| ConflictError | 409 |
| ValidationError | 422 |
| AuthenticationError | 401 |
| AuthorizationError | 403 |
| DatabaseError | 500 |

## Generation Order

When creating a new entity, generate files in this order:

1. **Model** (db/models.py) - Add SQLAlchemy model
2. **Schemas** (api/schemas/{entity}_schemas.py) - Pydantic DTOs
3. **Repository** (api/repositories/{entity}_repository.py) - Data access
4. **Service** (api/services/{entity}_service.py) - Business logic
5. **Router** (api/v1/{entity}.py) - API endpoints
6. **Register router** in app.py

## Quick Reference

### Repository Pattern
- `__init__` takes no parameters
- All methods receive `session` as first parameter
- Use `session.flush()` to persist, `session.refresh()` to reload

### Service Pattern
- `__init__` creates repository instances
- All methods receive `session` as first parameter
- Contains business validation logic

### Router Pattern
- Always include `session: AsyncSession = Depends(get_session)`
- Instantiate service directly: `service = EntityService()`
- Pass session to service methods

## References

See the `references/` directory for detailed patterns:
- `schema-pattern.md` - Pydantic DTO patterns
- `repository-pattern.md` - Data access layer
- `service-pattern.md` - Business logic layer
- `router-pattern.md` - API endpoints
- `model-pattern.md` - SQLAlchemy models
