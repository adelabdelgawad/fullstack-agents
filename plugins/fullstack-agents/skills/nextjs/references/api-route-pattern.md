# API Route Pattern Reference

Next.js API routes that proxy client requests to FastAPI backend with authentication and CSRF forwarding.

## Key Principles

1. **withAuth wrapper** — Handle authentication, token refresh, and errors
2. **backendFetch directly** — No helper wrappers (no backendGet/Post/Put/Delete)
3. **Import from `@/lib/fetch/backend`** — Not from `./server`
4. **`(token)` for GETs** — No CSRF header needed
5. **`(token, headers)` for mutations** — Forwards X-CSRF-Token to backend
6. **Forward query params** — Pass search params to backend

## Basic Route Structure

```tsx
// app/api/setting/items/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

/**
 * GET /api/setting/items
 * List items with pagination and filtering
 */
export async function GET(request: Request) {
  const params = new URL(request.url).searchParams.toString();
  return withAuth((token) =>
    backendFetch(`/setting/items?${params}`, token)
  );
}

/**
 * POST /api/setting/items
 * Create a new item — forwards CSRF header
 */
export async function POST(request: Request) {
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch('/setting/items', token, { method: 'POST', body, headers })
  );
}
```

## Dynamic Route with ID

```tsx
// app/api/setting/items/[itemId]/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

interface RouteParams {
  params: Promise<{ itemId: string }>;
}

/**
 * GET /api/setting/items/:itemId
 */
export async function GET(request: Request, { params }: RouteParams) {
  const { itemId } = await params;
  return withAuth((token) =>
    backendFetch(`/setting/items/${itemId}`, token)
  );
}

/**
 * PUT /api/setting/items/:itemId
 */
export async function PUT(request: Request, { params }: RouteParams) {
  const { itemId } = await params;
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch(`/setting/items/${itemId}`, token, { method: 'PUT', body, headers })
  );
}

/**
 * DELETE /api/setting/items/:itemId
 */
export async function DELETE(request: Request, { params }: RouteParams) {
  const { itemId } = await params;
  return withAuth((token, headers) =>
    backendFetch(`/setting/items/${itemId}`, token, { method: 'DELETE', headers })
  );
}
```

## Status Toggle Route

```tsx
// app/api/setting/items/[itemId]/status/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

interface RouteParams {
  params: Promise<{ itemId: string }>;
}

export async function PUT(request: Request, { params }: RouteParams) {
  const { itemId } = await params;
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch(`/setting/items/${itemId}/status`, token, { method: 'PUT', body, headers })
  );
}
```

## Bulk Operations Route

```tsx
// app/api/setting/items/status/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

export async function PUT(request: Request) {
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch('/setting/items/status', token, { method: 'PUT', body, headers })
  );
}
```

## The withAuth Helper

```tsx
// lib/fetch/api-route-helper.ts
import { NextResponse } from 'next/server';
import { headers, cookies } from 'next/headers';
import { auth } from '@/lib/auth/server-auth';
import { ApiError } from './errors';
import { setAuthCookies, clearAuthCookies, refreshTokenOnce } from '@/lib/auth/auth-cookies';

/**
 * Features:
 * - Pre-emptive token refresh (30s buffer before expiry)
 * - CSRF header forwarding from client → backend
 * - 401 retry with double-refresh safety
 * - 204 No Content handling
 * - Auth cookie refresh on response
 */
export async function withAuth<T>(
  handler: (token: string, forwardHeaders: Record<string, string>) => Promise<T>
): Promise<NextResponse> {
  // ... see fetch-architecture/references/api-route-helper-pattern.md for full implementation
}
```

## Nested Dynamic Routes

```tsx
// app/api/dialer/campaigns/[campaignId]/batches/[batchId]/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

interface RouteParams {
  params: Promise<{
    campaignId: string;
    batchId: string;
  }>;
}

export async function GET(request: Request, { params }: RouteParams) {
  const { campaignId, batchId } = await params;
  return withAuth((token) =>
    backendFetch(`/dialer/campaigns/${campaignId}/batches/${batchId}`, token)
  );
}

export async function PUT(request: Request, { params }: RouteParams) {
  const { campaignId, batchId } = await params;
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch(
      `/dialer/campaigns/${campaignId}/batches/${batchId}`,
      token,
      { method: 'PUT', body, headers }
    )
  );
}
```

## Route with Query Parameters

```tsx
// app/api/setting/items/search/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams.toString();
  return withAuth((token) =>
    backendFetch(`/setting/items/search?${params}`, token)
  );
}
```

## Route Directory Structure

```
app/api/setting/items/
├── route.ts                    # GET (list), POST (create)
├── status/
│   └── route.ts               # PUT (bulk status update)
├── counts/
│   └── route.ts               # GET (counts for dashboard)
└── [itemId]/
    ├── route.ts               # GET, PUT, DELETE (single item)
    └── status/
        └── route.ts           # PUT (toggle status)
```

## Key Points

1. **withAuth wrapper** — Always use for authenticated routes
2. **`(token)` for GET** — No CSRF forwarding needed
3. **`(token, headers)` for POST/PUT/PATCH/DELETE** — Forward CSRF token
4. **`backendFetch()` directly** — Import from `@/lib/fetch/backend`
5. **`await params`** — Next.js 15+ requires awaiting route params
6. **Forward query params** — Pass through to backend
7. **Consistent error format** — `{ detail: "message" }`
