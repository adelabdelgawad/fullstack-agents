# API Route Helper Pattern Reference

Wrappers for Next.js API routes that proxy client requests to FastAPI backend with authentication, CSRF forwarding, and token refresh.

## withAuth Helper

```typescript
// lib/fetch/api-route-helper.ts
import { NextResponse } from 'next/server';
import { headers, cookies } from 'next/headers';
import { auth } from '@/lib/auth/server-auth';
import { ApiError } from './errors';
import { setAuthCookies, clearAuthCookies, refreshTokenOnce } from '@/lib/auth/auth-cookies';

function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(Buffer.from(token.split('.')[1], 'base64').toString());
    if (!payload?.exp) return true;
    return payload.exp * 1000 < Date.now() + 30_000; // 30s buffer
  } catch { return true; }
}

async function tryRefreshToken(): Promise<{
  success: boolean;
  accessToken: string | null;
  setCookies: (response: NextResponse) => void;
}> {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get('refresh_token')?.value;
  if (!refreshToken) return { success: false, accessToken: null, setCookies: () => {} };

  const data = await refreshTokenOnce(refreshToken);
  if (!data) return { success: false, accessToken: null, setCookies: () => {} };

  return {
    success: true,
    accessToken: data.accessToken,
    setCookies: (response: NextResponse) => setAuthCookies(response, data),
  };
}

/**
 * Wrap API route with authentication, CSRF forwarding, token refresh, and error handling.
 *
 * - Pre-checks token expiry (30s buffer) and refreshes proactively
 * - Forwards X-CSRF-Token header from client to backend
 * - Retries on 401 with double-refresh safety (prevents family revocation)
 * - Handles 204 No Content responses
 * - Sets refreshed auth cookies on response
 */
export async function withAuth<T>(
  handler: (token: string, forwardHeaders: Record<string, string>) => Promise<T>
): Promise<NextResponse> {
  let accessToken: string | null = null;
  let refreshResult: RefreshResult | null = null;

  try {
    const session = await auth();
    if (!session?.accessToken) {
      return NextResponse.json({ detail: 'Unauthorized' }, { status: 401 });
    }

    accessToken = session.accessToken;

    // Pre-emptive token refresh (30s buffer)
    if (isTokenExpired(accessToken)) {
      refreshResult = await tryRefreshToken();
      if (!refreshResult.success || !refreshResult.accessToken) {
        const response = NextResponse.json({ detail: 'Session expired' }, { status: 401 });
        clearAuthCookies(response);
        return response;
      }
      accessToken = refreshResult.accessToken;
    }

    // Forward CSRF header from client request to backend
    const forwardHeaders: Record<string, string> = {};
    const requestHeaders = await headers();
    const csrfToken = requestHeaders.get('X-CSRF-Token');
    if (csrfToken) {
      forwardHeaders['X-CSRF-Token'] = csrfToken;
    }

    const data = await handler(accessToken, forwardHeaders);

    // Handle 204 No Content
    if (data === undefined) {
      const response = new NextResponse(null, { status: 204 });
      if (refreshResult) refreshResult.setCookies(response);
      return response;
    }

    const response = NextResponse.json(data);
    if (refreshResult) refreshResult.setCookies(response);
    return response;

  } catch (error) {
    if (error instanceof ApiError) {
      // 401 retry — but only if pre-check refresh didn't already happen
      // A second refresh with a stale cookie triggers backend reuse detection → family revocation
      if (error.status === 401 && !refreshResult) {
        const retryRefresh = await tryRefreshToken();
        if (retryRefresh.success && retryRefresh.accessToken) {
          try {
            const fh: Record<string, string> = {};
            const rh = await headers();
            const csrf = rh.get('X-CSRF-Token');
            if (csrf) fh['X-CSRF-Token'] = csrf;

            const data = await handler(retryRefresh.accessToken, fh);
            if (data === undefined) {
              const response = new NextResponse(null, { status: 204 });
              retryRefresh.setCookies(response);
              return response;
            }
            const response = NextResponse.json(data);
            retryRefresh.setCookies(response);
            return response;
          } catch (retryError) {
            if (retryError instanceof ApiError) {
              return NextResponse.json(
                { detail: retryError.message, ...(retryError.data && typeof retryError.data === 'object' ? retryError.data : {}) },
                { status: retryError.status }
              );
            }
            throw retryError;
          }
        }
        const response = NextResponse.json({ detail: error.message }, { status: 401 });
        clearAuthCookies(response);
        return response;
      }

      return NextResponse.json(
        { detail: error.message, ...(error.data && typeof error.data === 'object' ? error.data : {}) },
        { status: error.status }
      );
    }
    console.error('API route error:', error);
    return NextResponse.json({ detail: 'Internal server error' }, { status: 500 });
  }
}
```

**Note:** There are no `backendGet/Post/Put/Delete` helper functions. API routes call `backendFetch()` directly.

## Basic API Route Pattern

```typescript
// app/api/setting/users/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

/**
 * GET /api/setting/users
 * List users — GET doesn't need CSRF, so headers param is unused
 */
export async function GET(request: Request) {
  const params = new URL(request.url).searchParams.toString();
  return withAuth((token) =>
    backendFetch(`/setting/users?${params}`, token)
  );
}

/**
 * POST /api/setting/users
 * Create a new user — forwards CSRF header via forwardHeaders
 */
export async function POST(request: Request) {
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch('/setting/users', token, { method: 'POST', body, headers })
  );
}
```

## Dynamic Route Pattern

```typescript
// app/api/setting/users/[userId]/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

interface RouteParams {
  params: Promise<{ userId: string }>;
}

/**
 * GET /api/setting/users/:userId
 */
export async function GET(request: Request, { params }: RouteParams) {
  const { userId } = await params;
  return withAuth((token) =>
    backendFetch(`/setting/users/${userId}`, token)
  );
}

/**
 * PUT /api/setting/users/:userId
 */
export async function PUT(request: Request, { params }: RouteParams) {
  const { userId } = await params;
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch(`/setting/users/${userId}`, token, { method: 'PUT', body, headers })
  );
}

/**
 * DELETE /api/setting/users/:userId
 */
export async function DELETE(request: Request, { params }: RouteParams) {
  const { userId } = await params;
  return withAuth((token, headers) =>
    backendFetch(`/setting/users/${userId}`, token, { method: 'DELETE', headers })
  );
}
```

## Status Toggle Route

```typescript
// app/api/setting/users/[userId]/status/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

interface RouteParams {
  params: Promise<{ userId: string }>;
}

export async function PUT(request: Request, { params }: RouteParams) {
  const { userId } = await params;
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch(`/setting/users/${userId}/status`, token, { method: 'PUT', body, headers })
  );
}
```

## Bulk Operations Route

```typescript
// app/api/setting/users/status/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

export async function PUT(request: Request) {
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch('/setting/users/status', token, { method: 'PUT', body, headers })
  );
}
```

## Without Authentication

```typescript
// app/api/public/health/route.ts
import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({ status: "healthy" });
}
```

## Route Directory Structure

```
app/api/
├── setting/
│   └── users/
│       ├── route.ts                    # GET (list), POST (create)
│       ├── status/
│       │   └── route.ts               # PUT (bulk status)
│       └── [userId]/
│           ├── route.ts               # GET, PUT, DELETE
│           └── status/
│               └── route.ts           # PUT (toggle)
├── public/
│   └── health/
│       └── route.ts                   # GET (no auth)
└── auth/
    ├── login/
    │   └── route.ts
    └── refresh/
        └── route.ts
```

## Key Patterns

1. **withAuth wrapper** — Always use for authenticated routes
2. **`(token)` for GETs** — No CSRF needed, ignore forwardHeaders
3. **`(token, headers)` for mutations** — Forward CSRF token to backend
4. **`backendFetch()` directly** — No helper wrappers (no backendGet/Post/Put/Delete)
5. **Import from `@/lib/fetch/backend`** — Not from `./server`
6. **`await params`** — Required in Next.js 15+
7. **Pre-emptive refresh** — Token checked before handler runs (30s buffer)
8. **Double-refresh safety** — Won't retry refresh if pre-check already refreshed
9. **204 handling** — Returns `new NextResponse(null, { status: 204 })`
