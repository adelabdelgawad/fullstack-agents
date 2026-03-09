# Select Components in Data Tables

How to use `SingleSelect` and `MultiSelect` in data table contexts.
See [nextjs/references/select-components.md](../../nextjs/references/select-components.md) for full component source and general usage.

## SingleSelect as a Toolbar Filter

Use `SingleSelect` when filtering a table by a single value (e.g. status, campaign, agent group).
Wire it to a URL param so the filter survives navigation and SSR picks it up on refresh.

```tsx
// In [entity]-table.tsx or [entity]-table-controller.tsx
"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useTransition } from "react";
import { SingleSelect } from "@/components/ui/single-select";

const statusOptions = [
  { label: "All", value: "" },
  { label: "Active", value: "active" },
  { label: "Paused", value: "paused" },
  { label: "Completed", value: "completed" },
];

export function CampaignStatusFilter() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const [, startTransition] = useTransition();
  const current = searchParams.get("status") ?? "";

  return (
    <SingleSelect
      options={statusOptions}
      value={current}
      onValueChange={(v) => {
        startTransition(() => {
          const params = new URLSearchParams(searchParams.toString());
          if (v) { params.set("status", v); } else { params.delete("status"); }
          params.delete("page"); // reset to page 1
          router.replace(`${pathname}?${params.toString()}`);
        });
      }}
      placeholder="All statuses"
      className="w-[180px]"
    />
  );
}
```

Render it inside `DynamicTableBar`:

```tsx
<DynamicTableBar
  variant="header"
  left={<SearchInput />}
  middle={<CampaignStatusFilter />}
  right={<ColumnToggleButton table={table} />}
/>
```

## MultiSelect in Edit/Add Sheets

Use `MultiSelect` for multi-value fields in forms: roles, agent groups, extensions, tags, etc.

**Critical:** Always pass `modalPopover={true}` inside Sheet components — without it the popover
appears behind the sheet overlay (z-index clash).

```tsx
// In add-[entity]-sheet.tsx or edit-[entity]-sheet.tsx
"use client";

import { useState } from "react";
import { api } from "@/lib/fetch/client";
import { MultiSelect } from "@/components/ui/multi-select";
import type { MultiSelectOption } from "@/components/ui/multi-select";

interface Props {
  roles: { id: number; name: string }[];
}

export function AddUserSheet({ roles }: Props) {
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);

  const roleOptions: MultiSelectOption[] = roles.map((r) => ({
    label: r.name,
    value: String(r.id),
  }));

  const handleSubmit = async () => {
    const result = await api.post("/api/setting/users", {
      roleIds: selectedRoleIds.map(Number),
    });
  };

  return (
    <Sheet>
      <SheetContent>
        <MultiSelect
          options={roleOptions}
          defaultValue={selectedRoleIds}
          onValueChange={setSelectedRoleIds}
          placeholder="Select roles"
          modalPopover={true}   // Required inside Sheet
        />
        <Button onClick={handleSubmit}>Save</Button>
      </SheetContent>
    </Sheet>
  );
}
```

## Mapping API Responses to Options

Generic helper for any list endpoint that returns `{ id, name }` shaped objects:

```tsx
import type { SingleSelectOption } from "@/components/ui/single-select";

function toOptions<T extends { id: number | string; name: string }>(
  items: T[]
): SingleSelectOption[] {
  return items.map((item) => ({
    label: item.name,
    value: String(item.id),
  }));
}

// Usage
const campaignOptions = toOptions(campaigns);
const groupOptions = toOptions(agentGroups);
```

## Prop Tips

| Scenario | Prop |
|----------|------|
| Inside Sheet or Dialog | `modalPopover={true}` (required) |
| Small option list (< 5) where Select All adds no value | `hideSelectAll={true}` |
| Effectively single-select but needs flexibility | `closeOnSelect={true}` |
| Show more badge labels before overflow | `maxCount={5}` (default is 3) |
