# Fetch Architecture Examples

Real-world examples for Next.js fetch utilities.

## Example 1: Server Action for Data Mutation

```typescript
// lib/actions/users.actions.ts
"use server";

import { serverPost, serverPut, serverDelete } from "@/lib/fetch/server";
import type { User, UserCreate, UserUpdate } from "@/lib/types/api/users";

export async function createUser(data: UserCreate): Promise<{
  success: boolean;
  data?: User;
  error?: string;
}> {
  try {
    // /backend/ prefix — direct backend call (single hop)
    // CSRF token automatically included by directBackendFetch for POST
    const user = await serverPost<User>("/backend/setting/users", data);
    return { success: true, data: user };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create user"
    };
  }
}

export async function updateUser(
  userId: string,
  data: UserUpdate
): Promise<{ success: boolean; error?: string }> {
  try {
    await serverPut(`/backend/setting/users/${userId}`, data);
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update user"
    };
  }
}

export async function deleteUser(
  userId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    await serverDelete(`/backend/setting/users/${userId}`);
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete user"
    };
  }
}
```

## Example 2: Form with Server Action

```typescript
// app/(pages)/setting/users/_components/create-user-form.tsx
"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createUser } from "@/lib/actions/users.actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

export function CreateUserForm() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    role: "user"
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    startTransition(async () => {
      const result = await createUser(formData);

      if (result.success) {
        toast.success("User created successfully");
        router.push("/setting/users");
      } else {
        toast.error(result.error || "Failed to create user");
      }
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        placeholder="Name"
        value={formData.name}
        onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
        required
      />
      <Input
        type="email"
        placeholder="Email"
        value={formData.email}
        onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
        required
      />
      <Button type="submit" disabled={isPending}>
        {isPending ? "Creating..." : "Create User"}
      </Button>
    </form>
  );
}
```

## Example 3: Server Component with SSR Data

```typescript
// app/(pages)/setting/users/page.tsx
import { getUsers } from "@/lib/actions/users.actions";
import UsersTable from "./_components/table/users-table";

interface UsersResponse {
  items: User[];
  total: number;
  page: number;
  limit: number;
}

export default async function UsersPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; limit?: string; search?: string }>;
}) {
  // No auth check needed — layout handles it
  const params = await searchParams;
  const page = Number(params.page) || 1;
  const limit = Number(params.limit) || 10;
  const search = params.search || "";

  const queryParams = new URLSearchParams({
    limit: limit.toString(),
    skip: ((page - 1) * limit).toString(),
    ...(search && { search }),
  });

  // Server action calls directBackendFetch internally
  const users = await getUsers(limit, (page - 1) * limit, { search });

  return (
    <div className="container py-6">
      <h1 className="text-2xl font-bold mb-6">Users</h1>
      <UsersTable
        initialData={users}
        page={page}
        limit={limit}
        search={search}
      />
    </div>
  );
}
```

## Example 4: Parallel SSR Data Fetching

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

  // Both calls go directly to backend in parallel
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

## Example 5: API Route with CSRF Forwarding

```typescript
// app/api/setting/users/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

// GET — no CSRF needed, use (token) only
export async function GET(request: Request) {
  const params = new URL(request.url).searchParams.toString();
  return withAuth((token) =>
    backendFetch(`/setting/users?${params}`, token)
  );
}

// POST — forward CSRF header via (token, headers)
export async function POST(request: Request) {
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch('/setting/users', token, { method: 'POST', body, headers })
  );
}
```

```typescript
// app/api/setting/users/[userId]/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

interface RouteParams {
  params: Promise<{ userId: string }>;
}

export async function GET(request: Request, { params }: RouteParams) {
  const { userId } = await params;
  return withAuth((token) =>
    backendFetch(`/setting/users/${userId}`, token)
  );
}

export async function PUT(request: Request, { params }: RouteParams) {
  const { userId } = await params;
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch(`/setting/users/${userId}`, token, { method: 'PUT', body, headers })
  );
}

export async function DELETE(request: Request, { params }: RouteParams) {
  const { userId } = await params;
  return withAuth((token, headers) =>
    backendFetch(`/setting/users/${userId}`, token, { method: 'DELETE', headers })
  );
}
```

## Example 6: Client Component with State Management

```typescript
// app/(pages)/setting/users/_components/table/users-table.tsx
"use client";

import { useState, useCallback } from "react";
import api from "@/lib/fetch/client";
import { ApiError } from "@/lib/fetch/errors";
import { toast } from "sonner";
import type { User, UsersResponse } from "@/lib/types/api/users";

export default function UsersTable({ initialData }: { initialData: UsersResponse }) {
  const [data, setData] = useState(initialData);
  const [isLoading, setIsLoading] = useState(false);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      // api returns T directly — no { data } unwrapping
      const fresh = await api.get<UsersResponse>('/api/setting/users');
      setData(fresh);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const updateItems = useCallback((updated: User[]) => {
    setData(current => {
      if (!current) return current;
      const map = new Map(updated.map(u => [u.id, u]));
      return {
        ...current,
        items: current.items.map(item => map.get(item.id) ?? item),
      };
    });
  }, []);

  const handleToggleStatus = async (userId: string, isActive: boolean) => {
    try {
      // CSRF token automatically included by client fetch for PUT
      const updated = await api.put<User>(
        `/api/setting/users/${userId}/status`,
        { is_active: isActive }
      );
      updateItems([updated]);
      toast.success(`User ${isActive ? 'activated' : 'deactivated'}`);
    } catch (error) {
      if (error instanceof ApiError) {
        toast.error(error.message);
      }
    }
  };

  const handleCreate = async (userData: Partial<User>) => {
    const created = await api.post<User>('/api/setting/users', userData);
    setData(current => ({
      ...current!,
      items: [created, ...current!.items],
      total: current!.total + 1,
    }));
  };

  const handleDelete = async (userId: string) => {
    await api.delete(`/api/setting/users/${userId}`);
    setData(current => ({
      ...current!,
      items: current!.items.filter(u => u.id !== userId),
      total: current!.total - 1,
    }));
  };

  // ... render table
}
```

## Example 7: File Upload with Progress

```typescript
// lib/fetch/upload.ts
"use client";

export async function uploadFile(
  file: File,
  onProgress?: (percent: number) => void
): Promise<{ url: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append('file', file);

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress((e.loaded / e.total) * 100);
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new Error('Upload failed'));
      }
    });

    xhr.addEventListener('error', () => reject(new Error('Upload failed')));
    xhr.open('POST', '/api/upload');
    xhr.withCredentials = true;
    xhr.send(formData);
  });
}
```

## Example 8: Error Boundary Integration

```typescript
// app/(pages)/setting/users/error.tsx
"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Users page error:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[400px]">
      <h2 className="text-xl font-semibold mb-4">Something went wrong!</h2>
      <p className="text-muted-foreground mb-4">{error.message}</p>
      <Button onClick={reset}>Try again</Button>
    </div>
  );
}
```

## Common Patterns Summary

| Pattern | Use Case | Function |
|---------|----------|----------|
| Client GET | Fetch data in client component | `api.get()` |
| Client POST | Submit form in client component | `api.post()` |
| Server GET | SSR data fetching (direct to backend) | `serverGet('/backend/...')` |
| Server POST | Server action mutation (direct to backend) | `serverPost('/backend/...')` |
| API Route GET | Proxy client GET to backend | `withAuth((token) => backendFetch(...))` |
| API Route Mutation | Proxy client mutation with CSRF | `withAuth((token, headers) => backendFetch(..., { headers }))` |
