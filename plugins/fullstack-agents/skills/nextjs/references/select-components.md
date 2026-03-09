# Select Components

Two controlled, searchable select components built on Popover + Command (shadcn).

## When to Use

| Use case | Component |
|----------|-----------|
| Single value (one selection at a time) | `SingleSelect` |
| Multiple values (array of selections) | `MultiSelect` |

Both are **fully controlled** — the parent owns state via `value` + `onValueChange`.

> **Note:** This reference documents the canonical controlled implementation sourced from a reference project. If your project has a different MultiSelect installed (e.g. one that uses `defaultValue` instead of `value`, or exposes a ref handle), adapt the API accordingly. The SingleSelect component may also need to be scaffolded if not present — the source above is the complete file to create at `components/ui/single-select.tsx`.

## Option Interface

Both components share the same option shape:

```typescript
interface Option {
  label: string;                                        // Display text
  value: string;                                        // Internal value
  icon?: React.ComponentType<{ className?: string }>;  // Optional icon
  description?: string;                                 // Optional subtitle
  disabled?: boolean;                                   // Prevents selection
}
```

## SingleSelect

> ⚠️ **Inside Sheet or Dialog:** Always pass `modalPopover={true}` to prevent the popover from rendering behind the overlay.

Scaffold at: `components/ui/single-select.tsx`

```tsx
"use client";

import * as React from "react";
import { CheckIcon, ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Button } from "@/components/ui/button";

export interface SingleSelectOption {
  label: string;
  value: string;
  icon?: React.ComponentType<{ className?: string }>;
  description?: string;
  disabled?: boolean;
}

interface SingleSelectProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  options: SingleSelectOption[];
  /** Controlled selected value. */
  value: string;
  /** Callback when selection changes. */
  onValueChange: (value: string) => void;
  placeholder?: string;
  modalPopover?: boolean;
  className?: string;
  emptyMessage?: string;
  searchPlaceholder?: string;
  disabled?: boolean;
}

export function SingleSelect({
  options,
  value,
  onValueChange,
  placeholder = "Select option",
  modalPopover = false,
  className,
  emptyMessage = "No results found.",
  searchPlaceholder = "Search...",
  disabled = false,
  ...props
}: SingleSelectProps) {
  const [isPopoverOpen, setIsPopoverOpen] = React.useState(false);

  const selected = options.find((o) => o.value === value);

  const handleSelect = (optionValue: string) => {
    if (disabled) { return; }
    onValueChange(optionValue);
    setIsPopoverOpen(false);
  };

  return (
    <Popover
      open={isPopoverOpen}
      onOpenChange={(open) => {
        if (!disabled) { setIsPopoverOpen(open); }
      }}
      modal={modalPopover}
    >
      <PopoverTrigger asChild>
        <Button
          {...props}
          type="button"
          disabled={disabled}
          className={cn(
            "flex h-9 w-full items-center justify-between rounded-md border border-input bg-background px-3 text-sm font-normal text-foreground hover:bg-background hover:text-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
            className
          )}
        >
          <span
            className={cn(
              "truncate",
              !selected && "text-muted-foreground"
            )}
          >
            {selected ? selected.label : placeholder}
          </span>
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground ml-2" />
        </Button>
      </PopoverTrigger>

      <PopoverContent
        className="w-auto p-0 min-w-[var(--radix-popover-trigger-width)]"
        align="start"
        onEscapeKeyDown={() => setIsPopoverOpen(false)}
        onWheel={(e) => e.stopPropagation()}
      >
        <Command>
          <CommandInput placeholder={searchPlaceholder} />
          <CommandList className="max-h-[40vh] overflow-y-auto overscroll-contain">
            <CommandEmpty>{emptyMessage}</CommandEmpty>
            <CommandGroup>
              {options.map((option) => {
                const isSelected = option.value === value;
                return (
                  <CommandItem
                    key={option.value}
                    value={`${option.label} ${option.value}`}
                    onSelect={() => handleSelect(option.value)}
                    className={cn(
                      "cursor-pointer",
                      option.disabled && "opacity-50 cursor-not-allowed"
                    )}
                    disabled={option.disabled}
                  >
                    {option.icon && (
                      <option.icon className="mr-2 h-4 w-4 text-muted-foreground shrink-0" />
                    )}
                    <div className="flex flex-col min-w-0 flex-1">
                      <span className="truncate">{option.label}</span>
                      {option.description && (
                        <span className="text-xs text-muted-foreground truncate">
                          {option.description}
                        </span>
                      )}
                    </div>
                    <CheckIcon
                      className={cn(
                        "ml-2 h-4 w-4 shrink-0",
                        isSelected ? "opacity-100" : "opacity-0"
                      )}
                    />
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export type { SingleSelectProps };
```

## MultiSelect

> ⚠️ **Inside Sheet or Dialog:** Always pass `modalPopover={true}` to prevent the popover from rendering behind the overlay.

Scaffold at: `components/ui/multi-select.tsx`

```tsx
"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { CheckIcon, XCircle, ChevronDown, XIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";

const multiSelectVariants = cva("m-1 transition ease-in-out delay-150", {
  variants: {
    variant: {
      default:
        "border-foreground/10 text-foreground bg-card hover:bg-card/80",
      secondary:
        "border-foreground/10 bg-secondary text-secondary-foreground hover:bg-secondary/80",
      destructive:
        "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
      inverted: "inverted",
    },
  },
  defaultVariants: {
    variant: "default",
  },
});

export interface MultiSelectOption {
  label: string;
  value: string;
  icon?: React.ComponentType<{ className?: string }>;
  description?: string;
  disabled?: boolean;
}

interface MultiSelectProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof multiSelectVariants> {
  options: MultiSelectOption[];
  /** Controlled selected values. */
  value: string[];
  /** Callback when selection changes. */
  onValueChange: (value: string[]) => void;
  placeholder?: string;
  /** Max badges shown before "+ N more" overflow. Default: 3. */
  maxCount?: number;
  modalPopover?: boolean;
  className?: string;
  /** If true, hides the Select All option. */
  hideSelectAll?: boolean;
  emptyMessage?: string;
  searchPlaceholder?: string;
  disabled?: boolean;
  /** If true, closes the popover after each selection. */
  closeOnSelect?: boolean;
}

export function MultiSelect({
  options,
  value,
  onValueChange,
  variant,
  placeholder = "Select options",
  maxCount = 3,
  modalPopover = false,
  className,
  hideSelectAll = false,
  emptyMessage = "No results found.",
  searchPlaceholder = "Search...",
  disabled = false,
  closeOnSelect = false,
  ...props
}: MultiSelectProps) {
  const [isPopoverOpen, setIsPopoverOpen] = React.useState(false);

  const toggleOption = (optionValue: string) => {
    if (disabled) { return; }
    const option = options.find((o) => o.value === optionValue);
    if (option?.disabled) { return; }

    const newSelectedValues = value.includes(optionValue)
      ? value.filter((v) => v !== optionValue)
      : [...value, optionValue];
    onValueChange(newSelectedValues);

    if (closeOnSelect) { setIsPopoverOpen(false); }
  };

  const handleClear = () => {
    if (disabled) { return; }
    onValueChange([]);
  };

  const handleTogglePopover = () => {
    if (disabled) { return; }
    setIsPopoverOpen((prev) => !prev);
  };

  const clearExtraOptions = () => {
    if (disabled) { return; }
    onValueChange(value.slice(0, maxCount));
  };

  const toggleAll = () => {
    if (disabled) { return; }
    const enabledOptions = options.filter((o) => !o.disabled);
    if (value.length === enabledOptions.length) {
      handleClear();
    } else {
      onValueChange(enabledOptions.map((o) => o.value));
    }
    if (closeOnSelect) { setIsPopoverOpen(false); }
  };

  return (
    <Popover
      open={isPopoverOpen}
      onOpenChange={setIsPopoverOpen}
      modal={modalPopover}
    >
      <PopoverTrigger asChild>
        <Button
          {...props}
          onClick={handleTogglePopover}
          disabled={disabled}
          className={cn(
            "flex p-1 rounded-md border min-h-10 h-auto items-center justify-between bg-inherit hover:bg-inherit [&_svg]:pointer-events-auto w-full",
            disabled && "opacity-50 cursor-not-allowed",
            className
          )}
        >
          {value.length > 0 ? (
            <div className="flex justify-between items-center w-full">
              <div className="flex items-center flex-wrap gap-1">
                {value.slice(0, maxCount).map((v) => {
                  const option = options.find((o) => o.value === v);
                  const IconComponent = option?.icon;
                  return (
                    <Badge
                      key={v}
                      className={cn(multiSelectVariants({ variant }))}
                    >
                      {IconComponent && (
                        <IconComponent className="h-4 w-4 mr-2" />
                      )}
                      {option?.label ?? v}
                      <div
                        role="button"
                        tabIndex={0}
                        onClick={(event) => {
                          event.stopPropagation();
                          toggleOption(v);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            event.stopPropagation();
                            toggleOption(v);
                          }
                        }}
                        aria-label={`Remove ${option?.label}`}
                        className="ml-2 h-4 w-4 cursor-pointer hover:bg-white/20 rounded-sm p-0.5 -m-0.5 focus:outline-none focus:ring-1 focus:ring-white/50"
                      >
                        <XCircle className="h-3 w-3" />
                      </div>
                    </Badge>
                  );
                })}
                {value.length > maxCount && (
                  <Badge
                    className={cn(
                      "bg-transparent text-foreground border-foreground/1 hover:bg-transparent",
                      multiSelectVariants({ variant })
                    )}
                  >
                    {`+ ${value.length - maxCount} more`}
                    <XCircle
                      className="ml-2 h-4 w-4 cursor-pointer"
                      onClick={(event) => {
                        event.stopPropagation();
                        clearExtraOptions();
                      }}
                    />
                  </Badge>
                )}
              </div>
              <div className="flex items-center justify-between">
                <div
                  role="button"
                  tabIndex={0}
                  onClick={(event) => {
                    event.stopPropagation();
                    handleClear();
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      event.stopPropagation();
                      handleClear();
                    }
                  }}
                  aria-label="Clear all"
                  className="flex items-center justify-center h-4 w-4 mx-2 cursor-pointer text-muted-foreground hover:text-foreground focus:outline-none rounded-sm"
                >
                  <XIcon className="h-4 w-4" />
                </div>
                <Separator
                  orientation="vertical"
                  className="flex min-h-6 h-full"
                />
                <ChevronDown className="h-4 mx-2 cursor-pointer text-muted-foreground" />
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between w-full mx-auto">
              <span className="text-sm text-muted-foreground mx-3">
                {placeholder}
              </span>
              <ChevronDown className="h-4 cursor-pointer text-muted-foreground mx-2" />
            </div>
          )}
        </Button>
      </PopoverTrigger>

      <PopoverContent
        className="w-auto p-0 min-w-[var(--radix-popover-trigger-width)]"
        align="start"
        onEscapeKeyDown={() => setIsPopoverOpen(false)}
        onWheel={(e) => e.stopPropagation()}
      >
        <Command className="overflow-visible">
          <CommandInput placeholder={searchPlaceholder} />
          <CommandList className="max-h-[40vh] overflow-y-auto overscroll-contain">
            <CommandEmpty>{emptyMessage}</CommandEmpty>

            {!hideSelectAll && (
              <CommandGroup>
                <CommandItem
                  key="all"
                  onSelect={toggleAll}
                  className="cursor-pointer"
                >
                  <div
                    className={cn(
                      "mr-2 flex h-4 w-4 items-center justify-center rounded-sm border border-primary",
                      value.length === options.filter((o) => !o.disabled).length
                        ? "bg-primary text-primary-foreground"
                        : "opacity-50 [&_svg]:invisible"
                    )}
                  >
                    <CheckIcon className="h-4 w-4" />
                  </div>
                  <span>(Select All)</span>
                </CommandItem>
              </CommandGroup>
            )}

            <CommandGroup>
              {options.map((option) => {
                const isSelected = value.includes(option.value);
                return (
                  <CommandItem
                    key={option.value}
                    value={`${option.label} ${option.value}`}
                    onSelect={() => toggleOption(option.value)}
                    className={cn(
                      "cursor-pointer",
                      option.disabled && "opacity-50 cursor-not-allowed"
                    )}
                    disabled={option.disabled}
                  >
                    <div
                      className={cn(
                        "mr-2 flex h-4 w-4 items-center justify-center rounded-sm border border-primary shrink-0",
                        isSelected
                          ? "bg-primary text-primary-foreground"
                          : "opacity-50 [&_svg]:invisible"
                      )}
                    >
                      <CheckIcon className="h-4 w-4" />
                    </div>
                    {option.icon && (
                      <option.icon className="mr-2 h-4 w-4 text-muted-foreground" />
                    )}
                    <div className="flex flex-col min-w-0">
                      <span className="truncate">{option.label}</span>
                      {option.description && (
                        <span className="text-xs text-muted-foreground truncate">
                          {option.description}
                        </span>
                      )}
                    </div>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>

          {/* Footer: Clear + Close — outside CommandList so it's never filtered */}
          <div className="border-t border-border">
            <div className="flex items-center justify-between">
              {value.length > 0 && (
                <>
                  <button
                    type="button"
                    onClick={handleClear}
                    className="flex-1 justify-center py-1.5 text-sm text-center cursor-pointer hover:bg-accent hover:text-accent-foreground"
                  >
                    Clear
                  </button>
                  <Separator
                    orientation="vertical"
                    className="flex min-h-6 h-full"
                  />
                </>
              )}
              <button
                type="button"
                onClick={() => setIsPopoverOpen(false)}
                className="flex-1 justify-center py-1.5 text-sm text-center cursor-pointer hover:bg-accent hover:text-accent-foreground"
              >
                Close
              </button>
            </div>
          </div>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export type { MultiSelectProps };
```

## Usage Examples

### Basic — SingleSelect

```tsx
const [status, setStatus] = useState("");

<SingleSelect
  options={[
    { label: "Active", value: "active" },
    { label: "Inactive", value: "inactive" },
  ]}
  value={status}
  onValueChange={setStatus}
  placeholder="Select status"
/>
```

### Basic — MultiSelect

```tsx
const [roleIds, setRoleIds] = useState<string[]>([]);

<MultiSelect
  options={[
    { label: "Admin", value: "1" },
    { label: "Agent", value: "2" },
    { label: "Supervisor", value: "3" },
  ]}
  value={roleIds}
  onValueChange={setRoleIds}
  placeholder="Select roles"
/>
```

### With Icon and Description

```tsx
import { ShieldCheck, User } from "lucide-react";

<SingleSelect
  options={[
    { label: "Admin", value: "admin", icon: ShieldCheck, description: "Full system access" },
    { label: "Agent", value: "agent", icon: User, description: "Call center agent" },
  ]}
  value={value}
  onValueChange={setValue}
/>
```

### Disabled Options

```tsx
<MultiSelect
  options={[
    { label: "Available", value: "available" },
    { label: "In Use", value: "in_use", disabled: true },
  ]}
  value={values}
  onValueChange={setValues}
/>
```

### Inside Sheet or Dialog

**Always pass `modalPopover={true}` when inside a Sheet or Dialog** to prevent z-index issues (popover appearing behind the overlay):

```tsx
<SingleSelect
  options={options}
  value={value}
  onValueChange={setValue}
  modalPopover={true}
/>

<MultiSelect
  options={options}
  value={values}
  onValueChange={setValues}
  modalPopover={true}
/>
```

## Dependencies

Both components require these to already exist in the project:

- `lucide-react` — `CheckIcon`, `XCircle`, `ChevronDown`, `XIcon`
- `class-variance-authority` — `cva` (MultiSelect only)
- shadcn components: `Popover`, `PopoverContent`, `PopoverTrigger`
- shadcn components: `Command`, `CommandInput`, `CommandList`, `CommandEmpty`, `CommandGroup`, `CommandItem`
- shadcn components: `Button`
- shadcn components: `Badge`, `Separator` (MultiSelect only)
