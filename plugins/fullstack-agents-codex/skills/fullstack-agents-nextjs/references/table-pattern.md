# Table Pattern Reference

Client-side table component with SWR data management and server-response updates.

## Key Principles

1. **"use client"** - Table is a client component
2. **SWR with fallbackData** - SSR data as initial cache
3. **Server response updates** - NOT optimistic updates; which update each mutation gets follows [data-freshness.md](data-freshness.md)
4. **Context provider** - Pass actions to children

## Basic Table Structure

```tsx
// app/(pages)/setting/items/_components/table/items-table.tsx
"use client";

import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { api } from "@/lib/fetch/client";
import { ItemsActionsProvider } from "../../context/items-actions-context";
import ItemsTableBody from "./items-table-body";
import { StatusPanel } from "../sidebar/status-panel";
import { Pagination } from "@/components/data-table/table/pagination";
import LoadingSkeleton from "@/components/loading-skelton";

interface ItemsTableProps {
  initialData: ItemsResponse | null;
}

// SWR fetcher
const fetcher = async (url: string) => {
  return api.get(url);
};

export default function ItemsTable({ initialData }: ItemsTableProps) {
  const searchParams = useSearchParams();

  // Read URL parameters
  const page = Number(searchParams?.get("page") || "1");
  const limit = Number(searchParams?.get("limit") || "10");
  const search = searchParams?.get("search") || "";
  const isActive = searchParams?.get("is_active") || "";

  // Build API URL with current filters
  const params = new URLSearchParams();
  params.append("skip", ((page - 1) * limit).toString());
  params.append("limit", limit.toString());
  if (search) params.append("search", search);
  if (isActive) params.append("is_active", isActive);

  const apiUrl = `/api/setting/items?${params.toString()}`;

  // Fields this list filters, sorts or counts on.
  const LIST_FIELDS = ["isActive", "name"] as const;

  // SWR hook with optimized configuration
  const { data, mutate, isLoading, error } = useSWR<ItemsResponse>(
    apiUrl,
    fetcher,
    {
      fallbackData: initialData ?? undefined,  // SSR data as initial
      keepPreviousData: true,                   // Smooth transitions
      revalidateOnMount: false,                 // Trust SSR data
      revalidateIfStale: true,                  // Refetch if stale
      revalidateOnFocus: false,                 // Don't refetch on focus
      revalidateOnReconnect: false,             // Don't refetch on reconnect
    }
  );

  const items = data?.items ?? [];
  const activeCount = data?.activeCount ?? 0;
  const inactiveCount = data?.inactiveCount ?? 0;
  const totalItems = data?.total ?? 0;
  const totalPages = Math.ceil(totalItems / limit);

  /**
   * Update cache with server response (NOT optimistic)
   */
  const updateItems = async (serverResponse: Item[]) => {
    const currentData = data;
    if (!currentData) return;

    // Map server response by ID for quick lookup
    const responseMap = new Map(serverResponse.map(i => [i.id, i]));

    // Replace items with server response
    const updatedList = currentData.items.map(item =>
      responseMap.has(item.id) ? responseMap.get(item.id)! : item
    );

    // Counts and membership stay server-owned; only the rows are patched.
    await mutate({ ...currentData, items: updatedList }, { revalidate: false });
  };

  // Define actions for context
  const actions = {
    onToggleStatus: async (id: string, isActive: boolean) => {
      try {
        const updated = await api.put<Item>(
          `/setting/items/${id}/status`,
          { is_active: isActive }
        );
        await updateItems([updated]);
        // isActive is filtered and counted: revalidate the list query.
        void mutate();
        return { success: true, message: `Item ${isActive ? "enabled" : "disabled"}` };
      } catch (error) {
        return { success: false, error: "Failed to update status" };
      }
    },

    onUpdate: async (id: string, updateData: Partial<Item>) => {
      try {
        const updated = await api.put<Item>(
          `/setting/items/${id}`,
          updateData
        );
        await updateItems([updated]);
        // An edit to a field this list filters, sorts or counts on can move the row.
        if (LIST_FIELDS.some(field => field in updateData)) void mutate();
        return { success: true, message: "Item updated", data: updated };
      } catch (error) {
        return { success: false, error: "Failed to update item" };
      }
    },

    onBulkUpdateStatus: async (ids: string[], isActive: boolean) => {
      try {
        const result = await api.put<{ updatedItems: Item[] }>(
          `/setting/items/status`,
          { ids, is_active: isActive }
        );
        if (result.updatedItems?.length > 0) {
          await updateItems(result.updatedItems);
        }
        void mutate();
        return { success: true, message: `Updated ${ids.length} items` };
      } catch (error) {
        return { success: false, error: "Failed to update items" };
      }
    },

    onRefresh: async () => {
      await mutate();
      return { success: true, message: "Refreshed" };
    },

    updateItems,
  };

  // Error notification
  const errorNotification = error ? (
    <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-sm mb-2">
      <div className="font-medium">Failed to load items</div>
      <button onClick={() => mutate()} className="mt-2 px-3 py-1 bg-red-600 text-white rounded-sm">
        Retry
      </button>
    </div>
  ) : null;

  return (
    <ItemsActionsProvider actions={actions}>
      <div className="relative h-full flex bg-muted min-h-0 p-1">
        {/* Loading Overlay */}
        {isLoading && <LoadingSkeleton />}

        {/* Status Panel */}
        <StatusPanel
          total={activeCount + inactiveCount}
          activeCount={activeCount}
          inactiveCount={inactiveCount}
        />

        {/* Main Content */}
        <div className="h-full flex flex-col min-h-0 ml-2 space-y-2">
          {errorNotification}

          {/* Table */}
          <div className="flex-1 min-h-0 flex flex-col">
            <ItemsTableBody
              items={items}
              page={page}
              mutate={mutate}
              updateItems={updateItems}
            />
          </div>

          {/* Pagination */}
          <div className="shrink-0 bg-card border-t border-border">
            <Pagination
              currentPage={page}
              totalPages={totalPages}
              pageSize={limit}
              totalItems={totalItems}
            />
          </div>
        </div>
      </div>
    </ItemsActionsProvider>
  );
}
```

## SWR Configuration Options

```tsx
const { data, mutate, isLoading, error } = useSWR(
  apiUrl,
  fetcher,
  {
    // SSR hydration
    fallbackData: initialData,

    // Smooth pagination/filter transitions
    keepPreviousData: true,

    // Trust SSR data on first render
    revalidateOnMount: false,

    // Refetch if data is stale
    revalidateIfStale: true,

    // Reduce unnecessary API calls
    revalidateOnFocus: false,
    revalidateOnReconnect: false,

    // Optional: dedupe interval (2000 ms is SWR's default; raise it only for data that changes rarely)
    dedupingInterval: 2000,

    // Optional: error retry
    errorRetryCount: 3,
    errorRetryInterval: 1000,
  }
);
```

## Server Response Update Pattern

```tsx
/**
 * CRITICAL: Always use server response, never optimistic updates
 * This ensures cache matches backend state exactly
 */
const updateItems = async (serverResponse: Item[]) => {
  const currentData = data;
  if (!currentData) return;

  // Create lookup map from server response
  const responseMap = new Map(serverResponse.map(i => [i.id, i]));

  // Replace items in list with server versions
  const updatedList = currentData.items.map(item =>
    responseMap.has(item.id) ? responseMap.get(item.id)! : item
  );

  // Update cache WITHOUT revalidation (we have fresh data)
  await mutate(
    { ...currentData, items: updatedList },
    { revalidate: false }
  );
};

// Usage in action:
const handleUpdate = async (id: string, data: UpdateData) => {
  // Call API and get server response
  const updated = await api.put<Item>(`/items/${id}`, data);

  // Update cache with server response
  await updateItems([updated]);
};
```

## Creating and Deleting Items

A created row's page, position and the aggregate counts are decided by the server's filter, sort
and pagination, and a delete pulls the next page's first row onto this one. Never splice the row
into the cached page or adjust `total` locally: revalidate the list query.

```tsx
const addItem = async (newItem: ItemCreate) => {
  try {
    const created = await api.post<Item>('/setting/items', newItem);
    await mutate();
    return { success: true, data: created };
  } catch (error) {
    return { success: false, error: "Failed to create item" };
  }
};

const deleteItem = async (id: string) => {
  try {
    await api.delete(`/setting/items/${id}`);
    await mutate();
    return { success: true };
  } catch (error) {
    return { success: false, error: "Failed to delete item" };
  }
};
```

## Key Points

1. **"use client"** - Required for hooks and interactivity
2. **SWR fallbackData** - Use SSR data for instant render
3. **Server response updates** - Never use optimistic updates
4. **Context for actions** - Pass handlers to child components
5. **keepPreviousData** - Smooth transitions between pages
6. **revalidateOnMount: false** - Trust server data on initial load
7. **Error handling** - Show inline errors, provide retry
