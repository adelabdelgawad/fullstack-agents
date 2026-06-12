---
name: fetch-architecture
description: Client and server-side fetch utilities for Next.js — direct backend calls from server code and API route proxying with auth refresh for client code. Use when setting up fetch utilities, configuring client-side API calls, or implementing server-side data fetching. Do not use to scaffold per-entity fetch code (use fetch-plan then fetch-implement).
---

# Fetch Architecture Skill

Client and server-side fetch utilities for Next.js applications with two distinct data paths: direct backend calls (server) and API route proxying (client).

## When to Use This Skill

Use this skill when asked to:
- Set up fetch utilities for Next.js
- Configure client-side API calls with auth refresh
- Implement server-side data fetching
- Create API route proxies to backend services
- Handle authentication tokens across layers

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser (Client)                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Client Components                                   │    │
│  │  • api.get/post/put/delete                          │    │
│  │  • CSRF via csrfManager                             │    │
│  │  • URL auto-prefix (/setting/x → /api/setting/x)   │    │
│  └──────────────────────────┬──────────────────────────┘    │
└─────────────────────────────┼───────────────────────────────┘
                              │ HTTP (cookies)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Next.js Server                            │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  API Routes (app/api/...)          ← client only     │    │
│  │  • withAuth(token, forwardHeaders)                   │    │
│  │  • backendFetch() from backend.ts                    │    │
│  │  • Pre-emptive token refresh                         │    │
│  │  • CSRF forwarding                                   │    │
│  └──────────────────────────┬──────────────────────────┘    │
│                             │ HTTP (Bearer token)            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Server Actions (lib/actions/)     ← SSR path        │    │
│  │  • directBackendFetch() — calls backend DIRECTLY     │    │
│  │  • getAccessToken() + getBackendURL()                │    │
│  │  • CSRF via getServerCsrfToken() for mutations       │    │
│  └──────────────────────────┬──────────────────────────┘    │
│                             │ HTTP (Bearer token)            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Server Components (pages)                           │    │
│  │  • Call server actions for SSR data                  │    │
│  │  • Layout handles auth check                         │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────┼───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                           │
│  /backend/setting/...  /backend/management/...              │
└─────────────────────────────────────────────────────────────┘
```

## Anti-Patterns (NEVER DO)

Server actions MUST call the backend directly via `directBackendFetch()`.
Routing server actions through Next.js API routes is FORBIDDEN (unnecessary 2-hop overhead).

```typescript
// ❌ WRONG — server action routing through API route (2 hops)
import { serverGet } from '@/lib/fetch/server';
const data = await serverGet('/api/setting/users');

// ❌ WRONG — server action calling API route URL
const res = await fetch('http://localhost:3000/api/setting/users', {
  headers: { Cookie: cookieHeader }
});

// ✅ CORRECT — server action calls backend directly (1 hop)
import { serverGet } from '@/lib/fetch/server';
const data = await serverGet<UsersResponse>('/backend/setting/users');
```

**Rule:** Server actions always use `/backend/...` URLs. API routes are only for client-side requests.

## Directory Structure

```
lib/
├── fetch/
│   ├── index.ts              # Exports
│   ├── client.ts             # Client-side fetch (browser) — exports `api`
│   ├── server.ts             # Server-side fetch (direct backend calls)
│   ├── backend.ts            # Backend fetch (used in API routes only)
│   ├── api-route-helper.ts   # API route wrappers (withAuth)
│   ├── errors.ts             # Error classes
│   └── types.ts              # TypeScript types
└── auth/
    ├── server-auth.ts        # Server authentication (getAccessToken, auth)
    ├── auth-cookies.ts       # Cookie management (getBackendURL)
    ├── auth-service.ts       # Client auth (token refresh)
    ├── csrf-manager.ts       # Client CSRF token management
    ├── redirect-guard.ts     # Redirect loop detection
    └── auth-logger.ts        # Auth event logging
```

## Core Files

### 1. Error Classes

```typescript
// lib/fetch/errors.ts
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function extractErrorMessage(data: unknown, status: number): string {
  if (typeof data === 'string') return data;
  if (typeof data === 'object' && data !== null) {
    const obj = data as Record<string, unknown>;
    if (typeof obj.detail === 'string') return obj.detail;
    if (typeof obj.message === 'string') return obj.message;
    if (typeof obj.error === 'string') return obj.error;
  }
  return 'An error occurred';
}
```

### 2. Type Definitions

```typescript
// lib/fetch/types.ts
export interface FetchOptions {
  headers?: Record<string, string>;
  timeout?: number;
  cache?: RequestCache;
  next?: NextFetchRequestConfig;
}

export interface FetchRequestOptions extends FetchOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
}
```

### 3. Server Fetch (Direct Backend Calls)

```typescript
// lib/fetch/server.ts
"use server";

/**
 * Server-side fetch utilities for server actions.
 * All requests call the backend directly (single hop).
 * Mutations include a CSRF token fetched from the backend.
 */

import { getAccessToken } from '@/lib/auth/server-auth';
import { getBackendURL } from '@/lib/auth/auth-cookies';
import { ApiError, extractErrorMessage } from './errors';
import type { FetchOptions, FetchRequestOptions } from './types';

const DEFAULT_TIMEOUT = 30000;

async function getServerCsrfToken(accessToken: string): Promise<string | null> {
  try {
    const backendUrl = getBackendURL();
    const response = await fetch(`${backendUrl}/backend/csrf-token`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`,
      },
      cache: 'no-store',
    });
    if (!response.ok) return null;
    const data = await response.json();
    return data.csrfToken ?? data.csrf_token ?? null;
  } catch {
    return null;
  }
}

async function directBackendFetch<T>(
  url: string,
  options: FetchRequestOptions = {}
): Promise<T> {
  const token = await getAccessToken();
  if (!token) {
    throw new ApiError('Not authenticated', 401);
  }

  const backendUrl = getBackendURL();
  const fullUrl = `${backendUrl}${url}`;
  const method = options.method || 'GET';

  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(),
    options.timeout || DEFAULT_TIMEOUT
  );

  // Fetch CSRF token for state-changing requests
  const csrfHeaders: Record<string, string> = {};
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrfToken = await getServerCsrfToken(token);
    if (csrfToken) {
      csrfHeaders['X-CSRF-Token'] = csrfToken;
    }
  }

  try {
    const response = await fetch(fullUrl, {
      method,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'X-Request-ID': crypto.randomUUID(),
        ...csrfHeaders,
        ...options.headers,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
      cache: options.cache ?? 'no-store',
      next: options.next,
    });

    let data: unknown;
    try { data = await response.json(); } catch { data = {}; }

    if (!response.ok) {
      throw new ApiError(extractErrorMessage(data, response.status), response.status, data);
    }
    return data as T;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError('Request timeout', 408);
    }
    if (error instanceof ApiError) { throw error; }
    throw new ApiError(
      error instanceof Error ? error.message : 'Network error', 500
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function serverGet<T>(url: string, opts?: FetchOptions): Promise<T> {
  return directBackendFetch<T>(url, { ...opts, method: 'GET' });
}

export async function serverPost<T>(url: string, body: unknown, opts?: FetchOptions): Promise<T> {
  return directBackendFetch<T>(url, { ...opts, method: 'POST', body });
}

export async function serverPut<T>(url: string, body: unknown, opts?: FetchOptions): Promise<T> {
  return directBackendFetch<T>(url, { ...opts, method: 'PUT', body });
}

export async function serverDelete<T>(url: string, opts?: FetchOptions & { body?: unknown }): Promise<T> {
  return directBackendFetch<T>(url, { ...opts, method: 'DELETE', body: opts?.body });
}
```

### 4. Client Fetch (Browser)

```typescript
// lib/fetch/client.ts
"use client";

import { AuthService } from '@/lib/auth/auth-service';
import { authLogger } from '@/lib/auth/auth-logger';
import { redirectGuard } from '@/lib/auth/redirect-guard';
import { csrfManager } from '@/lib/auth/csrf-manager';
import { ApiError, extractErrorMessage } from './errors';
import type { FetchOptions, FetchRequestOptions } from './types';

const DEFAULT_TIMEOUT = 30000;
const MAX_RETRIES = 2;
const RETRY_DELAY = 1000;

async function clientFetch<T>(
  url: string,
  options: FetchRequestOptions = {},
  attempt = 1,
  isRetryAfterRefresh = false
): Promise<T> {
  // Auto-prefix: /setting/roles → /api/setting/roles
  const fullUrl = url.startsWith('/api') ? url : `/api${url}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(),
    options.timeout || DEFAULT_TIMEOUT
  );

  try {
    const method = options.method || 'GET';

    // Include CSRF token for state-changing requests
    const csrfHeaders: Record<string, string> = {};
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
      try {
        const csrfToken = await csrfManager.getToken();
        csrfHeaders['X-CSRF-Token'] = csrfToken;
      } catch {
        // Continue without CSRF token
      }
    }

    const response = await fetch(fullUrl, {
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-Request-ID': globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2) + Date.now().toString(36),
        ...csrfHeaders,
        ...options.headers,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
      credentials: 'include',
    });

    let data: unknown;
    try { data = await response.json(); } catch { data = {}; }

    if (!response.ok) {
      if (response.status === 401 && !isRetryAfterRefresh) {
        clearTimeout(timeoutId);
        authLogger.logTokenExpiry({ url: fullUrl });
        try {
          const newToken = await AuthService.refreshAccessToken();
          if (newToken) {
            authLogger.logRefreshAttempt(true);
            return clientFetch<T>(url, options, attempt, true);
          }
        } catch (error) {
          authLogger.logRefreshAttempt(false, error instanceof Error ? error.message : 'Unknown error');
        }
        if (typeof window !== 'undefined') {
          if (!redirectGuard.canRedirect()) {
            redirectGuard.showLoopError();
            throw new ApiError('Session expired - redirect loop detected', 401);
          }
          authLogger.logRedirect('Session expired', window.location.href);
          redirectGuard.recordRedirect();
          window.location.href = '/login?auth_error=session_expired';
        }
        throw new ApiError('Session expired', 401);
      }

      if ((response.status === 429 || response.status === 503) && attempt < MAX_RETRIES) {
        clearTimeout(timeoutId);
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY * attempt));
        return clientFetch<T>(url, options, attempt + 1, isRetryAfterRefresh);
      }

      throw new ApiError(extractErrorMessage(data, response.status), response.status, data);
    }

    return data as T;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError('Request timeout', 408);
    }
    if (error instanceof ApiError) throw error;
    throw new ApiError(error instanceof Error ? error.message : 'Network error', 500);
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Client API — returns T directly (no wrapping)
 */
export const api = {
  get: <T>(url: string, opts?: FetchOptions): Promise<T> =>
    clientFetch<T>(url, { ...opts, method: 'GET' }),

  post: <T>(url: string, body: unknown, opts?: FetchOptions): Promise<T> =>
    clientFetch<T>(url, { ...opts, method: 'POST', body }),

  put: <T>(url: string, body: unknown, opts?: FetchOptions): Promise<T> =>
    clientFetch<T>(url, { ...opts, method: 'PUT', body }),

  patch: <T>(url: string, body: unknown, opts?: FetchOptions): Promise<T> =>
    clientFetch<T>(url, { ...opts, method: 'PATCH', body }),

  delete: <T>(url: string, opts?: FetchOptions): Promise<T> =>
    clientFetch<T>(url, { ...opts, method: 'DELETE' }),
};

export default api;
```

### 5. Backend Fetch (API Routes Only)

```typescript
// lib/fetch/backend.ts
import { getBackendURL } from '@/lib/auth/auth-cookies';
import { ApiError, extractErrorMessage } from './errors';

export async function backendFetch<T>(
  endpoint: string,
  token: string,
  options?: {
    method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
    body?: unknown;
    headers?: Record<string, string>;
  }
): Promise<T> {
  const backendUrl = getBackendURL();
  const fullUrl = `${backendUrl}/backend${endpoint}`;

  const response = await fetch(fullUrl, {
    method: options?.method || 'GET',
    headers: {
      'Content-Type': 'application/json',
      'X-Request-ID': crypto.randomUUID(),
      Authorization: `Bearer ${token}`,
      ...options?.headers,
    },
    body: options?.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(extractErrorMessage(errorData, response.status), response.status, errorData);
  }

  if (response.status === 204 || response.headers.get('content-length') === '0') {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
```

### 6. API Route Helper

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
 * GET routes use (token) — no CSRF needed.
 * Mutation routes use (token, headers) — forwards X-CSRF-Token.
 */
export async function withAuth<T>(
  handler: (token: string, forwardHeaders: Record<string, string>) => Promise<T>
): Promise<NextResponse> {
  let accessToken: string | null = null;
  let refreshResult: { success: boolean; accessToken: string | null; setCookies: (r: NextResponse) => void } | null = null;

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

    // Forward CSRF header from client request
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
      // 401 retry with double-refresh safety
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

## Request Flow

### Client-Side (Mutations)
```
Component → api.post() → /api/... route → withAuth(token, headers) → backendFetch() → FastAPI
```

### Server-Side (SSR)
```
Page → Server Action → directBackendFetch() → FastAPI  (single hop, no API route)
```

### Data Fetching (Strategy A Only)

```
useState(initialData) → api.get (manual refresh) → API Route → withAuth → backendFetch → FastAPI
```

This application uses Strategy A (Simple Fetching) exclusively. No SWR.

## Client-Side State Management

Use `useState` for all pages — data changes only via user actions:

```tsx
"use client";
import { useState, useCallback } from "react";
import api from "@/lib/fetch/client";

function DataView({ initialData }) {
  const [data, setData] = useState(initialData);
  const [isLoading, setIsLoading] = useState(false);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      const fresh = await api.get(apiUrl);
      setData(fresh);
    } finally {
      setIsLoading(false);
    }
  }, [apiUrl]);

  const onUpdate = async (id: string, payload: object) => {
    const updated = await api.put(`/api/items/${id}`, payload);
    setData(current => ({
      ...current,
      items: current.items.map(i => i.id === id ? updated : i),
    }));
  };
}
```

See [nextjs/references/data-fetching-strategy.md](../nextjs/references/data-fetching-strategy.md) for the full decision framework.

## Key Patterns

1. **Server actions call backend directly** — `directBackendFetch()` with Bearer token
2. **Client uses API routes** — `api.get/post/put/delete` with `credentials: 'include'`
3. **CSRF on server** — `getServerCsrfToken()` fetched from backend for mutations
4. **CSRF on client** — `csrfManager.getToken()` for POST/PUT/PATCH/DELETE
5. **API routes forward CSRF** — `withAuth` passes `forwardHeaders` to handler
6. **Pre-emptive token refresh** — `withAuth` checks token expiry with 30s buffer
7. **Auto token refresh on 401** — Both client and API route retry once
8. **Consistent error format** — `ApiError` class throughout
9. **Retry on rate limit** — 429/503 with exponential backoff (client only)
