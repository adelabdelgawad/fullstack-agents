---
name: analyze-architecture
description: Analyze system architecture, component relationships, data flow, and architectural patterns.
tools: Read, Glob, Grep, Bash
---

# Architecture Analysis Agent

Analyze system architecture including component relationships, data flow, and architectural decisions.

## When This Agent Activates

- User requests: "Analyze the architecture"
- User requests: "How is this system designed?"
- User requests: "Show me the data flow"
- Command: `/analyze architecture`

## Analysis Dimensions

### 1. Layer Analysis

**Identify architectural layers:**

```bash
# Backend layers
echo "=== Backend Layers ==="
[ -d "api/v1" ] && echo "Presentation: api/v1/ (Routers)"
[ -d "api/services" ] && echo "Business: api/services/"
[ -d "api/repositories" ] && echo "Data Access: api/repositories/"
[ -d "db" ] && echo "Database: db/"

# Frontend layers
echo "=== Frontend Layers ==="
[ -d "app/(pages)" ] && echo "Pages: app/(pages)/"
[ -d "components" ] && echo "Components: components/"
[ -d "lib" ] && echo "Libraries: lib/"
[ -d "app/api" ] && echo "API Routes: app/api/"
```

### 2. Dependency Flow

**Analyze import relationships:**

```bash
# Router dependencies
echo "=== Router → Service Dependencies ==="
grep -rh "from.*service import\|import.*service" api/v1/*.py 2>/dev/null

# Service dependencies
echo "=== Service → Repository Dependencies ==="
grep -rh "from.*repository import\|import.*repository" api/services/*.py 2>/dev/null
```

### 3. API Surface

**Document API endpoints:**

```bash
# FastAPI endpoints
echo "=== Backend API Endpoints ==="
grep -rh "@router\.\(get\|post\|put\|delete\|patch\)" api/v1/*.py 2>/dev/null

# Next.js API routes
echo "=== Frontend API Routes ==="
find app/api -name "route.ts" 2>/dev/null
```

### 4. Data Models

**Entity relationships:**

```bash
# Find relationships in models
echo "=== Model Relationships ==="
grep -n "relationship\|ForeignKey" db/models.py 2>/dev/null
```

## Output Format

```markdown
## Architecture Analysis Report

**Generated:** {timestamp}

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client (Browser)                         │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Next.js Frontend (SSR)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Pages     │  │  Components │  │  Context Providers      │ │
│  │  (SSR+SWR)  │  │  (Client)   │  │  (State Management)     │ │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘ │
│         │                │                      │               │
│         └────────────────┴──────────────────────┘               │
│                          │                                       │
│                    API Routes                                    │
│              (Proxy to Backend)                                  │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Routers   │→ │  Services   │→ │     Repositories        │ │
│  │   (v1/)     │  │ (Business)  │  │    (Data Access)        │ │
│  └─────────────┘  └─────────────┘  └───────────┬─────────────┘ │
│                                                 │               │
└─────────────────────────────────────────────────┬───────────────┘
                              │                   │
                              ▼                   ▼
┌────────────────────┐  ┌─────────────────────────────────────────┐
│   Redis            │  │              PostgreSQL                  │
│  (Cache/Queue)     │  │             (Database)                   │
└────────────────────┘  └─────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Celery Workers                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Worker    │  │    Beat     │  │     Flower              │ │
│  │  (Tasks)    │  │ (Scheduler) │  │   (Monitoring)          │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Layer Architecture

#### Backend (FastAPI)

| Layer | Purpose | Location | Dependencies |
|-------|---------|----------|--------------|
| **Router** | HTTP handling, validation | `api/v1/` | Service |
| **Service** | Business logic | `api/services/` | Repository |
| **Repository** | Data access | `api/repositories/` | Database |
| **Schema** | Data transfer objects | `api/schemas/` | None |
| **Model** | Database entities | `db/models.py` | SQLAlchemy |

**Dependency Rule:** Router → Service → Repository (never reverse)

#### Frontend (Next.js)

| Layer | Purpose | Location | Type |
|-------|---------|----------|------|
| **Page** | Route + SSR data | `app/(pages)/` | Server |
| **Table** | Data display + SWR | `_components/table/` | Client |
| **Context** | CRUD operations | `context/` | Client |
| **API Routes** | Backend proxy | `app/api/` | Server |

### Data Flow

#### Request Flow (List Products)

```
1. Browser → GET /setting/products
2. Next.js Page (Server)
   └→ Fetch /api/setting/products (with cookies)
3. API Route (Server)
   └→ Proxy to backend /api/v1/products (with token)
4. FastAPI Router
   └→ Inject session dependency
   └→ Call ProductService.list()
5. ProductService
   └→ Call ProductRepository.list()
6. ProductRepository
   └→ Execute SQL query
7. Response flows back
8. Page renders with initial data
9. Client hydrates, SWR takes over
```

#### Mutation Flow (Create Product)

```
1. User fills form, clicks "Create"
2. ProductContext.addProduct() called
3. fetchClient POST /api/setting/products
4. API Route proxies to backend
5. FastAPI validates with ProductCreate schema
6. ProductService.create()
7. ProductRepository.create()
8. Database INSERT
9. Response returns created product
10. SWR mutate() updates cache with response
11. UI updates to show new product
```

### Entity Relationships

```
┌──────────────────┐
│      User        │
│──────────────────│
│ id               │
│ email            │
│ role             │
└────────┬─────────┘
         │
         │ 1:N
         ▼
┌──────────────────┐       ┌──────────────────┐
│      Order       │──────→│     Product      │
│──────────────────│  N:M  │──────────────────│
│ id               │       │ id               │
│ user_id (FK)     │       │ name             │
│ status           │       │ price            │
│ total            │       │ category_id (FK) │
└──────────────────┘       └────────┬─────────┘
                                    │
                                    │ N:1
                                    ▼
                           ┌──────────────────┐
                           │    Category      │
                           │──────────────────│
                           │ id               │
                           │ name             │
                           └──────────────────┘
```

### Architectural Patterns

| Pattern | Implementation | Location |
|---------|----------------|----------|
| Repository Pattern | Data access abstraction | `api/repositories/` |
| Service Layer | Business logic isolation | `api/services/` |
| Single Session Per Request | Session passed through layers | Router → Service → Repo |
| SSR + SWR Hybrid | Server render + client updates | Next.js pages |
| API Proxy | Frontend doesn't call backend directly | `app/api/` routes |
| Context Pattern | State management for CRUD | `context/*.tsx` |

### Architectural Decisions

1. **Why Repository Pattern?**
   - Isolates data access logic
   - Makes services testable with mocks
   - Single place for query optimization

2. **Why Single Session Per Request?**
   - Ensures transaction consistency
   - Avoids connection pool exhaustion
   - Simplifies error handling

3. **Why SSR + SWR?**
   - SEO-friendly initial render
   - Fast client-side updates
   - Automatic background revalidation

4. **Why API Proxy?**
   - Hides backend from client
   - Handles auth token refresh
   - Enables request transformation

### Recommendations

1. **Consider adding API versioning**
   - Current: `/api/v1/`
   - Allows breaking changes in future versions

2. **Add circuit breaker for external services**
   - Prevents cascade failures
   - Graceful degradation

3. **Consider event-driven architecture**
   - For cross-service communication
   - Async processing with Celery
```
