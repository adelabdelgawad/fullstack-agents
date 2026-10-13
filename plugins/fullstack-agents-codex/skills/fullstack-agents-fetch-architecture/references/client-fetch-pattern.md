# Client Fetch Pattern Reference

Browser-side fetch utilities for Next.js client components.

## Complete Client Fetch Implementation

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

/**
 * Core client fetch function with:
 * - URL auto-prefix (/setting/roles → /api/setting/roles)
 * - CSRF token for mutations via csrfManager
 * - Timeout handling
 * - Auto retry on 429/503
 * - Token refresh on 401 with auth logging
 * - Redirect guard (loop detection)
 */
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
        // Continue without CSRF token - backend will reject if required
      }
    }

    const response = await fetch(fullUrl, {
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-Request-ID': globalThis.crypto?.randomUUID?.()
          ?? Math.random().toString(36).slice(2) + Date.now().toString(36),
        ...csrfHeaders,
        ...options.headers,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
      credentials: 'include',  // Send cookies to API routes
    });

    let data: unknown;
    try { data = await response.json(); } catch { data = {}; }

    if (!response.ok) {
      // ==========================================
      // HANDLE 401 - Token Refresh
      // ==========================================
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
          authLogger.logRefreshAttempt(
            false,
            error instanceof Error ? error.message : 'Unknown error'
          );
        }

        if (typeof window !== 'undefined') {
          // Check redirect guard before redirecting
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

      // ==========================================
      // HANDLE 429/503 - Rate Limit / Unavailable
      // ==========================================
      if ((response.status === 429 || response.status === 503) && attempt < MAX_RETRIES) {
        clearTimeout(timeoutId);
        await new Promise(resolve =>
          setTimeout(resolve, RETRY_DELAY * attempt)
        );
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
    throw new ApiError(
      error instanceof Error ? error.message : 'Network error',
      500
    );
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

## Usage in Components

### Direct API Calls (Standard Pattern)

```typescript
"use client";

import api from '@/lib/fetch/client';
import { ApiError } from '@/lib/fetch/errors';
import { toast } from 'sonner';

async function handleUpdate(id: string, data: UpdateData) {
  try {
    // Returns T directly — no { data } unwrapping needed
    const updated = await api.put<Item>(
      `/api/items/${id}`,
      data
    );
    toast.success('Updated successfully');
    return updated;
  } catch (error) {
    if (error instanceof ApiError) {
      toast.error(error.message);
    }
    throw error;
  }
}
```

### URL Auto-Prefix

```typescript
// Both are equivalent — auto-prefix adds /api
const roles = await api.get<Role[]>('/setting/roles');
const roles = await api.get<Role[]>('/api/setting/roles');

// Use whichever is more readable in context
```

### With Error Handling

```typescript
"use client";

import api from '@/lib/fetch/client';
import { ApiError } from '@/lib/fetch/errors';

async function createItem(data: CreateData) {
  try {
    const created = await api.post<Item>('/api/items', data);
    return { success: true, data: created };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 400) {
        return { success: false, error: 'Invalid data', details: error.data };
      }
      if (error.status === 409) {
        return { success: false, error: 'Item already exists' };
      }
      return { success: false, error: error.message };
    }
    return { success: false, error: 'Network error' };
  }
}
```

### State Management (Strategy A)

```typescript
"use client";

import { useState, useCallback } from "react";
import api from "@/lib/fetch/client";
import type { ItemsResponse, Item } from "@/lib/types/api/items";

function ItemsTable({ initialData }: { initialData: ItemsResponse }) {
  const [data, setData] = useState(initialData);
  const [isLoading, setIsLoading] = useState(false);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      const fresh = await api.get<ItemsResponse>(apiUrl);
      setData(fresh);
    } finally {
      setIsLoading(false);
    }
  }, [apiUrl]);

  // Update from mutation response
  const updateItems = useCallback((serverResponse: Item[]) => {
    setData(current => {
      if (!current) return current;
      const responseMap = new Map(serverResponse.map(i => [i.id, i]));
      return {
        ...current,
        items: current.items.map(item =>
          responseMap.has(item.id) ? responseMap.get(item.id)! : item
        ),
      };
    });
  }, []);

  const onToggleStatus = async (id: string, isActive: boolean) => {
    const updated = await api.put<Item>(
      `/api/setting/items/${id}/status`,
      { is_active: isActive }
    );
    updateItems([updated]);
  };
}
```

## Auth Service Integration

```typescript
// lib/auth/auth-service.ts
export class AuthService {
  static async refreshAccessToken(): Promise<string | null> {
    try {
      const response = await fetch('/api/auth/refresh', {
        method: 'POST',
        credentials: 'include',
      });

      if (!response.ok) {
        return null;
      }

      const data = await response.json();
      return data.accessToken;
    } catch {
      return null;
    }
  }

  static async logout(): Promise<void> {
    await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'include',
    });
    window.location.href = '/login';
  }
}
```

## Key Features

| Feature | Implementation |
|---------|---------------|
| API object | `api.get/post/put/patch/delete` — returns `T` directly |
| URL prefix | Auto-adds `/api` if missing |
| CSRF | `csrfManager.getToken()` for POST/PUT/PATCH/DELETE |
| Cookies | `credentials: 'include'` |
| Timeout | AbortController with setTimeout |
| Retry | Exponential backoff on 429/503 |
| Auth Refresh | Auto-refresh on 401 via `AuthService` |
| Redirect Guard | `redirectGuard.canRedirect()` prevents loops |
| Auth Logger | `authLogger` logs token expiry, refresh attempts, redirects |
| Request ID | `X-Request-ID` header for tracing |
| Type Safety | Generic return types |
