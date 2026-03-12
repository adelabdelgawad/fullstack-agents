---
name: fetch-implement
description: Scaffold fetch boilerplate for a new entity — generates server actions, API routes, and client call patterns following the correct architecture.
---

# Fetch Implement

Scaffold the fetch layer for a new entity. Creates server actions and API routes with correct patterns.

## Usage

```
/fetch-implement <entity> <section>
```

**Examples:**
```
/fetch-implement schedules setting
/fetch-implement campaigns management
/fetch-implement queue dialer
```

## Prerequisites

Before running, ensure:
1. A fetch plan exists (run `/fetch-plan` first if unsure)
2. TypeScript types exist at `lib/types/api/{path-name}.ts`
3. Backend endpoint is implemented and responding

---

## Template: Server Actions

```typescript
// lib/actions/{section}/{path-name}.actions.ts
"use server";

import { serverGet, serverPost, serverPut, serverDelete } from "@/lib/fetch/server";
import type { {Entity}, {Entity}Create, {Entity}Response } from "@/lib/types/api/{path-name}";

export async function get{Entities}(
  limit: number,
  skip: number,
  filters?: Record<string, string | undefined>
): Promise<{Entity}Response> {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  params.append('skip', skip.toString());
  if (filters) {
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.append(key, value);
    });
  }
  return serverGet<{Entity}Response>(`/backend/{section}/{path}?${params.toString()}`);
}

export async function get{Entity}(id: string): Promise<{Entity}> {
  return serverGet<{Entity}>(`/backend/{section}/{path}/${id}`);
}

export async function create{Entity}(data: {Entity}Create): Promise<{Entity}> {
  return serverPost<{Entity}>("/backend/{section}/{path}", data);
}

export async function update{Entity}(id: string, data: Partial<{Entity}>): Promise<{Entity}> {
  return serverPut<{Entity}>(`/backend/{section}/{path}/${id}`, data);
}

export async function delete{Entity}(id: string): Promise<void> {
  return serverDelete(`/backend/{section}/{path}/${id}`);
}
```

**Substitution guide:**
| Placeholder | Example (entity: `campaign_batch`, section: `management`) |
|-------------|-----------------------------------------------------------|
| `{Entity}` | `CampaignBatch` |
| `{Entities}` | `CampaignBatches` |
| `{section}` | `management` |
| `{path}` | `campaign-batches` |
| `{path-name}` | `campaign-batches` |

---

## Template: API Route — Collection

```typescript
// app/api/{section}/{path}/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams.toString();
  return withAuth((token) =>
    backendFetch(`/{section}/{path}?${params}`, token)
  );
}

export async function POST(request: Request) {
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch('/{section}/{path}', token, { method: 'POST', body, headers })
  );
}
```

---

## Template: API Route — Resource

```typescript
// app/api/{section}/{path}/[{entityId}]/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

interface RouteParams {
  params: Promise<{ {entityId}: string }>;
}

export async function GET(request: Request, { params }: RouteParams) {
  const { {entityId} } = await params;
  return withAuth((token) =>
    backendFetch(`/{section}/{path}/${{entityId}}`, token)
  );
}

export async function PUT(request: Request, { params }: RouteParams) {
  const { {entityId} } = await params;
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch(`/{section}/{path}/${{entityId}}`, token, { method: 'PUT', body, headers })
  );
}

export async function DELETE(request: Request, { params }: RouteParams) {
  const { {entityId} } = await params;
  return withAuth((token, headers) =>
    backendFetch(`/{section}/{path}/${{entityId}}`, token, { method: 'DELETE', headers })
  );
}
```

---

## Template: API Route — Status Toggle

```typescript
// app/api/{section}/{path}/[{entityId}]/status/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

interface RouteParams {
  params: Promise<{ {entityId}: string }>;
}

export async function PUT(request: Request, { params }: RouteParams) {
  const { {entityId} } = await params;
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch(`/{section}/{path}/${{entityId}}/status`, token, { method: 'PUT', body, headers })
  );
}
```

---

## Template: API Route — Bulk Status

```typescript
// app/api/{section}/{path}/status/route.ts
import { withAuth } from '@/lib/fetch/api-route-helper';
import { backendFetch } from '@/lib/fetch/backend';

export async function PUT(request: Request) {
  const body = await request.json();
  return withAuth((token, headers) =>
    backendFetch('/{section}/{path}/status', token, { method: 'PUT', body, headers })
  );
}
```

---

## After Scaffolding

Run `/fetch-validate` to confirm compliance:

- [ ] Server actions use `/backend/{section}/{path}` URLs
- [ ] API routes import `backendFetch` from `@/lib/fetch/backend`
- [ ] GET handlers use `(token)` callback
- [ ] Mutation handlers use `(token, headers)` with `{ headers }` passed through
- [ ] No `backendGet/Post/Put/Delete` helpers
- [ ] No `fetchClient` usage

## Automated Script

For quick scaffolding, use the helper script from `src/frontend/`:

```bash
cd src/frontend/

# Generate API routes
python3 /path/to/fullstack-agents/skills/fetch-architecture/scripts/helper.py generate <entity> <section>

# Generate server actions
python3 /path/to/fullstack-agents/skills/fetch-architecture/scripts/helper.py actions <entity> <section>
```
