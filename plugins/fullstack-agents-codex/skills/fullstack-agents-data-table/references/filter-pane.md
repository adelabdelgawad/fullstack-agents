# Filter Pane (collapsible, active-count badge, clear-all)

`DynamicTableBar` is a flat 3-section toolbar. The **filter pane** (`DataTableController`)
wraps it with a collapsible region that holds several faceted filters at once, plus
the cross-cutting controls that make multi-dimension filtering usable:

- A **filters toggle** with an **active-filter-count badge** (how many dimensions
  are set) and an inline **clear-all (×)**.
- A **collapsible panel** that opens to reveal a grid of faceted filters
  (one per dimension — see [faceted-filters.md](faceted-filters.md)).
- An optional **selection-actions row** that appears above the controls when rows
  are selected (bulk enable/disable, etc.).
- It defaults to **open** when any filter is already active (deep-linked URL).

Use the filter pane when a table has **2+ filter dimensions** or any faceted
filter. For a single binary `is_active` filter, the flat `DynamicTableBar` +
`StatusBadgeFilter` is enough.

## Hook: `hooks/use-url-filter-count.ts`

Computes the active-filter count and a reset handler from a fixed set of URL keys.
This is the single source of truth for "how many filters are on" and "clear them".

```tsx
"use client";

import { useCallback } from "react";
import { useSearchParams, usePathname, useRouter } from "next/navigation";

export function useUrlFilterCount(keys: readonly string[]): {
  activeFilterCount: number;
  handleReset: () => void;
} {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();

  const activeFilterCount = keys.filter((k) => {
    const value = searchParams?.get(k);
    return value !== null && value !== undefined && value.trim() !== "";
  }).length;

  const handleReset = useCallback(() => {
    const params = new URLSearchParams(searchParams?.toString() || "");
    for (const k of keys) { params.delete(k); }
    params.delete("page"); // reset pagination when clearing filters
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
  }, [searchParams, pathname, router, keys]);

  return { activeFilterCount, handleReset };
}
```

## Component: `components/data-table/table/data-table-controller.tsx`

```tsx
"use client";

import React, { ReactNode, useId, useState } from "react";
import { SlidersHorizontal, X } from "lucide-react";
import { DynamicTableBar } from "./data-table-bar";
import { Button } from "@/components/ui/button";

interface DataTableControllerI18n {
  toggle: string;
  showFilters: string;
  hideFilters: string;
  reset?: string;
}

interface DataTableControllerProps {
  left?: ReactNode;
  /** Pass a node to append the filters toggle after it, or a render fn that
   *  receives the toggle node and places it manually. */
  right?: ReactNode | ((toggle: ReactNode) => ReactNode);
  filters?: ReactNode;
  activeFilterCount?: number;
  defaultOpen?: boolean;
  hasSelection?: boolean;
  selectionInfo?: ReactNode;
  selectionActions?: ReactNode;
  onReset?: () => void;
  i18n: DataTableControllerI18n;
}

export const DataTableController: React.FC<DataTableControllerProps> = ({
  left,
  right,
  filters,
  activeFilterCount = 0,
  defaultOpen = false,
  hasSelection = false,
  selectionInfo,
  selectionActions,
  onReset,
  i18n,
}) => {
  const panelId = useId();
  const [open, setOpen] = useState<boolean>(defaultOpen || activeFilterCount > 0);

  const toggleButton = filters ? (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="h-9 gap-1"
      aria-expanded={open}
      aria-controls={panelId}
      onClick={() => setOpen((v) => !v)}
      title={open ? i18n.hideFilters : i18n.showFilters}
    >
      <SlidersHorizontal className="size-4" />
      <span>{i18n.toggle}</span>
      {activeFilterCount > 0 && (
        <span className="ms-1 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-[11px] font-medium text-primary-foreground tabular-nums">
          {activeFilterCount}
        </span>
      )}
      {activeFilterCount > 0 && onReset && (
        <span
          role="button"
          tabIndex={0}
          className="ms-0.5 inline-flex h-5 w-5 items-center justify-center rounded-sm hover:bg-muted transition-colors"
          onClick={(e) => { e.stopPropagation(); onReset(); }}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.stopPropagation(); onReset(); } }}
          aria-label={i18n.reset ?? "Reset filters"}
        >
          <X className="size-3" />
        </span>
      )}
    </Button>
  ) : null;

  const rightContent =
    typeof right === "function"
      ? right(toggleButton)
      : (<>{right}{toggleButton}</>);

  const showSelectionRow = hasSelection && !!selectionActions;

  return (
    <div className="shrink-0">
      {showSelectionRow && (
        <DynamicTableBar
          variant="controller"
          hasSelection
          left={selectionInfo}
          right={selectionActions}
        />
      )}
      <DynamicTableBar
        variant="controller"
        hasSelection={hasSelection && !showSelectionRow}
        left={left}
        right={rightContent}
      />
      {filters && open && (
        <div
          id={panelId}
          role="region"
          aria-label={i18n.toggle}
          className="border-b border-border bg-card px-3 py-2"
        >
          <div className="flex items-center gap-2 flex-wrap">
            {filters}
          </div>
        </div>
      )}
    </div>
  );
};
```

## Wiring: the table controller for one entity

Declare the filter param keys once (used for both the active-count badge and
clear-all), feed server-provided counts to each faceted filter, and lay the
filters out in a grid inside the `filters` slot.

```tsx
// _components/table/[entity]-table-controller.tsx
"use client";

import type { Table } from "@tanstack/react-table";
import {
  DataTableController, SelectionDisplay, EnableButton, DisableButton,
  ColumnToggleButton, DataTableSortList, SearchInput, RefreshButton,
} from "@/components/data-table";
import { useUrlFilterCount } from "@/hooks/use-url-filter-count";
import { StatusDropdownFilter } from "../filters/status-dropdown-filter";
import { RoleDropdownFilter } from "../filters/role-dropdown-filter";

// Every filterable dimension's URL param. Drives the active-count badge + reset.
const FILTER_PARAM_KEYS = ["is_active", "role", "search"] as const;

export function UsersTableController<TData>({
  selectedIds, isUpdating, onClearSelection, onDisable, onEnable, onRefresh,
  tableInstance, activeCount, inactiveCount, roleOptions,
}: UsersTableControllerProps<TData>) {
  const { activeFilterCount, handleReset } = useUrlFilterCount(FILTER_PARAM_KEYS);

  return (
    <DataTableController
      hasSelection={selectedIds.length > 0}
      activeFilterCount={activeFilterCount}
      onReset={handleReset}
      i18n={{ toggle: "Filters", showFilters: "Show filters", hideFilters: "Hide filters" }}
      left={
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <SelectionDisplay
            selectedCount={selectedIds.length}
            onClearSelection={onClearSelection}
            i18n={{ selected: "{count} {item} selected", clearSelection: "Clear", itemName: "user" }}
          />
          <SearchInput placeholder="Search users" urlParam="search" debounceMs={300} className="flex-none w-64" />
        </div>
      }
      filters={
        <div className="flex flex-col gap-2 w-full px-1">
          <div className="grid grid-cols-3 gap-3">
            <RoleDropdownFilter roleOptions={roleOptions} />
            <StatusDropdownFilter activeCount={activeCount} inactiveCount={inactiveCount} />
          </div>
        </div>
      }
      right={(toggle) => (
        <>
          {toggle}
          <RefreshButton onRefresh={onRefresh} />
          <DataTableSortList sortableColumns={[/* ... */]} />
          <ColumnToggleButton table={tableInstance} />
          {selectedIds.length > 0 && (
            <>
              <DisableButton selectedIds={selectedIds.map(Number)} onDisable={(ids) => onDisable(ids.map(String))} disabled={isUpdating} iconOnly />
              <EnableButton selectedIds={selectedIds.map(Number)} onEnable={(ids) => onEnable(ids.map(String))} disabled={isUpdating} iconOnly />
            </>
          )}
        </>
      )}
    />
  );
}
```

## How it all connects

1. The SSR page reads the filter params from `searchParams` and fetches with them;
   the backend returns `items`, `total`, and the **per-facet counts**.
2. The page passes those counts into each faceted filter and `activeCount` /
   `inactiveCount` into the status filter.
3. `useUrlFilterCount(FILTER_PARAM_KEYS)` derives the **active-filter-count badge**
   and the **clear-all** handler from the same keys — keep this list in sync with
   the filters you render.
4. Changing any filter calls `router.replace` with the updated param and
   `page` deleted, which re-runs the SSR fetch and returns refreshed counts.

This keeps the whole pane **URL-driven and server-driven**: deep links restore the
exact filter state, and every count reflects the backend, never client-side guesses.
