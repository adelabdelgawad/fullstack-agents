# Table Component Pattern

The main table component is a "use client" component that manages data and wraps with context.

**Choose based on data fetching strategy:**
- **Strategy A (Default)**: Simple state with `useState` - for most CRUD tables.
- **Strategy B (When Justified)**: SWR with `useSWR` - for dashboards/multi-user scenarios.

See [data-fetching-strategy.md](../../nextjs/references/data-fetching-strategy.md) for the decision framework and [data-freshness.md](../../nextjs/references/data-freshness.md) for which update each mutation gets. In both strategies below, row patches leave counts to the server, and toggles, bulk updates and edits of filtered, sorted or counted fields (`LIST_FIELDS`) reload the list; add create and delete handlers the same way.

**Reference implementations in the actual codebase:**
- `src/frontend/app/(pages)/setting/users/_components/table/users-table.tsx` (Strategy A)
- `src/frontend/app/(pages)/setting/roles/_components/table/roles-table.tsx` (Strategy A)

---

## Strategy A: Simple Fetching (Default)

Use this for most CRUD/admin tables where data changes only via user actions.

```tsx
// _components/table/[entity]-table.tsx
"use client";

import { useState, useCallback, useMemo, useRef, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import type { [Entity]ListResponse, [Entity]Response } from "@/lib/types/api/[entity]";
import { StatusPanel } from "../sidebar/status-panel";
import [Entity]TableBody from "./[entity]-table-body";
import LoadingSkeleton from "@/components/loading-skeleton";
import { api } from "@/lib/fetch/client";
import { [Entity]ActionsProvider } from "../../context/[entity]-actions-context";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Pagination } from "@/components/data-table/table/pagination";

interface [Entity]TableProps {
  initialData: [Entity]ListResponse | null;
}

function [Entity]Table({ initialData }: [Entity]TableProps) {
  const searchParams = useSearchParams();

  // Read URL parameters
  const page = Number(searchParams?.get("page") || "1");
  const limit = Number(searchParams?.get("limit") || "10");
  const filter = searchParams?.get("filter") || "";
  const isActive = searchParams?.get("is_active") || "";

  // Build API URL
  const apiUrl = useMemo(() => {
    const params = new URLSearchParams();
    params.append("skip", ((page - 1) * limit).toString());
    params.append("limit", limit.toString());
    if (filter) params.append("search", filter);
    if (isActive) params.append("is_active", isActive);
    return `/[section]/[entity]?${params.toString()}`;
  }, [page, limit, filter, isActive]);

  // Local state (no SWR)
  // Fields this list filters, sorts or counts on: an edit to one of them can move the row.
  const LIST_FIELDS = ["isActive", "name"] as const;

  const [data, setData] = useState<[Entity]ListResponse | null>(initialData);
  // A new server render (URL change) replaces local state; useState alone would keep the old rows.
  useEffect(() => setData(initialData), [initialData]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const items = data?.items ?? [];
  const activeCount = data?.activeCount ?? 0;
  const inactiveCount = data?.inactiveCount ?? 0;

  // List coordinator: every trigger reloads through here; the newest request wins.
  const requestSeq = useRef(0);
  const load = useCallback(async (background: boolean) => {
    const seq = ++requestSeq.current;
    if (!background) setIsLoading(true);
    setError(null);
    try {
      const response = await api.get<[Entity]ListResponse>(apiUrl);
      if (seq === requestSeq.current) setData(response);
    } catch (err) {
      if (seq === requestSeq.current) setError(err as Error);
    } finally {
      if (seq === requestSeq.current) setIsLoading(false);
    }
  }, [apiUrl]);
  // Refresh button shows the loading overlay; post-mutation reloads run in the background.
  const refresh = useCallback(() => load(false), [load]);
  const revalidate = useCallback(() => load(true), [load]);

  // Update items from server response
  const updateItems = useCallback((serverResponse: [Entity]Response[]) => {
    setData(current => {
      if (!current) return current;
      const responseMap = new Map(serverResponse.map(item => [item.id, item]));
      const updatedList = current.items.map(item =>
        responseMap.has(item.id) ? responseMap.get(item.id)! : item
      );
      // Counts and membership stay server-owned; only the rows are patched.
      return { ...current, items: updatedList };
    });
  }, []);

  const totalItems = data?.total ?? 0;
  const totalPages = Math.ceil(totalItems / limit);

  // Error notification
  const errorNotification = error ? (
    <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-sm mb-2 flex items-center justify-between">
      <div>
        <div className="font-medium">Failed to load data</div>
        <div className="text-sm">{error.message}</div>
      </div>
      <button
        onClick={refresh}
        className="px-3 py-1 bg-red-600 text-white rounded-sm hover:bg-red-700 text-sm"
      >
        Retry
      </button>
    </div>
  ) : null;

  // Actions for context
  const actions = useMemo(() => ({
    onToggleStatus: async (id: string, isActive: boolean) => {
      try {
        const updated = await api.put<[Entity]Response>(
          `/[section]/[entity]/${id}/status`,
          { entity_id: id, is_active: isActive }
        );
        updateItems([updated]);
        // isActive is filtered and counted: reload membership and counts.
        void revalidate();
        return { success: true, message: `Item ${isActive ? "enabled" : "disabled"}`, data: updated };
      } catch (error: unknown) {
        const err = error as { data?: { detail?: string }; message?: string };
        return { success: false, error: err.data?.detail || err.message || "Failed to update" };
      }
    },

    onUpdate: async (id: string, payload: Record<string, unknown>) => {
      try {
        const updated = await api.put<[Entity]Response>(
          `/[section]/[entity]/${id}`,
          payload
        );
        updateItems([updated]);
        // An edit to a field this list filters, sorts or counts on can move the row.
        if (LIST_FIELDS.some((field) => field in payload)) void revalidate();
        return { success: true, message: "Updated", data: updated };
      } catch (error: unknown) {
        const err = error as { data?: { detail?: string }; message?: string };
        return { success: false, error: err.data?.detail || err.message || "Failed to update" };
      }
    },

    onBulkUpdateStatus: async (ids: string[], isActive: boolean) => {
      try {
        const result = await api.put<{ updatedItems: [Entity]Response[] }>(
          `/[section]/[entity]/status`,
          { entity_ids: ids, is_active: isActive }
        );
        if (result.updatedItems?.length > 0) {
          updateItems(result.updatedItems);
        }
        void revalidate();
        return { success: true, message: `Updated ${ids.length} items`, data: result.updatedItems };
      } catch (error: unknown) {
        const err = error as { data?: { detail?: string }; message?: string };
        return { success: false, error: err.data?.detail || err.message || "Failed to update" };
      }
    },

    onFetchEntity: async (id: string) => {
      try {
        const data = await api.get<[Entity]Response>(
          `/[section]/[entity]/${id}`
        );
        return { success: true, data };
      } catch (error: unknown) {
        const err = error as { data?: { detail?: string }; message?: string };
        return { success: false, error: err.data?.detail || err.message || "Failed to load" };
      }
    },

    onRefresh: refresh,
    updateItems,
  }), [updateItems, refresh, revalidate]);

  return (
    <[Entity]ActionsProvider actions={actions}>
      <div className="relative h-full flex bg-muted min-h-0 p-1">
        {isLoading && <LoadingSkeleton />}
        <StatusPanel total={activeCount + inactiveCount} activeCount={activeCount} inactiveCount={inactiveCount} />
        <ErrorBoundary>
          <div className="h-full flex flex-col min-h-0 ml-2 space-y-2">
            {errorNotification}
            <div className="flex-1 min-h-0 flex flex-col">
              <[Entity]TableBody items={items} updateItems={updateItems} onRefresh={refresh} />
            </div>
            <div className="shrink-0 bg-card border-t border-border">
              <Pagination currentPage={page} totalPages={totalPages} pageSize={limit} totalItems={totalItems} />
            </div>
          </div>
        </ErrorBoundary>
      </div>
    </[Entity]ActionsProvider>
  );
}

export default [Entity]Table;
```

---

## Strategy B: SWR Fetching (When Justified)

Use this for dashboards, multi-user editing, or when external sources update data.

**Requires justification comment!**

```tsx
// _components/table/[entity]-table.tsx
"use client";

import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import type { [Entity]ListResponse, [Entity]Response } from "@/lib/types/api/[entity]";
import { StatusPanel } from "../sidebar/status-panel";
import [Entity]TableBody from "./[entity]-table-body";
import LoadingSkeleton from "@/components/loading-skeleton";
import { api } from "@/lib/fetch/client";
import { [Entity]ActionsProvider } from "../../context/[entity]-actions-context";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Pagination } from "@/components/data-table/table/pagination";

interface [Entity]TableProps {
  initialData: [Entity]ListResponse | null;
}

const fetcher = async (url: string) => {
  return api.get(url);
};

function [Entity]Table({ initialData }: [Entity]TableProps) {
  const searchParams = useSearchParams();

  // Read URL parameters
  const page = Number(searchParams?.get("page") || "1");
  const limit = Number(searchParams?.get("limit") || "10");
  const filter = searchParams?.get("filter") || "";
  const isActive = searchParams?.get("is_active") || "";

  // Build API URL with current filters
  const params = new URLSearchParams();
  params.append("skip", ((page - 1) * limit).toString());
  params.append("limit", limit.toString());
  if (filter) params.append("search", filter);
  if (isActive) params.append("is_active", isActive);

  const apiUrl = `/[section]/[entity]?${params.toString()}`;

  // Fields this list filters, sorts or counts on: an edit to one of them can move the row.
  const LIST_FIELDS = ["isActive", "name"] as const;

  /**
   * SWR JUSTIFICATION:
   * - Reason: [Document why revalidation is needed - e.g., "Dashboard updated by background jobs"]
   * - Trigger: [Interval / Focus / Manual]
   * - Interval: [N seconds, if applicable]
   */
  const { data, mutate, isLoading, error } = useSWR<[Entity]ListResponse>(
    apiUrl,
    fetcher,
    {
      fallbackData: initialData ?? undefined,
      keepPreviousData: true,
      revalidateOnMount: false,
      revalidateIfStale: true,
      revalidateOnFocus: false,  // Set true only if justified
      revalidateOnReconnect: false,
      // refreshInterval: 30000,  // Uncomment if interval-based refresh is justified
    }
  );

  const items = data?.items ?? [];
  const activeCount = data?.activeCount ?? 0;
  const inactiveCount = data?.inactiveCount ?? 0;

  /**
   * Updates SWR cache with backend response data (NOT optimistic)
   * - Takes the actual server response from PUT/POST
   * - Replaces matching items in cache with server data
   * - Leaves counts and membership to the server (revalidate for those)
   */
  const updateItems = async (serverResponse: [Entity]Response[]) => {
    const currentData = data;
    if (!currentData) return;

    // Map server response by ID for quick lookup
    const responseMap = new Map(serverResponse.map((item) => [item.id, item]));

    // Replace items with server response (NOT merge - use server data directly)
    const updatedList = currentData.items.map((item) =>
      responseMap.has(item.id) ? responseMap.get(item.id)! : item
    );

    await mutate({ ...currentData, items: updatedList }, { revalidate: false });
  };

  const totalItems = data?.total ?? 0;
  const totalPages = Math.ceil(totalItems / limit);

  // Error notification (inline, doesn't block rendering)
  const errorNotification = error ? (
    <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-sm mb-2 flex items-center justify-between">
      <div>
        <div className="font-medium">Failed to load data</div>
        <div className="text-sm">{error.message}</div>
      </div>
      <button
        onClick={() => mutate()}
        className="px-3 py-1 bg-red-600 text-white rounded-sm hover:bg-red-700 text-sm"
      >
        Retry
      </button>
    </div>
  ) : null;

  // Define actions for the context provider
  const actions = {
    onToggleStatus: async (id: string, isActive: boolean) => {
      try {
        const updated = await api.put<[Entity]Response>(
          `/[section]/[entity]/${id}/status`,
          { entity_id: id, is_active: isActive }
        );
        await updateItems([updated]);
        // isActive is filtered and counted: revalidate the list query.
        void mutate();
        return {
          success: true,
          message: `Item ${isActive ? "enabled" : "disabled"} successfully`,
          data: updated,
        };
      } catch (error: unknown) {
        const err = error as { data?: { detail?: string }; message?: string };
        return {
          success: false,
          error: err.data?.detail || err.message || "Failed to update status",
        };
      }
    },

    onUpdate: async (id: string, payload: Record<string, unknown>) => {
      try {
        const updated = await api.put<[Entity]Response>(
          `/[section]/[entity]/${id}`,
          payload
        );
        await updateItems([updated]);
        if (LIST_FIELDS.some((field) => field in payload)) void mutate();
        return {
          success: true,
          message: "Updated successfully",
          data: updated,
        };
      } catch (error: unknown) {
        const err = error as { data?: { detail?: string }; message?: string };
        return {
          success: false,
          error: err.data?.detail || err.message || "Failed to update",
        };
      }
    },

    onBulkUpdateStatus: async (ids: string[], isActive: boolean) => {
      try {
        const result = await api.put<{
          updatedItems: [Entity]Response[];
        }>(`/[section]/[entity]/status`, {
          entity_ids: ids,
          is_active: isActive,
        });

        if (result.updatedItems?.length > 0) {
          await updateItems(result.updatedItems);
        }
        void mutate();

        return {
          success: true,
          message: `Successfully ${isActive ? "enabled" : "disabled"} ${ids.length} item(s)`,
          data: result.updatedItems,
        };
      } catch (error: unknown) {
        const err = error as { data?: { detail?: string }; message?: string };
        return {
          success: false,
          error: err.data?.detail || err.message || "Failed to update status",
        };
      }
    },

    onFetchEntity: async (id: string) => {
      try {
        const data = await api.get<[Entity]Response>(
          `/[section]/[entity]/${id}`
        );
        return { success: true, data };
      } catch (error: unknown) {
        const err = error as { data?: { detail?: string }; message?: string };
        return { success: false, error: err.data?.detail || err.message || "Failed to load" };
      }
    },

    onRefresh: async () => {
      await mutate();
      return { success: true, message: "Refreshed", data: null };
    },

    updateItems,
  };

  return (
    <[Entity]ActionsProvider actions={actions}>
      <div className="relative h-full flex bg-muted min-h-0 p-1">
        {/* Loading Overlay */}
        {isLoading && <LoadingSkeleton />}

        {/* Status Panel (Optional) */}
        <StatusPanel
          total={activeCount + inactiveCount}
          activeCount={activeCount}
          inactiveCount={inactiveCount}
        />

        {/* Main Content */}
        <ErrorBoundary>
          <div className="h-full flex flex-col min-h-0 ml-2 space-y-2">
            {/* Error Notification */}
            {errorNotification}

            {/* Table */}
            <div className="flex-1 min-h-0 flex flex-col">
              <[Entity]TableBody
                items={items}
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
        </ErrorBoundary>
      </div>
    </[Entity]ActionsProvider>
  );
}

export default [Entity]Table;
```

## Key Points

### Common to Both Strategies
1. **SSR Initial Data**: Both receive `initialData` from server component
2. **URL-Driven State**: Read from `searchParams`, build `apiUrl` dynamically
3. **Server Response Updates**: `updateItems()` uses actual API response, not optimistic
4. **Context Provider**: Wraps entire table to share actions with children
5. **Error Handling**: Inline error banner with retry button

### Strategy A (Simple)
- Uses `useState` for local data management
- One `refresh()` list coordinator that drops superseded responses
- No automatic revalidation
- Lower complexity, no SWR dependency

### Strategy B (SWR)
- Requires **justification comment** explaining why SWR is needed
- Uses `useSWR` with configurable revalidation
- Automatic refresh (interval, focus, reconnect) is opt-in per dataset with its freshness requirement named ([data-freshness.md](../../nextjs/references/data-freshness.md) §2)
- Built-in caching and deduplication
