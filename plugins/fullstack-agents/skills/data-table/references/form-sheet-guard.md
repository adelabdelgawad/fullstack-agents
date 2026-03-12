# Form Sheet / Dialog Close Guard

Prevent silent data loss when users close a Sheet or Dialog with unsaved changes.
When the form is dirty and the user tries to close (X button, Escape, or clicking outside),
intercept the close and show a "Discard changes?" confirmation dialog.

## How It Works

Radix UI Dialog fires `onOpenChange(false)` for all close triggers: X button, Escape key,
and overlay click. Passing a guarded handler instead of the raw `onOpenChange` prop lets
you intercept every close path from one place — no need to modify the Sheet/Dialog component itself.

## The `useFormSheet` Hook

The project provides `@/hooks/use-form-sheet` for this pattern.

```typescript
import { useFormSheet } from "@/hooks/use-form-sheet";

const { handleOpenChange, isDirty, confirmDialog } = useFormSheet({
  form,          // React Hook Form instance (isDirty auto-detected)
  onOpenChange,  // parent prop
});
```

Or with manual dirty tracking (no React Hook Form):

```typescript
const { handleOpenChange, isDirty, confirmDialog } = useFormSheet({
  isDirty,       // boolean you compute from state comparison
  onOpenChange,
  onReset,       // optional: reset local state on discard
});
```

## Usage with React Hook Form

```tsx
"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useFormSheet } from "@/hooks/use-form-sheet";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface EditFooDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: FooItem;
}

export function EditFooDialog({ open, onOpenChange, item }: EditFooDialogProps) {
  const form = useForm<FooFormValues>({
    resolver: zodResolver(fooSchema),
    defaultValues: { name: item.name },
  });

  // Intercepts all close triggers — shows "Discard changes?" if form is dirty
  const { handleOpenChange, isDirty, confirmDialog } = useFormSheet({
    form,
    onOpenChange,
  });

  const handleSave = form.handleSubmit(async (data) => {
    await api.put(`/setting/foo/${item.id}`, data);
    onOpenChange(false);
  });

  return (
    <>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Edit Foo
              {isDirty && (
                <span className="ml-2 text-sm font-normal text-orange-500">
                  • Unsaved changes
                </span>
              )}
            </DialogTitle>
          </DialogHeader>

          <form id="edit-foo-form" onSubmit={handleSave}>
            {/* form fields */}
          </form>

          <DialogFooter>
            <Button variant="outline" onClick={() => handleOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" form="edit-foo-form" disabled={!isDirty}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Required: renders the "Discard changes?" confirmation dialog */}
      {confirmDialog}
    </>
  );
}
```

## Usage with Manual Dirty Tracking

For dialogs that don't use React Hook Form, compute `isDirty` yourself by comparing
current state against initial values captured in a ref.

```tsx
"use client";

import { useState, useEffect, useRef } from "react";
import { useFormSheet } from "@/hooks/use-form-sheet";

interface EditBarDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: BarItem;
}

export function EditBarDialog({ open, onOpenChange, item }: EditBarDialogProps) {
  const [name, setName] = useState(item.name);
  const [description, setDescription] = useState(item.description ?? "");

  // Capture initial values on open
  const initialValues = useRef({ name: item.name, description: item.description ?? "" });
  useEffect(() => {
    if (open) {
      initialValues.current = { name: item.name, description: item.description ?? "" };
      setName(item.name);
      setDescription(item.description ?? "");
    }
  }, [open, item]);

  // Compare current state to initial values
  const isDirty =
    name !== initialValues.current.name ||
    description !== initialValues.current.description;

  const { handleOpenChange, confirmDialog } = useFormSheet({
    isDirty,
    onOpenChange,
    onReset: () => {
      setName(initialValues.current.name);
      setDescription(initialValues.current.description);
    },
  });

  return (
    <>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent>
          {/* form fields */}
        </DialogContent>
      </Dialog>
      {confirmDialog}
    </>
  );
}
```

## Rules

- **Always render `{confirmDialog}`** as a sibling of `<Dialog>` — it won't show otherwise
- **Cancel button** should call `handleOpenChange(false)` not `onOpenChange(false)`, so it also checks dirty state
- **Save button** calls `onOpenChange(false)` directly after a successful save (no confirmation needed)
- **Add dialogs** do not need this guard (no pre-existing data to lose)
- **Sheet** works the same way as Dialog — pass `handleOpenChange` to `onOpenChange`

## Checklist

- [ ] `useFormSheet` imported from `@/hooks/use-form-sheet`
- [ ] `handleOpenChange` passed to `<Dialog onOpenChange={handleOpenChange}>`
- [ ] `{confirmDialog}` rendered as sibling of `</Dialog>`
- [ ] Cancel button uses `handleOpenChange(false)` not `onOpenChange(false)`
- [ ] Save success path uses `onOpenChange(false)` directly (bypasses confirmation)
- [ ] `isDirty && <span>• Unsaved changes</span>` shown in dialog title
