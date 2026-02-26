---
name: codebase-scanning
description: Dynamically detect project patterns and coding style before code generation. MANDATORY before first generation in any session.
---

# Codebase Scanning

Detect project structure, conventions, and coding patterns to ensure generated code matches the existing codebase exactly.

## When to Use

**MANDATORY** before the first code generation in any session. Run this scan BEFORE any generate agent produces code.

If you have already scanned this session and the results are still in context, skip re-scanning and use the cached profile.

## Phase 1: Structure Detection (~5 seconds)

Quickly identify the project layout:

```
CHECK: src/backend/ exists?
  YES → Nested layout (src/backend/api/, src/backend/db/, etc.)
  NO  → Flat layout (api/, db/, etc.)

CHECK: src/frontend/ exists?
  YES → Nested layout (src/frontend/app/, src/frontend/lib/, etc.)
  NO  → Check for app/ or pages/ directly

CHECK: Router registration
  SCAN: How are routers included in the app?
  - app_setup/routers_group/ pattern?
  - Direct app.include_router() in main.py?
  - APIRouter prefix pattern?

CHECK: Frontend directory layout
  - app/(pages)/ grouping?
  - Direct app/ pages?
  - pages/ directory (Pages Router)?
```

## Phase 2: Pattern Extraction (~10 seconds)

Read 2-3 existing entities to extract actual patterns. Read ONE file from each category:

### Backend Patterns

**ONE router file** (e.g., the first .py in api/routers/setting/):
- How is the session dependency injected? (`SessionDep` param? `Depends(get_session)`?)
- Response schema pattern? (`response_model=` on decorator? Return type annotation?)
- Error handling pattern? (HTTPException directly? Custom exceptions?)
- Pagination pattern? (`skip`/`limit` params? Page-based?)

**ONE model** (from db/model.py or db/models/):
- Field naming convention (snake_case confirmed?)
- Inheritance pattern (`SQLModel`? `Base`? Custom base?)
- Type annotations (`Mapped[str]`? `Column(String)`?)
- Common fields (is_active, created_at, updated_at, name_en/name_ar?)

**ONE schema** (from api/schemas/):
- Base class (`CamelModel`? `BaseModel`?)
- Field convention (snake_case with camelCase alias?)
- Create/Read/Update split pattern

**ONE service or CRUD file** (from api/services/ or api/crud/):
- Data access pattern (Repository class? CRUD helpers? Direct queries?)
- Session handling (passed as param? Stored in __init__?)
- Commit pattern (flush vs commit, who commits?)

### Frontend Patterns

**ONE page.tsx** (from app/(pages)/):
- Server component? Client component?
- Data fetching approach (server actions? direct fetch? SWR?)
- Layout pattern

**ONE table component** (from _components/table/):
- State management (`useState` with initialData? `useSWR`?)
- Update pattern (in-place `updateItems`? `router.refresh()`?)
- Mutation approach (client-side `api.put`? Server actions?)

## Phase 3: Style Profile Construction

After extraction, build this profile and keep it in your working context:

```
┌─────────────────────────────────────────────────────────┐
│                  CODEBASE STYLE PROFILE                  │
├──────────────────────┬──────────────────────────────────┤
│ Backend layout       │ [src/backend/ | flat]            │
│ Frontend layout      │ [src/frontend/ | flat]           │
│ Router registration  │ [routers_group | main.py direct] │
│ Session pattern      │ [SessionDep | Depends(get_session)] │
│ Schema base class    │ [CamelModel | BaseModel]         │
│ Data access pattern  │ [Repository | CRUD helpers | Service+Repo] │
│ Who commits?         │ [Service | Router | CRUD helper] │
│ Bilingual fields     │ [yes: name_en/name_ar | no]      │
│ Soft delete          │ [is_active | hard delete]         │
│ Audit fields         │ [created_at/updated_at | none]    │
│ Model inheritance    │ [SQLModel | declarative Base]     │
│ Type annotations     │ [Mapped[T] | Column(T)]          │
│ Frontend state       │ [useState | useSWR | hybrid]      │
│ Mutation approach    │ [client api.put | server actions]  │
│ Table update pattern │ [updateItems in-place | router.refresh] │
│ API route pattern    │ [route factory | manual proxy]     │
│ Import style         │ [absolute | relative]              │
│ Indentation          │ [2 spaces | 4 spaces]              │
└──────────────────────┴──────────────────────────────────┘
```

## Priority Rule

**Codebase patterns ALWAYS override skill reference patterns.**

If the actual project uses a different pattern than what's described in skill references:
- Follow the **actual project** pattern
- Note the divergence for the user
- Do NOT "correct" the project to match the skill reference

The skill references are starting points. The real codebase is the source of truth.

## Output

After scanning, briefly report:
1. Detected project structure (1-2 lines)
2. Key patterns found (the style profile table)
3. Any divergences from skill references (if any)

Then proceed with the generation task that triggered this scan.
