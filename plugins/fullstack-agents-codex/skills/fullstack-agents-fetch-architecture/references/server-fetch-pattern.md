# Server Fetch Pattern Reference

Server-side fetch utilities for Next.js server actions. All requests call the FastAPI backend directly (single hop). No routing through API routes.

## Server Fetch for Server Actions

```typescript
// lib/fetch/server.ts
"use server";

/**
 * Server-side fetch utilities for server actions.
 * All requests (GET and mutations) call the backend directly (single hop).
 * Mutations include a CSRF token fetched from the backend.
 */

import { getAccessToken } from '@/lib/auth/server-auth';
import { getBackendURL } from '@/lib/auth/auth-cookies';
import { ApiError, extractErrorMessage } from './errors';
import type { FetchOptions, FetchRequestOptions } from './types';

const DEFAULT_TIMEOUT = 30000;

/**
 * Fetch a CSRF token from the backend for server-side mutation requests.
 */
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

  // Server actions pass `/backend/management/agents` — matches backend route prefix
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
    if (error instanceof ApiError) throw error;
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

## Usage in Server Actions

```typescript
// lib/actions/users.actions.ts
"use server";

import { serverGet, serverPost, serverPut } from "@/lib/fetch/server";
import type { UsersResponse, User, UserCreate } from "@/lib/types/api/users";

export async function getUsers(
  limit: number,
  skip: number,
  filters?: Record<string, string | undefined>
): Promise<UsersResponse> {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  params.append('skip', skip.toString());

  if (filters) {
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.append(key, value);
    });
  }

  // /backend/ prefix — calls FastAPI directly (single hop)
  return serverGet<UsersResponse>(`/backend/setting/users?${params.toString()}`);
}

export async function createUser(userData: UserCreate): Promise<User> {
  // CSRF token is automatically fetched by directBackendFetch for POST
  return serverPost<User>("/backend/setting/users", userData);
}

export async function updateUser(userId: string, userData: Partial<User>): Promise<User> {
  return serverPut<User>(`/backend/setting/users/${userId}`, userData);
}
```

## Usage in Page Components

```typescript
// app/(pages)/setting/users/page.tsx
import { getUsers } from "@/lib/actions/users.actions";
import UsersTable from "./_components/table/users-table";

export default async function UsersPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; limit?: string }>;
}) {
  // No auth check needed here — layout handles it
  const params = await searchParams;
  const page = Number(params.page) || 1;
  const limit = Number(params.limit) || 10;

  const users = await getUsers(limit, (page - 1) * limit);

  return <UsersTable initialData={users} />;
}
```

## Parallel Data Fetching in Pages

```typescript
// app/(pages)/management/campaigns/page.tsx
import { getCampaigns } from "@/lib/actions/management/campaigns.actions";
import { getAgentGroups } from "@/lib/actions/management/agent-groups.actions";
import CampaignsTable from "./_components/table/campaigns-table";

export default async function CampaignsPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; limit?: string }>;
}) {
  const params = await searchParams;
  const page = Number(params.page) || 1;
  const limit = Number(params.limit) || 10;

  // Parallel fetches — both go directly to backend
  const [campaigns, agentGroups] = await Promise.all([
    getCampaigns(limit, (page - 1) * limit),
    getAgentGroups(),
  ]);

  return (
    <CampaignsTable
      initialData={campaigns}
      agentGroups={agentGroups}
    />
  );
}
```

## Error Handling in Server Actions

```typescript
"use server";

import { serverPost } from "@/lib/fetch/server";
import { ApiError } from "@/lib/fetch/errors";

export async function createUserSafe(userData: UserCreate): Promise<{
  success: boolean;
  data?: User;
  error?: string;
}> {
  try {
    const user = await serverPost<User>("/backend/setting/users", userData);
    return { success: true, data: user };
  } catch (error) {
    if (error instanceof ApiError) {
      return { success: false, error: error.message };
    }
    return { success: false, error: "An unexpected error occurred" };
  }
}
```

## Key Points

1. **"use server"** — Required for server actions
2. **Direct backend calls** — `directBackendFetch()` calls FastAPI directly (no API route hop)
3. **`/backend/` URL prefix** — All server action URLs start with `/backend/`
4. **CSRF for mutations** — `getServerCsrfToken()` automatically fetches CSRF token for POST/PUT/PATCH/DELETE
5. **Token from cookies** — `getAccessToken()` reads JWT from server-side cookies
6. **Timeout handling** — AbortController prevents hung requests
7. **No cookie forwarding** — Token extracted directly, no need to forward cookie headers
8. **Layout handles auth** — Pages don't need `auth()` check, layout redirects unauthenticated users
