# Faceted Filters (per-option counts, single & multi)

`StatusBadgeFilter` covers the binary `is_active` dimension (All / Active / Inactive
with counts). **Faceted filters** generalize that to any dimension with arbitrary
options, each showing its own **count**, in either single- or multi-select mode.
Several faceted filters side by side give the multi-dimension "levels" of filtering
(e.g. status × group × disposition), each dimension independent (combined with AND).

## What faceted filters add

- **Per-option counts** — every option shows how many rows match it: `Available 12`.
- **Single OR multi select** — `multiple` prop. Single-select closes on pick and
  acts like a radio; multi-select accumulates values.
- **Search inside the dropdown** — `FacetedInput` filters long option lists.
- **Active-selection chips** — `FacetedBadgeList` renders the picked values as
  badges in the trigger, with adaptive overflow (`+3`) and an optional clear (×).
- **Count-ranked ordering** — `sortFacetedOptions` surfaces high-count options
  first (skip it for filters with intentional semantic order).

## Where counts come from (server-provided)

Counts are **computed by the backend and returned in the list envelope**, not
derived client-side from the current page. The list response carries one field per
facet option, e.g.:

```typescript
interface AgentListResponse {
  items: Agent[];
  total: number;            // total rows matching current filters (drives pagination)
  // faceted counts — one per option, computed server-side:
  offlineCount: number;
  availableCount: number;
  busyCount: number;
  activeCount: number;      // a second, independent dimension
  inactiveCount: number;
}
```

The page passes these counts down to each faceted filter. Because they are
server-provided, they stay correct under pagination and reflect the full filtered
result set, not just the visible page.

## Component: `components/ui/faceted.tsx`

A compound component built on shadcn `Popover` + `Command` (same primitives as
`MultiSelect`). Scaffold it once; reuse for every faceted filter.

**Adaptation notes:** replace `useLanguage()` / `t.common.select.*` with your i18n
or plain strings. The `FacetedBadgeList` adaptive-overflow measurement (the
`triggerRef` + `ResizeObserver` block) is optional polish — if you don't need it,
render up to `max` badges plus a `+N` overflow and drop the measurement effect.

```tsx
"use client";

import { Check, X } from "lucide-react";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

type FacetedValue<Multiple extends boolean> = Multiple extends true
  ? string[]
  : string;

interface FacetedContextValue<Multiple extends boolean = boolean> {
  value?: FacetedValue<Multiple>;
  onItemSelect?: (value: string) => void;
  multiple?: Multiple;
}

const FacetedContext = React.createContext<FacetedContextValue<boolean> | null>(
  null,
);

function useFacetedContext(name: string) {
  const context = React.useContext(FacetedContext);
  if (!context) {
    throw new Error(`\`${name}\` must be within Faceted`);
  }
  return context;
}

interface FacetedProps<Multiple extends boolean = false>
  extends React.ComponentProps<typeof Popover> {
  value?: FacetedValue<Multiple>;
  onValueChange?: (value: FacetedValue<Multiple> | undefined) => void;
  children?: React.ReactNode;
  multiple?: Multiple;
}

function Faceted<Multiple extends boolean = false>(
  props: FacetedProps<Multiple>,
) {
  const {
    open: openProp,
    onOpenChange: onOpenChangeProp,
    value,
    onValueChange,
    children,
    multiple = false,
    ...facetedProps
  } = props;

  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(false);
  const isControlled = openProp !== undefined;
  const open = isControlled ? openProp : uncontrolledOpen;

  // Ref keeps onItemSelect reading the latest value (no stale closure on rapid clicks)
  const valueRef = React.useRef(value);
  React.useEffect(() => {
    valueRef.current = value;
  }, [value]);

  const onOpenChange = React.useCallback(
    (newOpen: boolean) => {
      if (!isControlled) {
        setUncontrolledOpen(newOpen);
      }
      onOpenChangeProp?.(newOpen);
    },
    [isControlled, onOpenChangeProp],
  );

  const onItemSelect = React.useCallback(
    (selectedValue: string) => {
      if (!onValueChange) { return; }

      if (multiple) {
        const currentValue = (Array.isArray(valueRef.current) ? valueRef.current : []) as string[];
        const newValue = currentValue.includes(selectedValue)
          ? currentValue.filter((v) => v !== selectedValue)
          : [...currentValue, selectedValue];
        onValueChange(newValue as FacetedValue<Multiple>);
      } else {
        if (valueRef.current === selectedValue) {
          onValueChange(undefined);
        } else {
          onValueChange(selectedValue as FacetedValue<Multiple>);
        }
        requestAnimationFrame(() => onOpenChange(false));
      }
    },
    [multiple, onValueChange, onOpenChange],
  );

  const contextValue = React.useMemo<FacetedContextValue<typeof multiple>>(
    () => ({ value, onItemSelect, multiple }),
    [value, onItemSelect, multiple],
  );

  return (
    <FacetedContext.Provider value={contextValue}>
      <Popover open={open} onOpenChange={onOpenChange} {...facetedProps}>
        {children}
      </Popover>
    </FacetedContext.Provider>
  );
}

function FacetedTrigger(props: React.ComponentProps<typeof PopoverTrigger>) {
  const { className, children, ...triggerProps } = props;
  return (
    <PopoverTrigger
      {...triggerProps}
      className={cn("shrink-0 justify-between text-left", className)}
    >
      {children}
    </PopoverTrigger>
  );
}

interface FacetedBadgeListProps extends React.ComponentProps<"span"> {
  options?: { label: string; value: string }[];
  max?: number;
  badgeClassName?: string;
  placeholder?: string;
  selectedLabel?: string;
}

// Simple badge list: shows up to `max` chips then a "+N" overflow badge.
// (For adaptive width-based overflow, measure the trigger with a ResizeObserver.)
function FacetedBadgeList(props: FacetedBadgeListProps) {
  const {
    options = [],
    max = 2,
    placeholder = "Select",
    selectedLabel = "selected",
    className,
    badgeClassName,
    ...badgeListProps
  } = props;

  const context = useFacetedContext("FacetedBadgeList");
  const values = Array.isArray(context.value)
    ? context.value
    : ([context.value].filter(Boolean) as string[]);

  const getLabel = (value: string) =>
    options.find((opt) => opt.value === value)?.label ?? value;

  if (!values || values.length === 0) {
    if (!placeholder) { return null; }
    return (
      <span {...badgeListProps} className="flex w-full items-center gap-1 text-muted-foreground">
        {placeholder}
      </span>
    );
  }

  const showAll = max >= values.length;

  return (
    <span {...badgeListProps} className={cn("inline-flex flex-nowrap items-center gap-1", className)}>
      <span className="mx-1 h-4 w-px shrink-0 bg-border" />
      {showAll ? (
        values.map((value) => (
          <Badge key={value} variant="secondary" className={cn("rounded-sm px-1.5 font-normal", badgeClassName)}>
            <span className="whitespace-nowrap">{getLabel(value)}</span>
          </Badge>
        ))
      ) : (
        <>
          {values.slice(0, max).map((value) => (
            <Badge key={value} variant="secondary" className={cn("rounded-sm px-1.5 font-normal", badgeClassName)}>
              <span className="whitespace-nowrap">{getLabel(value)}</span>
            </Badge>
          ))}
          <Badge variant="secondary" className={cn("rounded-sm px-1.5 font-normal", badgeClassName)}>
            {values.length - max} {selectedLabel}
          </Badge>
        </>
      )}
    </span>
  );
}

function FacetedContent(props: React.ComponentProps<typeof PopoverContent>) {
  const { className, children, ...contentProps } = props;
  return (
    <PopoverContent
      {...contentProps}
      align="start"
      className={cn("w-[280px] p-0", className)}
    >
      <Command>{children}</Command>
    </PopoverContent>
  );
}

const FacetedInput = CommandInput;
const FacetedList = CommandList;
const FacetedEmpty = CommandEmpty;
const FacetedGroup = CommandGroup;
const FacetedSeparator = CommandSeparator;

interface FacetedItemProps extends React.ComponentProps<typeof CommandItem> {
  value: string;
}

function FacetedItem(props: FacetedItemProps) {
  const { value, onSelect, className, children, ...itemProps } = props;
  const context = useFacetedContext("FacetedItem");

  const isSelected = context.multiple
    ? Array.isArray(context.value) && context.value.includes(value)
    : context.value === value;

  const onItemSelect = React.useCallback(
    (currentValue: string) => {
      if (onSelect) { onSelect(currentValue); }
      else if (context.onItemSelect) { context.onItemSelect(currentValue); }
    },
    [onSelect, context.onItemSelect],
  );

  return (
    <CommandItem
      aria-selected={isSelected}
      data-selected={isSelected}
      className={cn("gap-2", className)}
      onSelect={() => onItemSelect(value)}
      {...itemProps}
    >
      <span
        className={cn(
          "flex size-4 items-center justify-center rounded-sm border border-primary",
          isSelected ? "bg-primary text-primary-foreground" : "opacity-50 [&_svg]:invisible",
        )}
      >
        <Check className="size-4" />
      </span>
      {children}
    </CommandItem>
  );
}

/**
 * Rank faceted options by count descending, then label ascending (locale- and
 * numeric-aware). Do NOT use for filters with intentional semantic order —
 * lifecycle stages, severity levels, workflow steps, curated enum sequences.
 */
export function sortFacetedOptions<T extends { label: string; count?: number }>(
  options: T[],
): T[] {
  return [...options].sort((a, b) => {
    const ac = a.count;
    const bc = b.count;
    if (ac !== undefined && bc !== undefined) {
      const diff = bc - ac;
      if (diff !== 0) { return diff; }
    }
    return a.label.localeCompare(b.label, undefined, { sensitivity: "base", numeric: true });
  });
}

export {
  Faceted,
  FacetedBadgeList,
  FacetedContent,
  FacetedEmpty,
  FacetedGroup,
  FacetedInput,
  FacetedItem,
  FacetedList,
  FacetedSeparator,
  FacetedTrigger,
};
```

## Usage: a multi-select faceted filter with counts (URL-driven)

One filter component per dimension. It reads/writes its own URL param and renders
per-option counts from the server envelope. Changing it resets `page` to 1.

```tsx
// _components/filters/agent-status-dropdown-filter.tsx
"use client";

import { useMemo, useCallback } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useTransition } from "react";
import { CirclePlus, CheckCircle, AlertCircle, CircleOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Faceted, FacetedTrigger, FacetedContent, FacetedInput, FacetedList,
  FacetedEmpty, FacetedGroup, FacetedItem, FacetedBadgeList, sortFacetedOptions,
} from "@/components/ui/faceted";

interface Props { offlineCount: number; availableCount: number; busyCount: number; }

export function AgentStatusDropdownFilter({ offlineCount, availableCount, busyCount }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const [, startTransition] = useTransition();

  const current = useMemo(
    () => (searchParams?.get("status")?.split(",").filter(Boolean) ?? []),
    [searchParams],
  );

  const options = useMemo(
    () => sortFacetedOptions([
      { value: "AVAILABLE", label: "Available", count: availableCount, icon: CheckCircle, iconClass: "text-green-500" },
      { value: "BUSY", label: "Busy", count: busyCount, icon: AlertCircle, iconClass: "text-red-500" },
      { value: "OFFLINE", label: "Offline", count: offlineCount, icon: CircleOff, iconClass: "text-muted-foreground" },
    ]),
    [availableCount, busyCount, offlineCount],
  );

  const handleChange = useCallback((value: string[] | undefined) => {
    startTransition(() => {
      const params = new URLSearchParams(searchParams?.toString() || "");
      params.delete("page"); // reset pagination on any filter change
      if (value && value.length > 0) { params.set("status", value.join(",")); }
      else { params.delete("status"); }
      router.replace(`${pathname}?${params.toString()}`);
    });
  }, [searchParams, pathname, router]);

  return (
    <Faceted multiple value={current} onValueChange={handleChange}>
      <FacetedTrigger asChild>
        <Button variant="outline" size="sm" className="h-9 border-dashed gap-1">
          <CirclePlus className="size-4" />
          Status
          <FacetedBadgeList options={options} max={2} placeholder="" />
        </Button>
      </FacetedTrigger>
      <FacetedContent>
        <FacetedInput placeholder="Status" />
        <FacetedList>
          <FacetedEmpty>No results.</FacetedEmpty>
          <FacetedGroup>
            {options.map((o) => (
              <FacetedItem key={o.value} value={o.value}>
                <o.icon className={`size-4 shrink-0 ${o.iconClass}`} />
                <span>{o.label}</span>
                <span className="ms-auto text-xs text-muted-foreground tabular-nums">{o.count}</span>
              </FacetedItem>
            ))}
          </FacetedGroup>
        </FacetedList>
      </FacetedContent>
    </Faceted>
  );
}
```

**Single-select** is the same component with `multiple` omitted, a single string
value (`searchParams?.get("disposition") ?? ""`), and `params.set(key, value)`
with one value. It closes on selection and toggles off when the active option is
re-picked.

## Counts and "levels", precisely

- **Per-option count** — `option.count`, server-provided, shown inline in the item
  and used by `sortFacetedOptions` for ranking.
- **Levels = independent filter dimensions.** Each faceted filter is one dimension
  (status, group, disposition, …). They are **orthogonal**, not hierarchical;
  combining them is an AND over the result set. Lay several side by side in the
  filter pane (see [filter-pane.md](filter-pane.md)).
- **Active-filter count** — how many dimensions are currently set; rendered as a
  badge on the filter-pane toggle (see [filter-pane.md](filter-pane.md)).
- **Total / selected-row counts** — `total` drives pagination; selected-row count
  comes from TanStack `rowSelection` via `SelectionDisplay` (already covered by the
  data-table component library).

Render order: put **semantic** dimensions (severity, lifecycle) in their natural
order; pass count-driven dimensions through `sortFacetedOptions`.
