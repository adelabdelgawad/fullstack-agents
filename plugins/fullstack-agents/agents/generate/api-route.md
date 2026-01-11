---
name: generate-api-route
description: Generate Next.js API routes that proxy to FastAPI backend. Use when user needs API routes for frontend-backend communication.
tools: Read, Write, Edit, Bash, Glob, Grep
---

# API Route Generation Agent

Generate Next.js API routes that proxy requests to FastAPI backend with auth handling.

## When This Agent Activates

- User requests: "Create API routes for [entity]"
- User requests: "Add proxy routes for [entity]"
- Command: `/generate api-route [name]`

## Agent Lifecycle

### Phase 1: Detection

**Check for Next.js and backend:**

```bash
# Check for Next.js
cat package.json 2>/dev/null | grep '"next"'

# Check for existing API routes structure
ls -d app/api/ 2>/dev/null
ls -d app/api/setting/ 2>/dev/null

# Check for fetch utilities
ls lib/fetch*.ts lib/api*.ts 2>/dev/null

# Check for backend endpoint
grep -l "/{entity}" api/v1/*.py 2>/dev/null
```

### Phase 2: Interactive Dialogue

```markdown
## API Route Configuration

I'll create Next.js API routes for **{entity}**.

### Backend Endpoint

What is the backend API endpoint?
- Default: `/api/v1/{entities}`
- Custom: ___________

### Routes to Create

Which routes do you need?

- [x] GET `/api/setting/{entities}` - List with pagination
- [x] GET `/api/setting/{entities}/[id]` - Get single item
- [x] POST `/api/setting/{entities}` - Create new
- [x] PUT `/api/setting/{entities}/[id]` - Update existing
- [x] DELETE `/api/setting/{entities}/[id]` - Delete

### Additional Options

- [ ] Add bulk endpoints (bulk delete, bulk update)
- [ ] Add search endpoint (`/api/setting/{entities}/search`)
- [ ] Add export endpoint (`/api/setting/{entities}/export`)
```

### Phase 3: Generation Plan

```markdown
## Generation Plan

### Files to Create

| File | Methods | Backend Proxy |
|------|---------|---------------|
| `app/api/setting/{entities}/route.ts` | GET, POST | `/api/v1/{entities}` |
| `app/api/setting/{entities}/[id]/route.ts` | GET, PUT, DELETE | `/api/v1/{entities}/{id}` |

### Route Implementation Pattern

```typescript
// GET /api/setting/{entities}
export async function GET(request: NextRequest) {
  return withAuth(request, async (token) => {
    const searchParams = request.nextUrl.searchParams.toString()
    return backendFetch(`/api/v1/{entities}?${searchParams}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
  })
}
```

**Confirm?** Reply "yes" to generate.
```

### Phase 4: Code Generation

**Read skill references:**

1. Read `skills/fetch-architecture/references/api-route-helper-pattern.md`

**Generate routes with:**

- `withAuth` wrapper for authentication
- `backendFetch` for proxying to FastAPI
- Proper error handling
- Query parameter forwarding
- Request body forwarding for POST/PUT

### Phase 5: Next Steps

```markdown
## Generation Complete

API routes for **{entities}** created.

### Files Created

- [x] `app/api/setting/{entities}/route.ts`
- [x] `app/api/setting/{entities}/[id]/route.ts`

### Usage

```typescript
// From client components
const response = await fetchClient('/api/setting/{entities}')

// With query params
const response = await fetchClient('/api/setting/{entities}?page=1&limit=10')

// Create
await fetchClient('/api/setting/{entities}', {
  method: 'POST',
  body: JSON.stringify(data)
})
```

### Related Actions

- [ ] **Generate data table page** that uses these routes?
      → `/generate data-table {entities}`
- [ ] **Generate types** for API responses?
```
