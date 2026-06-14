# Data Table Component Requirements

The skill assumes a centralized `@/components/data-table` component exists. This documents what it should export.

## Required Exports

```typescript
// components/data-table/index.ts

// Core table
export { DataTable } from './table/data-table';
export { DynamicTableBar } from './table/data-table-bar';
export { DataTableController } from './table/data-table-controller'; // collapsible filter pane
export { Pagination } from './table/pagination';

// Controls
export { SearchInput } from './controls/search-input';
export { ColumnToggleButton } from './controls/column-toggle-button';
export { RefreshButton } from './controls/refresh-button';

// Actions
export { SelectionDisplay } from './actions/selection-display';
export { EnableButton } from './actions/enable-button';
export { DisableButton } from './actions/disable-button';
export { ExportButton } from './actions/export-button';
export { PrintButton } from './actions/print-button';
```

## DataTable Props

```typescript
interface DataTableProps<TData> {
  data: TData[];
  columns: ColumnDef<TData>[];
  onRowSelectionChange?: (selectedRows: TData[]) => void;
  renderToolbar?: (table: TanStackTable<TData>) => React.ReactNode;
  isLoading?: boolean;
  tableInstanceHook?: (tableInstance: TanStackTable<TData>) => void;
  enableRowSelection?: boolean;
  enableSorting?: boolean;
}
```

## DynamicTableBar Props

```typescript
interface DynamicTableBarProps {
  left?: ReactNode;
  middle?: ReactNode;
  right?: ReactNode;
  variant?: "header" | "controller";
  hasSelection?: boolean;
}
```

## Pagination Props

```typescript
interface PaginationProps {
  currentPage?: number;
  pageSize?: number;
  totalItems?: number;
  totalPages?: number;
}
```

## Button Components

### EnableButton / DisableButton

```typescript
interface StatusButtonProps {
  selectedIds: (string | number)[];
  onEnable?: (ids: (string | number)[]) => void;
  onDisable?: (ids: (string | number)[]) => void;
  disabled?: boolean;
}
```

### RefreshButton

```typescript
interface RefreshButtonProps {
  onRefresh: () => void;
  disabled?: boolean;
}
```

### ColumnToggleButton

```typescript
interface ColumnToggleButtonProps {
  table: Table<unknown>;
}
```

### SelectionDisplay

```typescript
interface SelectionDisplayProps {
  selectedCount: number;
  onClearSelection: () => void;
  itemName?: string; // e.g., "user", "device" - pluralized automatically
}
```

### SearchInput

```typescript
interface SearchInputProps {
  placeholder?: string;
  urlParam?: string; // URL param to update, e.g., "search", "filter"
  debounceMs?: number;
}
```

## Usage Pattern

The data-table components use URL state via `nuqs`. When search or pagination changes, the URL updates, which triggers SWR to refetch with the new parameters.

```tsx
// Example: SearchInput updates URL param
<SearchInput
  placeholder="Search users..."
  urlParam="search"  // Updates ?search=... in URL
  debounceMs={500}
/>

// Example: Pagination updates URL param
<Pagination
  currentPage={page}
  totalPages={totalPages}
  pageSize={limit}
  totalItems={totalItems}
/>
// Internally uses:
// const [page, setPage] = useQueryState("page", parseAsInteger.withDefault(1));
```

## DataTableController Props (filter pane)

```typescript
interface DataTableControllerProps {
  left?: ReactNode;
  right?: ReactNode | ((toggle: ReactNode) => ReactNode);
  filters?: ReactNode;            // grid of faceted filters (one per dimension)
  activeFilterCount?: number;     // drives the badge on the toggle
  defaultOpen?: boolean;
  hasSelection?: boolean;
  selectionInfo?: ReactNode;
  selectionActions?: ReactNode;   // bulk-action row shown when rows are selected
  onReset?: () => void;           // clear-all
  i18n: { toggle: string; showFilters: string; hideFilters: string; reset?: string };
}
```

Full source + wiring: [filter-pane.md](filter-pane.md).

## Faceted Filter (per-option counts, single/multi)

`components/ui/faceted.tsx` — compound component (`Faceted`, `FacetedTrigger`,
`FacetedContent`, `FacetedInput`, `FacetedList`, `FacetedEmpty`, `FacetedGroup`,
`FacetedItem`, `FacetedBadgeList`) + `sortFacetedOptions` helper. `multiple` prop
switches single↔multi. Full source + usage: [faceted-filters.md](faceted-filters.md).

## useUrlFilterCount hook

```typescript
function useUrlFilterCount(keys: readonly string[]): {
  activeFilterCount: number;   // count of URL keys with a non-empty value
  handleReset: () => void;     // delete all keys + page from the URL
};
```

## List-envelope facet-count convention

The list response carries **server-computed counts** alongside the rows, so filter
options and the status bar can show accurate counts under pagination:

```typescript
interface EntityListResponse {
  items: Entity[];
  total: number;          // rows matching current filters → pagination
  activeCount: number;    // is_active dimension
  inactiveCount: number;
  // one field per faceted option for each additional dimension, e.g.:
  // availableCount, busyCount, offlineCount, ...
}
```

Counts are computed server-side over the full filtered set — never derived
client-side from the current page.
