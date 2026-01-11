# Table Component Pattern

The main table component is a "use client" component that wraps everything with SWR and context.

## Full Pattern

```tsx
// _components/table/[entity]-table.tsx
"use client";

import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import type { [Entity]ListResponse, [Entity]Response } from "@/types/[entity]";
import { StatusPanel } from "../sidebar/status-panel";
import [Entity]TableBody from "./[entity]-table-body";
import LoadingSkeleton from "@/components/loading-skeleton";
import { fetchClient } from "@/lib/fetch/client";
import { [Entity]ActionsProvider } from "../../context/[entity]-actions-context";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Pagination } from "@/components/data-table/table/pagination";

interface [Entity]TableProps {
  initialData: [Entity]ListResponse | null;
  // Add any additional props like dropdown options
}

/**
 * Fetcher function for SWR - uses fetch client for authentication
 */
const fetcher = async (url: string) => {
  const response = await fetchClient.get(url);
  return response.data;
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

  // SWR hook with SSR hydration
  const { data, mutate, isLoading, error } = useSWR<[Entity]ListResponse>(
    apiUrl,
    fetcher,
    {
      // Use server-side data as initial cache
      fallbackData: initialData ?? undefined,
      // Smooth transitions when changing filters/pagination
      keepPreviousData: true,
      // Don't refetch on mount (we have SSR data)
      revalidateOnMount: false,
      // Refetch if data is stale
      revalidateIfStale: true,
      // Disable automatic refetch on focus (reduces API calls)
      revalidateOnFocus: false,
      // Disable automatic refetch on reconnect
      revalidateOnReconnect: false,
    }
  );

  const items = data?.items ?? [];
  const activeCount = data?.activeCount ?? 0;
  const inactiveCount = data?.inactiveCount ?? 0;

  /**
   * Updates SWR cache with backend response data (NOT optimistic)
   * - Takes the actual server response from PUT/POST
   * - Replaces matching items in cache with server data
   * - Recalculates counts from the updated list
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

    // Recalculate counts from updated list
    const newActiveCount = updatedList.filter((item) => item.isActive).length;
    const newInactiveCount = updatedList.filter((item) => !item.isActive).length;

    // Update cache with server data
    await mutate(
      {
        ...currentData,
        items: updatedList,
        activeCount: newActiveCount,
        inactiveCount: newInactiveCount,
      },
      { revalidate: false }
    );
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
        const { data: updated } = await fetchClient.put<[Entity]Response>(
          `/[section]/[entity]/${id}/status`,
          { entity_id: id, is_active: isActive }
        );
        await updateItems([updated]);
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
        const { data: updated } = await fetchClient.put<[Entity]Response>(
          `/[section]/[entity]/${id}`,
          payload
        );
        await updateItems([updated]);
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
        const { data: result } = await fetchClient.put<{
          updatedItems: [Entity]Response[];
        }>(`/[section]/[entity]/status`, {
          entity_ids: ids,
          is_active: isActive,
        });

        if (result.updatedItems?.length > 0) {
          await updateItems(result.updatedItems);
        }

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

1. **SSR Hydration**: `fallbackData: initialData` ensures SSR data is used immediately
2. **URL-Driven State**: Read from `searchParams`, build `apiUrl` dynamically
3. **Server Response Updates**: `updateItems()` uses actual API response, not optimistic
4. **Context Provider**: Wraps entire table to share actions with children
5. **Error Handling**: Inline error banner with retry button
6. **Loading State**: Skeleton overlay during transitions
