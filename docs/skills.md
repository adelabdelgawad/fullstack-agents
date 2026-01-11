# Skills Reference

This document provides a complete reference for all 7 skill domains in the fullstack-agents plugin.

## Skills Overview

| Skill | Purpose |
|-------|---------|
| FastAPI | Backend API patterns and architecture |
| Next.js | Frontend patterns with React 19 |
| Data Table | TanStack Table with CRUD operations |
| Fetch Architecture | Client/server fetch utilities |
| Celery | Background task patterns |
| Tasks Management | APScheduler job patterns |
| Docker | Container infrastructure patterns |

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

### References

- `skills/fastapi/SKILL.md` - Complete skill overview
- `skills/fastapi/examples.md` - Usage examples
- `skills/fastapi/references/` - Detailed pattern documentation

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
