# Edit Sheet Pattern

## Overview

Data tables typically display a subset of entity fields (5-10 columns for readability), but edit forms require the complete entity with all properties (potentially 15-20+ fields).

**Problem:** Using `row.original` from the table provides only partial data.

**Solution:** Fetch the complete entity by ID **before** opening the edit sheet.

---

## Pattern: Fetch-Then-Open

```
1. User clicks Edit button → Button shows loading spinner
2. Server-side fetch retrieves complete entity by ID
3. Sheet opens with full data (no loading state inside sheet)
4. User edits and saves → Server response updates table cache
```

---

## Row Actions Component

The row actions component handles the fetch-then-open logic.

```tsx
// _components/table/[entity]-row-actions.tsx
"use client";

import { useState, useTransition } from "react";
import { api } from "@/lib/fetch/client";
import { Edit[Entity]Sheet } from "../modal/edit-[entity]-sheet";
import { use[Entity]Actions } from "../../context/[entity]-actions-context";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Loader2, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { toast } from "@/components/ui/custom-toast";
import type { [Entity]Response } from "@/types/[entity]";

interface [Entity]RowActionsProps {
  entityId: string;
}

export function [Entity]RowActions({ entityId }: [Entity]RowActionsProps) {
  const { updateItems } = use[Entity]Actions();
  const [editingData, setEditingData] = useState<[Entity]Response | null>(null);
  const [isPending, startTransition] = useTransition();

  const handleEditClick = () => {
    startTransition(async () => {
      try {
        const data = await api.get<[Entity]Response>(
          `/[section]/[entity]/${entityId}`
        );
        setEditingData(data);
      } catch (error: unknown) {
        const err = error as { data?: { detail?: string }; message?: string };
        toast.error(err.data?.detail || err.message || "Failed to load item");
      }
    });
  };

  const handleUpdate = (updated: [Entity]Response) => {
    updateItems([updated]);
    setEditingData(null);
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" disabled={isPending}>
            {isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <MoreHorizontal className="h-4 w-4" />
            )}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={handleEditClick}>
            <Pencil className="mr-2 h-4 w-4" />
            Edit
          </DropdownMenuItem>
          {/* Other menu items... */}
        </DropdownMenuContent>
      </DropdownMenu>

      {editingData && (
        <Edit[Entity]Sheet
          item={editingData}
          open={!!editingData}
          onClose={() => setEditingData(null)}
          onUpdate={handleUpdate}
        />
      )}
    </>
  );
}
```

---

## Edit Sheet Component

The sheet receives complete entity data and renders the form.

```tsx
// _components/modal/edit-[entity]-sheet.tsx
"use client";

import { useTransition } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { [Entity]Form } from "./[entity]-form";
import { api } from "@/lib/fetch/client";
import { toast } from "@/components/ui/custom-toast";
import type { [Entity]Response, Update[Entity]Payload } from "@/types/[entity]";

interface Edit[Entity]SheetProps {
  item: [Entity]Response;
  open: boolean;
  onClose: () => void;
  onUpdate: (updated: [Entity]Response) => void;
}

export function Edit[Entity]Sheet({
  item,
  open,
  onClose,
  onUpdate,
}: Edit[Entity]SheetProps) {
  const [isPending, startTransition] = useTransition();

  const handleSubmit = (payload: Update[Entity]Payload) => {
    startTransition(async () => {
      try {
        const updated = await api.put<[Entity]Response>(
          `/[section]/[entity]/${item.id}`,
          payload
        );
        toast.success("Updated successfully");
        onUpdate(updated);
      } catch (error: unknown) {
        const err = error as { data?: { detail?: string }; message?: string };
        toast.error(err.data?.detail || err.message || "Failed to update");
        // Keep sheet open on error so user can fix and retry
      }
    });
  };

  return (
    <Sheet open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <SheetContent className="sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Edit {item.name}</SheetTitle>
          <SheetDescription>
            Make changes to the item. Click save when done.
          </SheetDescription>
        </SheetHeader>
        <div className="mt-6">
          <[Entity]Form
            initialData={item}
            onSubmit={handleSubmit}
            onCancel={onClose}
            isSubmitting={isPending}
          />
        </div>
      </SheetContent>
    </Sheet>
  );
}
```

---

## Form Component

A reusable form component used by both add and edit sheets.

```tsx
// _components/modal/[entity]-form.tsx
"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Loader2 } from "lucide-react";
import type { [Entity]Response, Update[Entity]Payload } from "@/types/[entity]";

const formSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  // Add other fields...
});

type FormValues = z.infer<typeof formSchema>;

interface [Entity]FormProps {
  initialData?: [Entity]Response;
  onSubmit: (data: Update[Entity]Payload) => void;
  onCancel: () => void;
  isSubmitting: boolean;
}

export function [Entity]Form({
  initialData,
  onSubmit,
  onCancel,
  isSubmitting,
}: [Entity]FormProps) {
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: initialData?.name ?? "",
      // Map other fields...
    },
  });

  const handleSubmit = (values: FormValues) => {
    onSubmit(values as Update[Entity]Payload);
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Name</FormLabel>
              <FormControl>
                <Input {...field} disabled={isSubmitting} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        {/* Add other form fields... */}

        <div className="flex justify-end gap-2 pt-4">
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Save Changes
          </Button>
        </div>
      </form>
    </Form>
  );
}
```

---

## Integration with Context

The row actions consume `updateItems` from context to update the table cache after a successful save.

```tsx
// In row actions
const { updateItems } = use[Entity]Actions();

const handleUpdate = (updated: [Entity]Response) => {
  updateItems([updated]); // Updates table with server response
  setEditingData(null);   // Closes sheet
};
```

---

## Alternative: Using Context for Fetch

If you prefer to centralize the fetch logic in context:

```tsx
// In table-component (actions object)
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

// In row actions
const { onFetchEntity, updateItems } = use[Entity]Actions();

const handleEditClick = () => {
  startTransition(async () => {
    const result = await onFetchEntity(entityId);
    if (result.success) {
      setEditingData(result.data);
    } else {
      toast.error(result.error);
    }
  });
};
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Fetch fails | Show toast error, don't open sheet |
| Save fails | Show toast error, keep sheet open for retry |
| Network error | Show appropriate error message |

---

## Key Points

1. **Never use `row.original` for edit forms** - table rows contain partial data
2. **Fetch complete entity by ID** before opening the sheet
3. **Loading state on button** - not inside the sheet
4. **Sheet opens ready** - no skeleton or loading spinner in the sheet
5. **Server response updates cache** - never optimistic updates
6. **Keep sheet open on save error** - allow user to fix and retry

## Sheet Layout and Behaviour Rules (mandatory)

These are restrictions, not suggestions. A generated, changed or reviewed sheet that breaks one is
not done; a project design system that already encodes the same rule (for example a titled
settings-group primitive) is used rather than re-implemented.

1. **Titled sections when a tab has more than one group.** When one sheet tab (or a sheet without
   tabs) renders two or more field groups, every group carries a visible section title naming what
   it holds, for example "Basic information", "Connection information", "Routing". A tab with a
   single group has no section title; the tab label already names it. A conditionally rendered
   group counts whenever it can appear next to another group.
2. **Successful save closes the sheet** — on create and on edit alike, after the server response
   has updated the list. Save errors keep it open (rule 6 above). A sheet that must stay open after
   save (for example a pairing flow that shows a QR code next) states that exception in its code.
3. **Edit shows what is stored.** Every stored non-secret value is prefilled in its input, so the
   user edits in place. The edit endpoint must return those values; a write-only blob the form
   cannot read back is a backend gap to fix, not a reason to render empty inputs.
4. **Secrets stay write-only, one field at a time.** Tokens, passwords, API keys and webhook
   secrets are never returned to the browser. Their inputs show a "saved — leave blank to keep" or
   "not set" hint from a server-provided list of which secrets exist, and a blank secret input keeps
   the stored value. The server merges submitted fields over the stored configuration, so changing
   one field never forces the user to re-enter the others.
