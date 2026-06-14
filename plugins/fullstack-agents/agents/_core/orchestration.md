# Agent Orchestration

Patterns for coordinating multiple agents to complete complex tasks.

## Orchestration Concepts

### What is Orchestration?

Orchestration is the coordination of multiple specialized agents to complete a complex task that spans multiple domains. For example, generating a fullstack feature requires:

1. Backend agent (FastAPI entity)
2. API route agent (Next.js proxy routes)
3. Frontend agent (Next.js data table page)

### When to Use Orchestration

Use orchestration when:
- Task spans multiple domains (backend + frontend)
- Multiple files across different technologies need to be created
- Sequential dependencies exist (backend before frontend)
- User requests a "fullstack" feature

## Large & Repetitive Task Decomposition

A single request often expands into many similar units of work — "apply change X
across the app" when the app has 20 pages, "add field Y to every entity", "migrate
all data-tables to the new pattern". Do **not** treat this as one opaque task that
silently walks unit by unit. Decompose it so progress is visible, work can be
parallelized on request, and each unit is audited.

### When to decompose

Decompose when the work splits into **5+ independent units** (pages, entities,
files, endpoints, services) that share a pattern. Below that, do it inline. For a
genuinely large repetitive change, decomposition is the default.

### Step 1 — Enumerate the units

Discover the concrete list first (glob the pages, list the entities, read the
diff scope). Report the count and the list. Never assume "all" — enumerate, so
the breadth is explicit and the user can correct it before any work starts.

### Step 2 — Create one tracked task per unit

Use `TaskCreate` to make **one task per unit** plus a final **audit** task, so the
user sees real progress instead of a single spinner. Mark each `in_progress` when
it starts and `completed` the moment it lands.

- For very large N (say > 25), batch the units (e.g. one task per group of 5) and
  say so — never silently cap or drop units.
- Give each task a clear subject naming its unit (e.g. "Migrate products page").

### Step 3 — Confirm concurrency with the user (required)

Parallel / concurrent execution is **opt-in**. Before fanning out, ASK the user
how to run it — do not start parallel workers on your own initiative:

```markdown
This splits into N independent units. How should I run them?

1. Sequential (default) — one at a time, easiest to follow and review.
2. Parallel — dispatch M worker subagents at once; faster, more concurrent output
   to track. (How many at a time?)

Parallel workers each own one unit and must touch disjoint files.
```

Proceed sequentially if the user doesn't choose. Only run workers in parallel
after an explicit yes.

### Step 4 — Execute

- **Sequential:** work the task list top to bottom, updating status per unit.
- **Parallel (after opt-in):** dispatch worker subagents with the Agent tool,
  one unit per worker, running concurrently. Use **Sonnet** for non-trivial unit
  work and **Haiku** for small mechanical edits; reserve **Opus** for the audit.
  Each worker receives the **refined spec** (see the prompt-polish skill) for its
  unit only: intent, the exact files it owns, success criteria, constraints.
  Workers must touch **disjoint files**; route any shared-file edit to a single
  consolidation task to avoid write conflicts.

### Step 5 — Audit the executors

Executor output is not trusted until reviewed. Run an **audit pass** over the
completed units (an independent reviewer — Opus for substantial changes) that
checks each unit against the success criteria, the project patterns, and the
language-matched validation chain (ruff / clippy / tsc). This is the
draft → review → refine self-correction loop applied across units: fix what the
audit finds, then mark the audit task complete. Report which units passed, which
were fixed, and any that need the user's decision.

### Calibration

- Don't fan out trivial work — a handful of one-line edits is faster done directly
  than delegated.
- Fan out when units are independent, benefit from isolated context, or the user
  asked for speed. Spawn the parallel workers in a single turn.
- Keep progress incremental and the task list honest: status reflects reality, not
  intention.

## Orchestration Flows

### Fullstack Feature Generation

```
/generate fullstack [entity-name]

FLOW:
┌─────────────────────────────────────────────────────────────┐
│                    User Request                              │
│               /generate fullstack product                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Unified Detection                                  │
│  - Detect FastAPI backend                                   │
│  - Detect Next.js frontend                                  │
│  - Find shared entity naming conventions                    │
│  - Check for existing partial implementations               │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Unified Dialogue                                   │
│  - Entity name and fields (shared across all)               │
│  - Backend options (relationships, validations)             │
│  - Frontend options (columns, filters, actions)             │
│  - Confirm unified plan                                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Generate Backend                                   │
│  Agent: generate/fastapi-entity                             │
│  Creates: Model, Schema, CRUD helpers, Router                │
│  Status: Mark as "backend complete"                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: Generate API Routes                                │
│  Agent: generate/api-route                                  │
│  Creates: app/api/setting/{entity}/route.ts                 │
│  Uses: Types from backend schema                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: Generate Frontend                                  │
│  Agent: generate/nextjs-data-table                          │
│  Creates: Types, Page, Table, Columns, Context              │
│  Uses: Field definitions from backend                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 6: Unified Next Steps                                 │
│  - Database migration commands                              │
│  - Test instructions (backend + frontend)                   │
│  - Suggest related entities                                 │
└─────────────────────────────────────────────────────────────┘
```

### Complete CRUD Workflow

```
/generate crud [entity-name]

FLOW:
1. Detect project type
   - FastAPI only? Generate backend CRUD
   - Next.js only? Generate frontend CRUD
   - Both? Run fullstack orchestration

2. For each layer:
   - Backend: Model → Schema → CRUD helper → Router → Register
   - Frontend: Types → API Route → Context → Components → Page

3. Post-generation:
   - Offer to generate tests
   - Offer to add to Docker
   - Suggest related entities
```

### Project Bootstrap

```
/scaffold fullstack [project-name]

FLOW:
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Project Configuration                              │
│  - Project name                                             │
│  - Backend features (auth, celery, etc.)                    │
│  - Frontend features (data tables, forms, etc.)             │
│  - Infrastructure (docker, nginx, etc.)                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Scaffold Backend                                   │
│  Agent: scaffold/project-fastapi                            │
│  Creates: Full FastAPI project structure                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Scaffold Frontend                                  │
│  Agent: scaffold/project-nextjs                             │
│  Creates: Full Next.js project structure                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: Scaffold Infrastructure                            │
│  Agent: scaffold/docker-infrastructure                      │
│  Creates: docker-compose, Dockerfiles, nginx                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: Wire Everything Together                           │
│  - Configure environment variables                          │
│  - Set up shared types/interfaces                           │
│  - Configure proxying                                       │
└─────────────────────────────────────────────────────────────┘
```

## Shared Context

### Entity Definition Sharing

When orchestrating, entity definitions are shared across agents:

```python
# Shared entity context
entity_context = {
    "name": "product",
    "name_plural": "products",
    "name_pascal": "Product",
    "fields": [
        {"name": "name_en", "type": "str", "constraints": {"max_length": 64, "required": True}},
        {"name": "name_ar", "type": "str", "constraints": {"max_length": 64, "required": True}},
        {"name": "price", "type": "Decimal", "constraints": {"precision": 10, "scale": 2}},
        {"name": "category_id", "type": "int", "constraints": {"foreign_key": "category.id"}},
    ],
    "relationships": [
        {"name": "category", "type": "many-to-one", "target": "Category"}
    ],
    "features": {
        "bilingual": True,
        "soft_delete": True,
        "audit_fields": True,
    }
}
```

### Type Mapping

Map types across technologies:

| Python Type | TypeScript Type | SQLAlchemy | Pydantic |
|-------------|-----------------|------------|----------|
| `str` | `string` | `String` | `str` |
| `int` | `number` | `Integer` | `int` |
| `float` | `number` | `Float` | `float` |
| `Decimal` | `number` | `Numeric` | `Decimal` |
| `bool` | `boolean` | `Boolean` | `bool` |
| `datetime` | `string` (ISO) | `DateTime` | `datetime` |
| `date` | `string` (ISO) | `Date` | `date` |
| `UUID` | `string` | `UUID` | `UUID` |
| `JSON` | `Record<string, any>` | `JSON` | `dict` |

## Progress Tracking

### Orchestration Status

```markdown
## Fullstack Generation Progress

Entity: **Product**

### Backend (FastAPI)
- [x] Model created (`db/model.py`)
- [x] Schemas created (`api/schemas/product_schema.py`)
- [x] CRUD helpers created (`api/crud/products.py`)
- [x] Router created (`api/routers/setting/product_router.py`)
- [x] Router registered (`core/app_setup/routers_group/setting_routers.py`)

### API Routes (Next.js)
- [x] Types created (`lib/types/api/product.ts`)
- [x] GET route (`app/api/setting/products/route.ts`)
- [x] POST route (`app/api/setting/products/route.ts`)
- [x] PUT route (`app/api/setting/products/[id]/route.ts`)
- [x] DELETE route (`app/api/setting/products/[id]/route.ts`)

### Frontend (Next.js)
- [x] Context created (`context/products-context.tsx`)
- [x] Table component (`_components/table/products-table.tsx`)
- [x] Columns defined (`_components/table/columns.tsx`)
- [ ] Add modal (`_components/modals/add-product-sheet.tsx`)
- [ ] Edit modal (`_components/modals/edit-product-sheet.tsx`)
- [x] Page created (`page.tsx`)

### Status: 90% Complete

**Remaining:**
- Add modal component
- Edit modal component

Continue? (yes/no)
```

## Error Handling

### Partial Failure Recovery

```markdown
## Orchestration Error

### What Happened

Step 3 (Generate Frontend) failed:

```
Error: Component 'DataTable' not found in @/components/data-table
```

### Already Completed

- [x] Backend generation (all files created)
- [x] API routes (all routes created)

### Recovery Options

1. **Fix and retry** - Install missing dependency and retry frontend generation
   ```bash
   # The DataTable component needs to be created first
   /scaffold frontend-module data-table
   ```

2. **Skip frontend** - Keep backend only, generate frontend later
   ```bash
   /generate data-table products  # Run separately later
   ```

3. **Rollback all** - Delete all generated files
   ```bash
   # Warning: This will delete backend files too
   ```

Which option do you prefer?
```

### Dependency Missing

```markdown
## Orchestration Blocked

### Dependency Required

Cannot proceed with fullstack generation because:

**Missing: Next.js project**

The frontend portion requires a Next.js project, but none was detected.

### Options

1. **Scaffold Next.js project first**
   ```bash
   /scaffold nextjs
   ```
   Then run fullstack generation again.

2. **Generate backend only**
   ```bash
   /generate entity product
   ```
   Skip frontend generation.

3. **Specify frontend path**
   If Next.js is in a different directory, specify the path.

Which option do you prefer?
```

## Orchestration Commands

### /generate fullstack

```markdown
---
description: Generate complete fullstack feature with multiple agents
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Fullstack Feature Generation

Generate a complete fullstack feature spanning backend and frontend.

## Usage

```bash
/generate fullstack [entity-name]
```

## What It Creates

### Backend (FastAPI)
- SQLAlchemy model in `db/model.py`
- Pydantic schemas in `api/schemas/{entity}_schema.py`
- CRUD helpers in `api/crud/{entity}.py`
- Router in `api/routers/setting/{entity}_router.py`

### Frontend (Next.js)
- TypeScript types in `lib/types/api/{entity}.ts`
- API routes in `app/api/setting/{entity}/`
- Context provider in `app/(pages)/setting/{entity}/context/`
- Data table page in `app/(pages)/setting/{entity}/`

## Process

1. Detect both FastAPI and Next.js projects
2. Gather unified entity configuration
3. Generate backend (sequential)
4. Generate API routes
5. Generate frontend (sequential)
6. Provide unified next steps

## Example

```bash
/generate fullstack product

# Will ask:
# - Entity fields
# - Relationships
# - Frontend columns
# - Features (filters, bulk actions, etc.)
```
```

### /scaffold fullstack

```markdown
---
description: Scaffold complete fullstack project from scratch
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Fullstack Project Scaffold

Create a complete fullstack project with backend, frontend, and infrastructure.

## Usage

```bash
/scaffold fullstack [project-name]
```

## What It Creates

### Backend
- FastAPI project structure
- Database configuration
- Authentication (optional)
- Celery workers (optional)

### Frontend
- Next.js 15+ project
- Component library setup
- Authentication pages (optional)
- Data table components

### Infrastructure
- Docker Compose configuration
- Nginx reverse proxy
- MariaDB database
- Redis cache (optional)

## Process

1. Gather project configuration
2. Scaffold FastAPI project
3. Scaffold Next.js project
4. Scaffold Docker infrastructure
5. Configure environment variables
6. Provide setup instructions
```
