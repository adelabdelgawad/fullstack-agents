# Simple Fetching Pattern (Strategy A)

Default data fetching pattern using React state. No automatic revalidation.

## When to Use

Use this pattern when:
- Data only changes via user actions
- Settings/configuration pages
- Admin CRUD tables
- Forms and profile pages
- Single-user workflows

**Key principle:** The UI updates from server responses to mutations, not from polling or background refetch. Which update each mutation gets (patch, list refetch, `router.refresh()`) follows [data-freshness.md](data-freshness.md).

## Pattern Overview

```
page.tsx (Server Component)
├── Fetch initial data via server action
├── Pass initialData to client component
└── No "use client" directive

table.tsx (Client Component)
├── useState for local data management
├── updateItems() from server responses
├── Manual refresh function (optional)
└── No SWR dependency
```

## Complete Table Component Example

```tsx
// _components/table/items-table.tsx
"use client";

import { useState, useCallback, useMemo, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useQueryState, parseAsInteger } from "nuqs";
import api from "@/lib/fetch/client";
import { DataTable } from "@/components/data-table";
import { ItemsActionsProvider } from "../../context/items-actions-context";
import { ItemsTableBody } from "./items-table-body";
import type { ItemsResponse, Item, CreateItemData } from "@/types/items";

interface ItemsTableProps {
  initialData: ItemsResponse | null;
}

interface ActionResult {
  success: boolean;
  message?: string;
  error?: string;
  data?: Item;
}

export default function ItemsTable({ initialData }: ItemsTableProps) {
  // URL state management
  const [page, setPage] = useQueryState("page", parseAsInteger.withDefault(1));
  const [limit] = useQueryState("limit", parseAsInteger.withDefault(10));
  const searchParams = useSearchParams();
  const search = searchParams?.get("search") || "";
  const status = searchParams?.get("is_active") || "";

  // Local state (no SWR)
  const [data, setData] = useState<ItemsResponse | null>(initialData);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [updatingIds, setUpdatingIds] = useState<Set<string>>(new Set());

  // Build API URL from params
  const apiUrl = useMemo(() => {
    const params = new URLSearchParams();
    params.append("skip", ((page - 1) * limit).toString());
    params.append("limit", limit.toString());
    if (search) params.append("search", search);
    if (status) params.append("is_active", status);
    return `/api/setting/items?${params.toString()}`;
  }, [page, limit, search, status]);

  // List coordinator: every trigger reloads through here; a superseded response is dropped.
  const requestSeq = useRef(0);
  const refresh = useCallback(async () => {
    const seq = ++requestSeq.current;
    setIsLoading(true);
    setError(null);
    try {
      const fresh = await api.get<ItemsResponse>(apiUrl);
      if (seq === requestSeq.current) setData(fresh);
    } catch (err) {
      if (seq === requestSeq.current) setError(err as Error);
    } finally {
      if (seq === requestSeq.current) setIsLoading(false);
    }
  }, [apiUrl]);

  // Patch rows from the server response; counts and membership stay server-owned.
  const updateItems = useCallback((serverResponse: Item[]) => {
    setData(current => {
      if (!current) return current;
      const responseMap = new Map(serverResponse.map(i => [i.id, i]));
      return {
        ...current,
        items: current.items.map(item => responseMap.get(item.id) ?? item),
      };
    });
  }, []);

  // Toggle status action
  const onToggleStatus = useCallback(
    async (id: string, isActive: boolean): Promise<ActionResult> => {
      setUpdatingIds(prev => new Set(prev).add(id));
      try {
        const updated = await api.put<Item>(
          `/api/setting/items/${id}/status`,
          { is_active: isActive }
        );
        updateItems([updated]);
        // is_active is filtered and counted: membership and counts come from the server.
        void refresh();
        return {
          success: true,
          message: `Item ${isActive ? "enabled" : "disabled"}`,
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : "Failed to update status",
        };
      } finally {
        setUpdatingIds(prev => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }
    },
    [updateItems, refresh]
  );

  // Update action
  const onUpdate = useCallback(
    async (id: string, payload: Partial<Item>): Promise<ActionResult> => {
      setUpdatingIds(prev => new Set(prev).add(id));
      try {
        const updated = await api.put<Item>(
          `/api/setting/items/${id}`,
          payload
        );
        updateItems([updated]);
        // Fields this list filters, sorts or counts on can move the row: reload the list.
        if ("is_active" in payload || "name" in payload) void refresh();
        return { success: true, data: updated };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : "Failed to update",
        };
      } finally {
        setUpdatingIds(prev => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }
    },
    [updateItems, refresh]
  );

  // Create action
  const onCreate = useCallback(
    async (payload: CreateItemData): Promise<ActionResult> => {
      try {
        const created = await api.post<Item>(
          `/api/setting/items`,
          payload
        );
        // The server decides the new row's page, position and the counts.
        await refresh();
        return { success: true, data: created };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : "Failed to create",
        };
      }
    },
    [refresh]
  );

  // Delete action
  const onDelete = useCallback(
    async (id: string): Promise<ActionResult> => {
      setUpdatingIds(prev => new Set(prev).add(id));
      try {
        await api.delete(`/api/setting/items/${id}`);
        // A delete shifts the next page's first row onto this page and changes counts.
        await refresh();
        return { success: true };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : "Failed to delete",
        };
      } finally {
        setUpdatingIds(prev => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }
    },
    [refresh]
  );

  // Bulk status update
  const onBulkUpdateStatus = useCallback(
    async (ids: string[], isActive: boolean): Promise<ActionResult> => {
      ids.forEach(id => setUpdatingIds(prev => new Set(prev).add(id)));
      try {
        const updated = await api.post<Item[]>(
          `/api/setting/items/status`,
          { ids, is_active: isActive }
        );
        updateItems(updated);
        void refresh();
        return {
          success: true,
          message: `${ids.length} items ${isActive ? "enabled" : "disabled"}`,
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : "Failed to update",
        };
      } finally {
        ids.forEach(id =>
          setUpdatingIds(prev => {
            const next = new Set(prev);
            next.delete(id);
            return next;
          })
        );
      }
    },
    [updateItems, refresh]
  );

  // Actions object for context
  const actions = useMemo(
    () => ({
      onToggleStatus,
      onUpdate,
      onCreate,
      onDelete,
      onBulkUpdateStatus,
      onRefresh: refresh,
      updateItems,
    }),
    [onToggleStatus, onUpdate, onCreate, onDelete, onBulkUpdateStatus, refresh, updateItems]
  );

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <p className="text-destructive mb-4">Failed to load data</p>
        <button onClick={refresh} className="text-primary hover:underline">
          Try again
        </button>
      </div>
    );
  }

  return (
    <ItemsActionsProvider actions={actions}>
      <ItemsTableBody
        data={data}
        isLoading={isLoading}
        updatingIds={updatingIds}
        page={page}
        limit={limit}
        onPageChange={setPage}
      />
    </ItemsActionsProvider>
  );
}
```

## Context Pattern for Simple Fetching

```tsx
// context/items-actions-context.tsx
"use client";

import { createContext, useContext, ReactNode } from "react";
import type { Item, CreateItemData } from "@/types/items";

interface ActionResult {
  success: boolean;
  message?: string;
  error?: string;
  data?: Item;
}

interface ItemsActionsContextType {
  onToggleStatus: (id: string, isActive: boolean) => Promise<ActionResult>;
  onUpdate: (id: string, payload: Partial<Item>) => Promise<ActionResult>;
  onCreate: (payload: CreateItemData) => Promise<ActionResult>;
  onDelete: (id: string) => Promise<ActionResult>;
  onBulkUpdateStatus: (ids: string[], isActive: boolean) => Promise<ActionResult>;
  onRefresh: () => Promise<void>;
  updateItems: (items: Item[]) => void;
}

const ItemsActionsContext = createContext<ItemsActionsContextType | null>(null);

interface ProviderProps {
  children: ReactNode;
  actions: ItemsActionsContextType;
}

export function ItemsActionsProvider({ children, actions }: ProviderProps) {
  return (
    <ItemsActionsContext.Provider value={actions}>
      {children}
    </ItemsActionsContext.Provider>
  );
}

export function useItemsActions() {
  const context = useContext(ItemsActionsContext);
  if (!context) {
    throw new Error("useItemsActions must be used within ItemsActionsProvider");
  }
  return context;
}
```

## Page Component (Server)

```tsx
// page.tsx
import { getItems } from "@/lib/actions/items.actions";
import ItemsTable from "./_components/table/items-table";

export default async function ItemsPage({
  searchParams,
}: {
  searchParams: Promise<{
    is_active?: string;
    search?: string;
    page?: string;
    limit?: string;
  }>;
}) {
  const params = await searchParams;
  const pageNumber = Number(params.page) || 1;
  const limitNumber = Number(params.limit) || 10;
  const skip = (pageNumber - 1) * limitNumber;

  const data = await getItems(limitNumber, skip, {
    is_active: params.is_active,
    search: params.search,
  });

  return <ItemsTable initialData={data} />;
}
```

## Key Differences from SWR Pattern

| Aspect | Simple (Strategy A) | SWR (Strategy B) |
|--------|---------------------|------------------|
| Import | `useState` from React | `useSWR` from swr |
| Initial state | `useState(initialData)` | `useSWR({ fallbackData })` |
| Update function | `setData(...)` | `mutate(...)` |
| Auto refresh | No | Configurable |
| Caching | Manual (component state) | Built-in |
| Deduplication | None | Built-in |
| Loading state | Manual `isLoading` state | `isLoading` from hook |
| Error state | Manual `error` state | `error` from hook |

## When URL Params Change

With Strategy A, you need to manually refetch when URL parameters change:

```tsx
import { useEffect } from "react";

// Refetch when URL params change (pagination, filters)
useEffect(() => {
  refresh();
}, [apiUrl]); // Only if you want auto-refetch on URL change
```

Or let the page component handle it via SSR (recommended):
- When URL changes, Next.js re-renders the server component
- Server fetches new data
- Client receives new `initialData` prop
- `useState(initialData)` does **not** reset on a new prop: sync it (`useEffect(() => setData(initialData), [initialData])`) or key the table by the query string, or the old filter's rows stay on screen

## Checklist

- [ ] No SWR import or dependency
- [ ] `useState` for data management
- [ ] `updateItems()` patches rows from the server response and never recomputes counts
- [ ] Create, delete and edits of filtered/sorted/counted fields reload the list through `refresh()`
- [ ] `refresh()` drops superseded responses
- [ ] [data-freshness.md](data-freshness.md) checklist passes
- [ ] Loading state tracked manually
- [ ] Error state tracked manually
