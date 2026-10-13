# API Routes Pattern

Next.js API routes act as a proxy layer between frontend and backend, handling authentication.

## Directory Structure

```
app/api/[section]/[entity]/
├── route.ts                    # GET (list) + POST (create)
├── [entityId]/
│   ├── route.ts               # GET (single) + PUT (update) + DELETE
│   └── status/
│       └── route.ts           # PUT (toggle status)
├── status/
│   └── route.ts               # POST (bulk status update)
└── counts/
    └── route.ts               # GET (counts for status panel)
```

## Main Route (GET + POST)

```typescript
// app/api/[section]/[entity]/route.ts
import { NextRequest } from 'next/server';
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

/**
 * GET /api/[section]/[entity]
 * Fetches list with pagination, filtering, and sorting
 */
export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams.toString();
  return withAuth((token) =>
    backendFetch(`/[section]/[entity]/?${params}`, token)
  );
}

/**
 * POST /api/[section]/[entity]
 * Creates a new entity
 */
export async function POST(request: NextRequest) {
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch('/[section]/[entity]/', token, { method: 'POST', body, headers })
  );
}
```

## Individual Entity Route (GET + PUT + DELETE)

```typescript
// app/api/[section]/[entity]/[entityId]/route.ts
import { NextRequest } from 'next/server';
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

/**
 * GET /api/[section]/[entity]/[entityId]
 * Fetches single entity
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ entityId: string }> }
) {
  const { entityId } = await params;
  return withAuth((token) =>
    backendFetch(`/[section]/[entity]/${entityId}`, token)
  );
}

/**
 * PUT /api/[section]/[entity]/[entityId]
 * Updates an existing entity
 */
export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ entityId: string }> }
) {
  const { entityId } = await params;
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch(`/[section]/[entity]/${entityId}`, token, { method: 'PUT', body, headers })
  );
}

/**
 * DELETE /api/[section]/[entity]/[entityId]
 * Deletes (or soft-deletes) an entity
 */
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ entityId: string }> }
) {
  const { entityId } = await params;
  return withAuth((token, headers) =>
    backendFetch(`/[section]/[entity]/${entityId}`, token, { method: 'DELETE', headers })
  );
}
```

## Status Toggle Route

```typescript
// app/api/[section]/[entity]/[entityId]/status/route.ts
import { NextRequest } from 'next/server';
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

/**
 * PUT /api/[section]/[entity]/[entityId]/status
 * Toggles entity active status
 */
export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ entityId: string }> }
) {
  const { entityId } = await params;
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch(`/[section]/[entity]/${entityId}/status`, token, { method: 'PUT', body, headers })
  );
}
```

## Bulk Status Route

```typescript
// app/api/[section]/[entity]/status/route.ts
import { NextRequest } from 'next/server';
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

/**
 * POST /api/[section]/[entity]/status
 * Updates status for multiple entities (bulk operation)
 */
export async function POST(request: NextRequest) {
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch('/[section]/[entity]/status', token, { method: 'POST', body, headers })
  );
}
```

## Counts Route (Optional)

```typescript
// app/api/[section]/[entity]/counts/route.ts
import { NextRequest } from 'next/server';
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

/**
 * GET /api/[section]/[entity]/counts
 * Gets total counts (unaffected by filters)
 */
export async function GET(request: NextRequest) {
  return withAuth((token) =>
    backendFetch('/[section]/[entity]/counts', token)
  );
}
```

## Backend Fetch

API routes call `backendFetch()` directly — no helper wrappers. Import from `@/lib/fetch/backend`.

- `withAuth` lives in `@/lib/fetch/api-route-helper` and handles session extraction + error responses.
- `backendFetch` lives in `@/lib/fetch/backend` and handles the actual HTTP call to the FastAPI backend.
- For GET requests, the callback signature is `(token) => ...`.
- For POST/PUT/PATCH/DELETE requests, the callback signature is `(token, headers) => ...` so CSRF and other forwarded headers are passed through.

## Key Points

1. **Thin proxy layer** - API routes just forward to backend with auth
2. **Consistent error handling** - Use try/catch with proper status codes
3. **Return full entity** - All mutations return the complete updated entity
4. **Use NextRequest** - For type-safe request handling
5. **Await params** - Next.js 15+ requires `await params`
