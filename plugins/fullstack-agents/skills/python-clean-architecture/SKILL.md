---
name: python-clean-architecture
description: Clean Architecture + DDD for Python (FastAPI) microservices — pure domain layer with value objects and entities, application use cases owning transactions, repository ports as Protocols, SQLAlchemy adapters in infrastructure, and a four-stage error model. Use when creating or structuring a NEW Python microservice or applying DDD to Python. Do not use for the existing simplified FastAPI pattern (use fastapi — codebase-scanning decides which applies) and never for Rust services (use rust-clean-architecture).
---

# Python Clean Architecture + DDD

Clean Architecture for FastAPI microservices, mirroring the same layer rules as
rust-clean-architecture so polyglot services stay conceptually identical. Python
has no compiler-enforced crate boundaries — discipline plus import-linting
substitute for them.

**Scope boundary:** existing services built on the simplified pattern
(routers → CRUD helpers, detected by codebase-scanning) stay on the `fastapi`
skill. THIS skill is for new microservices where DDD pays for itself.

## Service Layout

```
my-service/
├── pyproject.toml
├── migrations/                  # alembic, single timeline
└── src/
    ├── domain/                  # entities, value objects, DomainError — PURE
    │   ├── shared.py            # DomainError, common value objects
    │   └── identity/            #   feature-first inside layers
    │       ├── user.py          #   entity + invariants
    │       └── value_objects.py #   Email, Username, UserId
    ├── application/             # use cases, ports, DTO mapping, AppError
    │   ├── errors.py            # RepoError, AppError
    │   └── identity/
    │       ├── ports.py         # Protocols (repository interfaces)
    │       ├── use_cases.py     # transaction-owning orchestration
    │       └── dto_map.py       # entity → DTO functions
    ├── infrastructure/          # SQLAlchemy repos, config, security, clients
    │   ├── config.py            # pydantic-settings, fail-fast
    │   └── persistence/
    │       ├── models.py        # SQLAlchemy ORM rows (NEVER exposed)
    │       └── user_repo.py     # port implementations
    ├── presentation/            # FastAPI routers + DI wiring
    │   ├── deps.py              # composition root (Depends providers)
    │   ├── errors.py            # AppError → HTTPException handlers
    │   └── routers/
    └── schemas/                 # wire DTOs — CamelModel (camelCase JSON)
```

## Layer Rules

| Layer | Contains | FORBIDDEN imports |
|---|---|---|
| `domain` | Entities, value objects, invariants, `DomainError` | fastapi, sqlalchemy, pydantic, redis — anything framework |
| `application` | Use cases, ports (Protocols), DTO mapping, `AppError` | fastapi, infrastructure, raw SQL. Allowed: `AsyncSession` TYPE for transaction control |
| `infrastructure` | SQLAlchemy models + repos, config, hashing/JWT, external clients | fastapi routers, presentation |
| `schemas` | CamelModel wire DTOs | domain, application, infrastructure |
| `presentation` | Routers, dependency providers, exception handlers | business logic (delegate to use cases) |

Dependencies point inward: `presentation → application → domain`;
`infrastructure → application + domain` (implements ports). Enforce with
import-linter contracts or ruff's banned-imports per package when available.

## DDD Building Blocks

Value objects parse, don't validate — frozen dataclasses with fallible constructors:

```python
# src/domain/identity/value_objects.py
@dataclass(frozen=True, slots=True)
class Email:
    value: str

    @classmethod
    def parse(cls, raw: str) -> "Email":
        normalized = raw.strip().lower()
        local, _, domain = normalized.partition("@")
        if not local or "." not in domain or len(normalized) > 254:
            raise DomainError(f"invalid email: {raw}")
        return cls(normalized)

    @classmethod
    def from_trusted(cls, value: str) -> "Email":   # rehydration only
        return cls(value)


@dataclass(frozen=True, slots=True)
class UserId:                                       # newtype — no raw UUIDs across layers
    value: UUID

    @classmethod
    def generate(cls) -> "UserId":
        return cls(uuid4())
```

Entities enforce invariants and expose intent-named behavior:

```python
# src/domain/identity/user.py
@dataclass(slots=True)
class User:
    id: UserId
    username: Username
    email: Email
    password_hash: str
    is_active: bool
    created_at: datetime
    updated_at: datetime | None

    @classmethod
    def create(cls, username: Username, email: Email,
               password_hash: str, now: datetime) -> "User":
        return cls(id=UserId.generate(), username=username, email=email,
                   password_hash=password_hash, is_active=True,
                   created_at=now, updated_at=None)

    def can_login(self) -> bool:
        return self.is_active
```

No Pydantic in domain — Pydantic belongs to the wire (`schemas/`) and config.

## Ports as Protocols

```python
# src/application/identity/ports.py
class UserRepository(Protocol):
    async def insert(self, session: AsyncSession, user: User) -> None: ...
    async def find_by_id(self, session: AsyncSession, user_id: UserId) -> User | None: ...
    async def list(self, session: AsyncSession, params: PageParams) -> tuple[list[User], int]: ...
```

Adapters in infrastructure map ORM rows to domain (rows are private):

```python
# src/infrastructure/persistence/user_repo.py
class PgUserRepository:
    async def find_by_id(self, session: AsyncSession, user_id: UserId) -> User | None:
        row = await session.get(UserModel, user_id.value)
        return _into_domain(row) if row else None

def _into_domain(row: UserModel) -> User:
    return User(id=UserId(row.id), username=Username.from_trusted(row.username),
                email=Email.from_trusted(row.email), password_hash=row.password_hash,
                is_active=row.is_active, created_at=row.created_at,
                updated_at=row.updated_at)
```

## Use Cases Own Transactions

```python
# src/application/identity/use_cases.py
async def create_user(session_factory: async_sessionmaker[AsyncSession],
                      users: UserRepository, hasher: PasswordHasher,
                      data: CreateUserInput) -> UserOutput:
    username = Username.parse(data.username)        # parse, don't validate
    email = Email.parse(data.email)
    if len(data.password) < MIN_PASSWORD_LEN:
        raise AppValidationError(f"password must be at least {MIN_PASSWORD_LEN} characters")

    user = User.create(username, email, hasher.hash(data.password), utc_now())

    async with session_factory() as session:        # use case owns the tx
        async with session.begin():
            try:
                await users.insert(session, user)
            except IntegrityError as exc:
                raise AppConflictError("username or email taken") from exc

    return user_output(user)                        # DTO out, never the entity
```

## Four-Stage Error Model

Same shape as Rust — internals never reach the wire:

```python
class DomainError(Exception): ...                   # 1. domain — business failures

class RepoError(Exception): ...                     # 2. persistence (NotFound,
class RepoConflictError(RepoError): ...             #    Conflict via IntegrityError)

class AppError(Exception): ...                      # 3. canonical app errors
class AppValidationError(AppError): ...
class AppConflictError(AppError): ...
class AppNotFoundError(AppError): ...
class AppUnauthorizedError(AppError): ...

# 4. wire — FastAPI exception handlers map AppError → HTTP + CamelModel body
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    status, payload = WIRE_MAP[type(exc)]           # Internal → 500 + "Unknown",
    logger.error("app error", exc_info=exc)         # detail logged, never sent
    return JSONResponse(status_code=status, content=payload)
```

HTTP mapping: Validation/Domain → 422, NotFound → 404, Conflict → 409,
Unauthorized → 401, Forbidden → 403, everything else → 500 with detail hidden.

## Composition Root

Wiring happens ONLY in `presentation/deps.py`:

```python
def get_user_repository() -> UserRepository:
    return PgUserRepository()

UsersDep = Annotated[UserRepository, Depends(get_user_repository)]

# Router — thin: extract, call ONE use case, return DTO
@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user_endpoint(payload: CreateUserRequest,
                               users: UsersDep, hasher: HasherDep) -> UserResponse:
    result = await create_user(session_factory, users, hasher, payload.to_input())
    return UserResponse.from_output(result)
```

Wire schemas are CamelModel (camelCase JSON) — the Next.js contract is identical
whether the service is Python or Rust (see rust-nextjs-contract for the shared
contract definition).

Config: pydantic-settings with required fields and NO silent defaults for
secrets — missing `DATABASE_URL`/`JWT_SECRET` aborts startup.

## Testing (mirrors rust-testing)

| Level | Scope | Tool |
|---|---|---|
| Unit (domain) | entities, VOs, invariants | pytest, no fixtures needed |
| Unit (application) | use cases with in-memory fakes | pytest-asyncio, hand fakes |
| Integration (repo) | real SQL | pytest + testcontainers/transactional fixtures |
| Integration (HTTP) | routers + handlers | httpx AsyncClient |

Ports as Protocols make fakes trivial — no mock library needed for most tests.

## Forbidden Patterns

| Pattern | Why |
|---|---|
| `fastapi`/`sqlalchemy`/`pydantic` import in domain | Domain stays framework-free |
| Pydantic models as domain entities | Wire shape ≠ business model; use dataclasses |
| ORM models exposed in responses | Map row → domain → DTO |
| Transaction opened in a repository | Use cases own transactions |
| Business logic in routers | Extract → one use case → map |
| Raw UUID/str IDs across layers | Newtype value objects |
| `except Exception: pass` | Four-stage model — every error has a mapped stage |
| thiserror/axum idioms transplanted | This is Python — see Language Separation |
