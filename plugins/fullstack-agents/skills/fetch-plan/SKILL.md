---
name: fetch-plan
description: Plan fetch layers for a new entity — determines which server actions, API routes, and client calls to create before implementation.
---

# Fetch Plan

Plan the complete fetch layer for a new entity before writing any code. Outputs a structured plan of files to create with their function signatures and URL patterns.

## Usage

```
/fetch-plan <entity> <section>
```

**Examples:**
```
/fetch-plan schedules setting
/fetch-plan campaigns management
/fetch-plan queue dialer
/fetch-plan agents report
```

## Input

Gather before planning:

| Input | Description | Example |
|-------|-------------|---------|
| Entity name | Singular, snake_case | `schedule`, `campaign_batch` |
| Section | Backend route group | `setting`, `management`, `dialer`, `report` |
| Operations | Which CRUD operations | GET list, GET single, POST, PUT, DELETE, status toggle, bulk status |

## Output Template

Generate this plan for the entity:

```markdown
## Fetch Plan: {entity} ({section})

### Naming Conventions
- **Path**: {path-name} (kebab-case, e.g., campaign-batches)
- **Entity ID param**: {entityId} (camelCase, e.g., campaignBatchId)
- **Pascal name**: {EntityPascal} (e.g., CampaignBatch)

### 1. Server Actions — `lib/actions/{section}/{path-name}.actions.ts`

| Function | Method | URL | Returns |
|----------|--------|-----|---------|
| `get{Entities}(limit, skip, filters?)` | GET | `/backend/{section}/{path}?...` | `{Entity}Response` |
| `get{Entity}(id)` | GET | `/backend/{section}/{path}/{id}` | `{Entity}` |
| `create{Entity}(data)` | POST | `/backend/{section}/{path}` | `{Entity}` |
| `update{Entity}(id, data)` | PUT | `/backend/{section}/{path}/{id}` | `{Entity}` |
| `delete{Entity}(id)` | DELETE | `/backend/{section}/{path}/{id}` | `void` |

### 2. API Routes

| File | Methods | Backend endpoint |
|------|---------|-----------------|
| `app/api/{section}/{path}/route.ts` | GET, POST | `/{section}/{path}` |
| `app/api/{section}/{path}/[{entityId}]/route.ts` | GET, PUT, DELETE | `/{section}/{path}/{id}` |
| `app/api/{section}/{path}/[{entityId}]/status/route.ts` | PUT | `/{section}/{path}/{id}/status` |
| `app/api/{section}/{path}/status/route.ts` | PUT | `/{section}/{path}/status` |

**Pattern reminders:**
- GET handlers: `(token) => backendFetch(...)`
- Mutation handlers: `(token, headers) => backendFetch(..., { headers })`
- Import: `backendFetch` from `@/lib/fetch/backend`

### 3. Client Calls (from table component)

| Action | Call | Returns |
|--------|------|---------|
| Refresh | `api.get<{Entity}Response>('/api/{section}/{path}?...')` | `{Entity}Response` |
| Create | `api.post<{Entity}>('/api/{section}/{path}', data)` | `{Entity}` |
| Update | `api.put<{Entity}>('/api/{section}/{path}/{id}', data)` | `{Entity}` |
| Toggle status | `api.put<{Entity}>('/api/{section}/{path}/{id}/status', { is_active })` | `{Entity}` |
| Delete | `api.delete('/api/{section}/{path}/{id}')` | `void` |
| Bulk status | `api.put('/api/{section}/{path}/status', { ids, is_active })` | `{Entity}[]` |

### 4. Page Component — `app/(pages)/{section}/{path}/page.tsx`

- SSR fetch via `get{Entities}()` server action
- Pass `initialData` to client table component
- No `auth()` check needed (layout handles it)
- Use `Promise.all()` if multiple data sources needed

### 5. Dependencies Check

Before implementing, verify these exist:
- [ ] Backend endpoint: `/{section}/{path}` responds
- [ ] TypeScript types: `lib/types/api/{path-name}.ts` has `{Entity}`, `{Entity}Create`, `{Entity}Response`
- [ ] Backend schemas use `CamelModel` (camelCase in API responses)
```

## Rules

1. **Always plan before implementing** — don't skip to code
2. **Server actions use `/backend/` URLs** — never `/api/`
3. **API routes use `backendFetch` directly** — no helper wrappers
4. **Mutations forward CSRF** — `(token, headers)` pattern
5. **Client uses `api` object** — returns `T` directly
6. **One server action file per entity** — group all CRUD in one file
7. **Standard route structure** — collection, resource, status, bulk status
