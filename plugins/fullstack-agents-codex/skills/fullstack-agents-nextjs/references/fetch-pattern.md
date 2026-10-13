# Fetch Pattern Reference

Client and server-side fetch utilities for API communication.

## File Structure

```
lib/fetch/
├── client.ts           # Client-side fetch (browser) — exports `api` object
├── server.ts           # Server-side fetch (server actions) — direct backend calls
├── backend.ts          # Backend fetch (API routes only) — calls FastAPI
├── api-route-helper.ts # withAuth wrapper for API routes
├── errors.ts           # Error classes
├── types.ts            # TypeScript types
└── index.ts            # Exports
```

## Two Data Paths

```
SERVER PATH (1 hop):  Server Action → directBackendFetch() → FastAPI
                      URLs: /backend/setting/users

CLIENT PATH (2 hops): Client → api.post() → /api/... → withAuth() → backendFetch() → FastAPI
```

## Client-Side Fetch (`lib/fetch/client.ts`)

```tsx
"use client";

import { AuthService } from '@/lib/auth/auth-service';
import { csrfManager } from '@/lib/auth/csrf-manager';
import { redirectGuard } from '@/lib/auth/redirect-guard';
import { authLogger } from '@/lib/auth/auth-logger';
import { ApiError, extractErrorMessage } from './errors';
import type { FetchOptions, FetchRequestOptions } from './types';

const DEFAULT_TIMEOUT = 30000;
const MAX_RETRIES = 2;
const RETRY_DELAY = 1000;
const API_PREFIX = '/api';

/**
 * Client fetch for calling Next.js API routes
 * Auto-prefixes URLs with /api/ if not already prefixed
 */
async function clientFetch<T>(
  url: string,
  options: FetchRequestOptions = {},
  attempt = 1,
  isRetryAfterRefresh = false
): Promise<T> {
  // Auto-prefix URL
  const fullUrl = url.startsWith('/api') ? url : `${API_PREFIX}${url}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(),
    options.timeout || DEFAULT_TIMEOUT
  );

  // Add CSRF token for mutations
  const isMutation = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(options.method || 'GET');
  const csrfToken = isMutation ? csrfManager.getToken() : null;

  try {
    const response = await fetch(fullUrl, {
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-Request-ID': crypto.randomUUID(),
        ...(csrfToken && { 'X-CSRF-Token': csrfToken }),
        ...options.headers,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
      credentials: 'include',
    });

    let data: unknown;
    try {
      data = await response.json();
    } catch {
      data = {};
    }

    if (!response.ok) {
      if (response.status === 401 && !isRetryAfterRefresh) {
        clearTimeout(timeoutId);
        if (redirectGuard.isLooping()) {
          throw new ApiError('Redirect loop detected', 401);
        }
        try {
          const newToken = await AuthService.refreshAccessToken();
          if (newToken) {
            authLogger.logRefresh('client-fetch');
            return clientFetch<T>(url, options, attempt, true);
          }
        } catch { /* Refresh failed */ }
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
        throw new ApiError('Session expired', 401);
      }

      if ((response.status === 429 || response.status === 503) && attempt < MAX_RETRIES) {
        clearTimeout(timeoutId);
        await new Promise(resolve => setTimeout(resolve, RETRY_DELAY * attempt));
        return clientFetch<T>(url, options, attempt + 1, isRetryAfterRefresh);
      }

      throw new ApiError(extractErrorMessage(data), response.status, data);
    }

    return data as T;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError('Request timeout', 408);
    }
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      error instanceof Error ? error.message : 'Network error',
      500
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * API client — returns T directly (no wrapper)
 * URLs auto-prefixed: api.get('/setting/users') → /api/setting/users
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

## Server-Side Fetch (`lib/fetch/server.ts`)

```tsx
"use server";

import { getAccessToken } from '@/lib/auth/server-auth';
import { getBackendURL } from '@/lib/auth/auth-cookies';
import { ApiError, extractErrorMessage } from './errors';
import type { FetchOptions, FetchRequestOptions } from './types';

const DEFAULT_TIMEOUT = 30000;

/**
 * Fetch CSRF token from backend for server-side mutations
 */
async function getServerCsrfToken(accessToken: string): Promise<string> {
  const backendUrl = getBackendURL();
  const response = await fetch(`${backendUrl}/auth/csrf-token`, {
    headers: { 'Authorization': `Bearer ${accessToken}` },
  });
  const data = await response.json();
  return data.csrf_token;
}

/**
 * Direct backend fetch — server actions call FastAPI directly (1 hop)
 * URLs use /backend/ prefix: /backend/setting/users
 */
async function directBackendFetch<T>(
  url: string,
  options: FetchRequestOptions = {}
): Promise<T> {
  const accessToken = await getAccessToken();
  if (!accessToken) throw new ApiError('Not authenticated', 401);

  const backendUrl = getBackendURL();
  // Strip /backend prefix to get the actual endpoint
  const endpoint = url.startsWith('/backend') ? url.replace('/backend', '') : url;
  const fullUrl = `${backendUrl}${endpoint}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(),
    options.timeout || DEFAULT_TIMEOUT
  );

  // Fetch CSRF token for mutations
  const isMutation = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(options.method || 'GET');
  const csrfToken = isMutation ? await getServerCsrfToken(accessToken) : null;

  try {
    const response = await fetch(fullUrl, {
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`,
        'X-Request-ID': crypto.randomUUID(),
        ...(csrfToken && { 'X-CSRF-Token': csrfToken }),
        ...options.headers,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });

    let data: unknown;
    try {
      data = await response.json();
    } catch {
      data = {};
    }

    if (!response.ok) {
      throw new ApiError(extractErrorMessage(data), response.status, data);
    }

    return data as T;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError('Request timeout', 408);
    }
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      error instanceof Error ? error.message : 'Network error',
      500
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

// Convenience methods for server actions — use /backend/ URLs
export async function serverGet<T>(url: string, opts?: FetchOptions): Promise<T> {
  return directBackendFetch<T>(url, { ...opts, method: 'GET' });
}

export async function serverPost<T>(url: string, body: unknown, opts?: FetchOptions): Promise<T> {
  return directBackendFetch<T>(url, { ...opts, method: 'POST', body });
}

export async function serverPut<T>(url: string, body: unknown, opts?: FetchOptions): Promise<T> {
  return directBackendFetch<T>(url, { ...opts, method: 'PUT', body });
}

export async function serverPatch<T>(url: string, body: unknown, opts?: FetchOptions): Promise<T> {
  return directBackendFetch<T>(url, { ...opts, method: 'PATCH', body });
}

export async function serverDelete<T>(url: string, opts?: FetchOptions): Promise<T> {
  return directBackendFetch<T>(url, { ...opts, method: 'DELETE' });
}
```

## Backend Fetch (`lib/fetch/backend.ts`)

```tsx
// Used by API routes ONLY — NOT by server actions
import { ApiError, extractErrorMessage } from './errors';
import type { FetchRequestOptions } from './types';

const DEFAULT_TIMEOUT = 30000;

/**
 * Fetch from FastAPI backend — used in API route handlers
 * Prepends backend URL to endpoint
 */
export async function backendFetch<T>(
  endpoint: string,
  accessToken: string,
  options: FetchRequestOptions = {}
): Promise<T> {
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';
  const fullUrl = `${backendUrl}${endpoint}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(),
    options.timeout || DEFAULT_TIMEOUT
  );

  try {
    const response = await fetch(fullUrl, {
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`,
        'X-Request-ID': crypto.randomUUID(),
        ...options.headers,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });

    if (response.status === 204) return undefined as T;

    let data: unknown;
    try {
      data = await response.json();
    } catch {
      data = {};
    }

    if (!response.ok) {
      throw new ApiError(extractErrorMessage(data), response.status, data);
    }

    return data as T;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError('Request timeout', 408);
    }
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      error instanceof Error ? error.message : 'Network error',
      500
    );
  } finally {
    clearTimeout(timeoutId);
  }
}
```

## Error Classes

```tsx
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

export function extractErrorMessage(data: unknown): string {
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

## Type Definitions

```tsx
// lib/fetch/types.ts
export interface FetchOptions {
  headers?: Record<string, string>;
  timeout?: number;
}

export interface FetchRequestOptions extends FetchOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
}
```

## Usage Examples

### Client Component
```tsx
"use client";
import api from "@/lib/fetch/client";

// api auto-prefixes /api/ — pass path without prefix
const handleUpdate = async () => {
  try {
    const result = await api.put<Item>(`/setting/items/${id}`, payload);
    toast.success("Updated");
  } catch (error) {
    toast.error(error.message);
  }
};

// Fetching data
const items = await api.get<ItemsResponse>('/setting/items?limit=50&skip=0');
```

### Server Action
```tsx
// lib/actions/setting/items.actions.ts
"use server";
import { serverGet, serverPost } from "@/lib/fetch/server";

// Server actions use /backend/ URLs (direct to FastAPI, 1 hop)
export async function getItems(limit: number, skip: number) {
  return serverGet<ItemsResponse>(`/backend/setting/items?limit=${limit}&skip=${skip}`);
}

export async function createItem(data: ItemCreate) {
  return serverPost<Item>("/backend/setting/items", data);
}
```

### API Route
```tsx
// app/api/setting/items/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

// GET uses (token) only
export async function GET(request: Request) {
  const params = new URL(request.url).searchParams.toString();
  return withAuth((token) =>
    backendFetch(`/setting/items?${params}`, token)
  );
}

// POST uses (token, headers) for CSRF forwarding
export async function POST(request: Request) {
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch('/setting/items', token, { method: 'POST', body, headers })
  );
}
```

## Key Points

1. **Client uses `api` object** — Returns `T` directly (no `{ data: T }` wrapper)
2. **`api` auto-prefixes URLs** — `api.get('/setting/users')` → `/api/setting/users`
3. **Server actions use `/backend/` URLs** — Direct to FastAPI (1 hop, no API routes)
4. **API routes use `backendFetch`** — From `@/lib/fetch/backend` (separate file)
5. **GET handlers**: `(token)` callback — no headers needed
6. **Mutation handlers**: `(token, headers)` callback — forwards CSRF token
7. **Auto token refresh** — On 401, tries refresh once
8. **CSRF on both paths** — Server: `getServerCsrfToken()`, Client: `csrfManager.getToken()`
