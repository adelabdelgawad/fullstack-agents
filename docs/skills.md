# Skills Reference

This document provides a complete reference for all 11 skill domains in the fullstack-agents plugin.

## Skills Overview

**Python lane**

| Skill | Purpose |
|-------|---------|
| FastAPI | Simplified backend pattern: model, schema, CRUD helpers, router |
| Python Clean Architecture | DDD for new microservices: pure domain, ports as Protocols, tx-owning use cases |
| Celery | Background task patterns |
| Tasks Management | APScheduler job patterns |

**Rust lane**

| Skill | Purpose |
|-------|---------|
| Rust Clean Architecture | Workspace-per-layer DDD: domain/application/infrastructure/shared + apps/api/worker |
| Rust Axum API | Axum 0.8 handlers, extractors, middleware, JWT auth, WebSocket |
| Rust SQLx | Compile-time-verified queries, migrations, offline cache, SQLSTATE mapping |
| Rust Correctness | Ownership, lifetimes, async Send/Sync hazards, panic-vs-Result |
| Rust Testing | Layer-mapped test pyramid: fakes, #[sqlx::test], tower oneshot |
| Rust Quality Gates | fmt / clippy-deny / audit / no-allow verification chain |
| Rust ↔ Next.js Contract | Wire parity with FastAPI — interchangeable backends |

**Frontend lane**

| Skill | Purpose |
|-------|---------|
| Next.js | Frontend patterns with React 19 |
| Data Table | TanStack Table with CRUD operations |
| Fetch Architecture | Client/server fetch utilities |

**Cross-cutting**

| Skill | Purpose |
|-------|---------|
| Using Fullstack Agents | Routing gate, language lanes, hard 5-step gate (auto-injected) |
| Codebase Scanning | Constitution + style profile detection before generation |
| Constitution | Per-project normative principles file (spec-kit compatible) |
| Senior Engineer | Architecture, modularity, duplication prevention on all work |
| Docker | Container infrastructure patterns |
| WebSocket | Real-time connection patterns |
| Batch Error Resolution | Disciplined batch error handling |
| Debug | Root-cause-first debugging discipline |

**Language lanes are strict:** Rust skills never apply to Python files and vice
versa. Lane detection (Cargo.toml vs pyproject.toml) routes per file/service.

---

## FastAPI Skill

Provides comprehensive patterns for FastAPI backend development.

### Architecture Pattern

```
app/
├── api/v1/endpoints/    # Routers (thin layer)
├── services/            # Business logic
├── repositories/        # Data access
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic schemas
└── core/                # Config, dependencies
```

### Key Patterns

#### Session Pattern (Critical)
```python
# Single session per request - passed through all layers
async def get_items(session: AsyncSession = Depends(get_session)):
    service = ItemService()
    return await service.get_all(session)

# Service receives session
async def get_all(self, session: AsyncSession):
    return await self.repository.get_all(session)

# Repository uses session
async def get_all(self, session: AsyncSession):
    result = await session.execute(select(Item))
    return result.scalars().all()
```

#### CamelModel Schema
```python
from app.core.schemas import CamelModel

class ItemCreate(CamelModel):
    name_en: str
    name_ar: str

# JSON: {"nameEn": "...", "nameAr": "..."}
```

#### Repository Pattern
```python
class ItemRepository:
    async def get_by_id(self, session: AsyncSession, id: int):
        return await session.get(Item, id)

    async def get_all(self, session: AsyncSession, skip: int = 0, limit: int = 100):
        result = await session.execute(
            select(Item).offset(skip).limit(limit)
        )
        return result.scalars().all()
```

### Pattern Files

**Core Patterns:**
- `model-pattern.md` - SQLAlchemy models
- `schema-pattern.md` - Pydantic DTO patterns
- `repository-pattern.md` - Data access layer
- `service-pattern.md` - Business logic layer
- `router-pattern.md` - API endpoints (PATCH, multiple responses)

**Advanced Patterns:**
- `file-upload-pattern.md` - File uploads with UploadFile, validation, S3
- `testing-pattern.md` - pytest fixtures, async tests, dependency overrides
- `response-types-pattern.md` - HTML, file downloads, streaming, redirects
- `middleware-pattern.md` - Security headers, correlation ID, timing, logging
- `form-data-pattern.md` - Form handling, OAuth2 password flow, headers, cookies

### References

- `skills/fastapi/SKILL.md` - Complete skill overview
- `skills/fastapi/examples.md` - Usage examples
- `skills/fastapi/references/` - All pattern documentation

---

## Next.js Skill

Provides patterns for Next.js 15+ with React 19.

### Architecture Pattern

```
app/
├── (routes)/            # Route groups
├── api/                 # API routes
├── components/          # Shared components
├── lib/                 # Utilities
└── types/               # TypeScript types
```

### Key Patterns

#### SSR + SWR Hybrid
```tsx
// page.tsx (Server Component)
export default async function ProductsPage() {
    const initialData = await fetchProducts();
    return <ProductsClient initialData={initialData} />;
}

// ProductsClient.tsx (Client Component)
"use client";
export function ProductsClient({ initialData }) {
    const { data } = useSWR('/api/products', fetcher, {
        fallbackData: initialData
    });
    return <ProductList products={data} />;
}
```

#### Server Actions
```tsx
"use server";

export async function createProduct(data: ProductCreate) {
    const response = await fetch(`${API_URL}/products`, {
        method: 'POST',
        body: JSON.stringify(data)
    });
    revalidatePath('/products');
    return response.json();
}
```

#### Type-Safe API Routes
```typescript
// app/api/products/route.ts
export async function GET() {
    const products = await backendFetch<Product[]>('/products');
    return NextResponse.json(products);
}

export async function POST(request: Request) {
    const data = await request.json();
    const product = await backendFetch<Product>('/products', {
        method: 'POST',
        body: JSON.stringify(data)
    });
    return NextResponse.json(product);
}
```

### References

- `skills/nextjs/SKILL.md` - Complete skill overview
- `skills/nextjs/examples.md` - Usage examples
- `skills/nextjs/references/` - Component patterns

---

## Data Table Skill

Provides patterns for TanStack Table with full CRUD operations.

### Architecture Pattern

```
app/{route}/
├── page.tsx                 # Server component
├── components/
│   ├── data-table.tsx       # Main table component
│   ├── columns.tsx          # Column definitions
│   ├── toolbar.tsx          # Filter/search toolbar
│   ├── row-actions.tsx      # Row action dropdown
│   └── dialogs/
│       ├── create-dialog.tsx
│       ├── edit-dialog.tsx
│       └── delete-dialog.tsx
└── types.ts
```

### Key Patterns

#### Column Definitions
```tsx
export const columns: ColumnDef<Product>[] = [
    {
        accessorKey: "name",
        header: ({ column }) => (
            <DataTableColumnHeader column={column} title="Name" />
        ),
    },
    {
        id: "actions",
        cell: ({ row }) => <RowActions row={row} />,
    },
];
```

#### URL State with nuqs
```tsx
import { useQueryState } from 'nuqs';

export function DataTable() {
    const [search, setSearch] = useQueryState('search');
    const [page, setPage] = useQueryState('page', parseAsInteger.withDefault(1));
    const [sort, setSort] = useQueryState('sort');
}
```

#### Server-Driven Updates
```tsx
// Never use optimistic updates
async function handleCreate(data: ProductCreate) {
    const result = await createProduct(data);
    // Use server response, not local state
    mutate('/api/products');
}
```

### References

- `skills/data-table/SKILL.md` - Complete skill overview
- `skills/data-table/examples.md` - Usage examples
- `skills/data-table/references/` - Component patterns

---

## Fetch Architecture Skill

Provides client and server-side fetch utilities.

### Architecture Pattern

```
lib/
├── fetch/
│   ├── client.ts        # Browser fetch with auth
│   ├── server.ts        # Server-side fetch
│   └── types.ts         # Shared types
```

### Key Patterns

#### Client Fetch
```typescript
// lib/fetch/client.ts
export async function clientFetch<T>(
    endpoint: string,
    options?: RequestInit
): Promise<T> {
    const response = await fetch(`/api${endpoint}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options?.headers,
        },
    });

    if (!response.ok) {
        throw new FetchError(response.status, await response.text());
    }

    return response.json();
}
```

#### Server Fetch
```typescript
// lib/fetch/server.ts
export async function serverFetch<T>(
    endpoint: string,
    options?: RequestInit
): Promise<T> {
    const response = await fetch(`${process.env.API_URL}${endpoint}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options?.headers,
        },
        cache: 'no-store',
    });

    if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
    }

    return response.json();
}
```

### References

- `skills/fetch-architecture/SKILL.md` - Complete skill overview
- `skills/fetch-architecture/examples.md` - Usage examples

---

## Celery Skill

Provides patterns for Celery background tasks.

### Architecture Pattern

```
app/
├── tasks/
│   ├── __init__.py      # Celery app
│   ├── email.py         # Email tasks
│   ├── reports.py       # Report generation
│   └── sync.py          # Data sync tasks
└── core/
    └── celery.py        # Celery configuration
```

### Key Patterns

#### Task Definition
```python
from app.core.celery import celery_app

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def send_email(self, to: str, subject: str, body: str):
    try:
        # Send email logic
        pass
    except Exception as exc:
        raise self.retry(exc=exc)
```

#### Task Invocation
```python
# Async call
send_email.delay("user@example.com", "Subject", "Body")

# With options
send_email.apply_async(
    args=["user@example.com", "Subject", "Body"],
    countdown=60,  # Delay 60 seconds
    expires=3600,  # Expire after 1 hour
)
```

### References

- `skills/celery/SKILL.md` - Complete skill overview
- `skills/celery/examples.md` - Usage examples

---

## Tasks Management Skill

Provides patterns for APScheduler recurring jobs.

### Architecture Pattern

```
app/
├── jobs/
│   ├── __init__.py      # Scheduler setup
│   ├── cleanup.py       # Cleanup jobs
│   ├── reports.py       # Report jobs
│   └── sync.py          # Sync jobs
└── core/
    └── scheduler.py     # APScheduler config
```

### Key Patterns

#### Job Definition
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job(
    CronTrigger(hour=0, minute=0),  # Daily at midnight
    id='cleanup_old_records',
    name='Cleanup old records'
)
async def cleanup_old_records():
    async with get_session() as session:
        await cleanup_service.delete_old_records(session)
```

#### Interval Jobs
```python
@scheduler.scheduled_job(
    'interval',
    minutes=30,
    id='sync_external_data'
)
async def sync_external_data():
    await sync_service.sync_all()
```

### References

- `skills/tasks-management/SKILL.md` - Complete skill overview
- `skills/tasks-management/examples.md` - Usage examples

---

## Docker Skill

Provides patterns for Docker container infrastructure.

### Architecture Pattern

```
├── docker-compose.yml           # Development
├── docker-compose.prod.yml      # Production
├── backend/
│   └── Dockerfile
├── frontend/
│   └── Dockerfile
├── nginx/
│   ├── Dockerfile
│   └── nginx.conf
└── scripts/
    └── docker-entrypoint.sh
```

### Key Patterns

#### Development Compose
```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://...
    depends_on:
      - db

  frontend:
    build: ./frontend
    volumes:
      - ./frontend:/app
    ports:
      - "3000:3000"

  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=app
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
```

#### Multi-Stage Dockerfile
```dockerfile
# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
```

### References

- `skills/docker/SKILL.md` - Complete skill overview
- `skills/docker/examples.md` - Usage examples
- `skills/docker/references/` - Service configurations

---

## Rust Lane Skills

Rust services follow clean architecture + DDD with crates as compiler-enforced
layers. No Leptos — Rust serves JSON APIs consumed by Next.js or other services.

```
crates/domain          entities, value objects, invariants — framework-free
crates/application     use cases (own transactions), repository ports, AppError
crates/infrastructure  SQLx adapters, config, JWT/Argon2, telemetry
crates/shared          wire DTOs (camelCase serde), pagination, wire errors
apps/api               Axum host: routers, middleware, composition root
apps/worker            advisory-lock singleton background jobs
```

Key rules: the four-stage error model (DomainError → RepoError → AppError →
wire error, internals never exposed), Axum 0.8 `{id}` path syntax (`:id`
panics at runtime), `#[allow(...)]` forbidden, warnings are errors, and every
frontend-exposed endpoint matches the FastAPI wire contract (camelCase JSON,
`limit`/`skip` pagination, `total` in list envelopes).

- `skills/rust-clean-architecture/SKILL.md` — layers, DDD building blocks, entity checklist
- `skills/rust-axum-api/SKILL.md` — handlers, extractors, middleware, auth
- `skills/rust-sqlx/SKILL.md` — queries, migrations, offline cache
- `skills/rust-correctness/SKILL.md` — language-level forbidden patterns
- `skills/rust-testing/SKILL.md` — test pyramid per layer
- `skills/rust-quality-gates/SKILL.md` — verification chain
- `skills/rust-nextjs-contract/SKILL.md` — wire-contract parity

---

## Python Clean Architecture Skill

DDD for NEW Python microservices, mirroring the Rust layer rules in Python
idiom: pure-dataclass domain (no Pydantic/SQLAlchemy imports), ports as
`Protocol`s, use cases owning `session.begin()`, four-stage errors mapped to
HTTP via exception handlers, CamelModel wire schemas. Existing
simplified-pattern services stay on the FastAPI skill — codebase-scanning
decides which applies.

- `skills/python-clean-architecture/SKILL.md` — complete skill

---

## Senior Engineer Skill

Cross-cutting discipline on ALL implementation work: search-before-implement
(with a concrete search recipe), never knowingly duplicate business logic,
functions < 50 lines / files < 800 lines / nesting ≤ 4,
dependencies point inward, leave touched code cleaner than found. Wired into
the hard gate (step 3: REUSE) and the agent lifecycle.

- `skills/senior-engineer/SKILL.md` — complete skill

---

## Constitution Skill

Creates and maintains a versioned, per-project principles file — NORMATIVE
intent, where codebase-scanning's profile is DESCRIPTIVE reality. Searched at
`.specify/memory/constitution.md` (spec-kit standard), repo root, then
`.claude/`. Precedence: constitution > codebase patterns > skill defaults.

- `skills/constitution/SKILL.md` — authoring guide + template

## Prompt Polish Skill

Refines a raw user instruction into a precise spec — intent, scope (breadth stated
explicitly), success criteria, constraints, output, and action-vs-advice — before
acting on it or delegating it to worker subagents. Grounds the rewrite in Claude
prompt-engineering best practices and Opus 4.x literal-instruction behavior. Always
in the loop via the `prompt-polish` UserPromptSubmit hook; scales to the request
(trivial prompts pass through, large/vague ones get full refinement).

- `skills/prompt-polish/SKILL.md` — refinement procedure + examples

## Fusion Panel Skill

Panel reasoning for high-stakes decisions, inspired by fusion-fable's "independence,
then synthesis": take several independent passes at the same question (blind to each
other), then synthesize consensus, contradictions, unique insights, and blind spots
into one grounded answer. Zero setup — parallel Claude subagents, no external CLIs
and no slash command. Reserve it for architecture choices, risky migrations,
security-sensitive changes, and stubborn bugs.

- `skills/fusion-panel/SKILL.md` — when to convene, procedure, synthesis structure
