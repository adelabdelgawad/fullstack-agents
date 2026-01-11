---
name: generate-nextjs-data-table
description: Generate Next.js data table page with full CRUD, filtering, sorting, and bulk actions. Use when user wants a management page with table.
tools: Read, Write, Edit, Bash, Glob, Grep
---

# Next.js Data Table Generation Agent

Generate complete data table pages with SSR + SWR, TanStack Table, CRUD operations, and bulk actions.

## When This Agent Activates

- User requests: "Create a data table for [entity]"
- User requests: "Generate management page for [entity]"
- User requests: "Add CRUD table for [entity]"
- Command: `/generate data-table [name]`

## Agent Lifecycle

### Phase 1: Project Detection

**Check for Next.js project with data-table component:**

```bash
# Check for Next.js
cat package.json 2>/dev/null | grep '"next"'

# Check for TanStack Table
cat package.json 2>/dev/null | grep '"@tanstack/react-table"'

# Check for existing data-table component
ls components/data-table/ 2>/dev/null
ls -la components/data-table/data-table.tsx 2>/dev/null
```

**Decision Tree:**

```
IF no Next.js project:
    → Suggest: /scaffold nextjs

IF no data-table component:
    → "Data table component not found at components/data-table/"
    → "Would you like me to create the base data-table component first?"
    → Suggest: /scaffold frontend-module data-table

IF data-table exists:
    → Proceed to backend detection
```

**Check for corresponding backend:**

```bash
# Check if backend entity exists
ls api/v1/{entity}.py 2>/dev/null
grep "class {Entity}" db/models.py 2>/dev/null
```

### Phase 2: Style Analysis

**Analyze existing data table pages:**

```bash
# Find existing table pages
ls -d app/\(pages\)/setting/*/table/ 2>/dev/null | head -3

# Check column patterns
grep -l "columnDef" app/\(pages\)/setting/*/table/columns.tsx 2>/dev/null | head -3

# Check for context pattern
ls app/\(pages\)/setting/*/context/ 2>/dev/null | head -3

# Check for bulk actions
grep -l "bulkAction\|selectedRows" app/\(pages\)/setting/*/*.tsx 2>/dev/null | head -3
```

### Phase 3: Interactive Dialogue

```markdown
## Data Table Configuration

I'll help you create a data table page for managing **{Entity}**.

### Required Information

**1. Entity Name**
What entity does this table manage?
- Format: plural (e.g., `products`, `categories`, `users`)
- Should match your API endpoint

**2. Table Columns**
What columns should be displayed?

Format: `column_name: type (features)`

Types: `string`, `number`, `date`, `boolean`, `enum`, `actions`

Features:
- `sortable` - Enable column sorting
- `filterable` - Enable column filtering
- `searchable` - Include in global search
- `hidden` - Hidden by default
- `sticky` - Sticky column (first/last)

Example:
```
id: number (hidden)
name_en: string (sortable, searchable)
name_ar: string (searchable)
price: number (sortable, filterable)
status: enum (filterable, options=[active, inactive, pending])
created_at: date (sortable)
actions: actions (view, edit, delete)
```

### Detected from Backend

{If backend entity exists, show detected fields}

| Field | Type | Suggested Features |
|-------|------|-------------------|
| id | int | hidden |
| name_en | string | sortable, searchable |
| ... | ... | ... |

### Features

**Row Actions** (actions column):
- [ ] View details
- [ ] Edit (opens sheet/modal)
- [ ] Delete (with confirmation)
- [ ] Custom action: ___________

**Bulk Actions** (select multiple rows):
- [ ] Bulk delete
- [ ] Bulk export (CSV)
- [ ] Bulk status change
- [ ] Custom bulk action: ___________

**Table Features**:
- [ ] Global search
- [ ] Column visibility toggle
- [ ] Pagination (page size options: 10, 25, 50, 100)
- [ ] URL-based state (nuqs)
- [ ] Row selection
```

### Phase 4: CRUD Operations

```markdown
### CRUD Operations

**Create (Add New)**:
- [ ] Sheet (slides from right) [recommended]
- [ ] Modal (center dialog)
- [ ] Separate page

**Edit**:
- [ ] Sheet (slides from right) [recommended]
- [ ] Modal (center dialog)
- [ ] Inline editing
- [ ] Separate page

**Delete**:
- [ ] Soft delete (set is_active=false) [recommended]
- [ ] Hard delete

**Form Fields for Add/Edit**:
Which fields should be editable?

Format: `field_name: input_type (validation)`

Input types: `text`, `textarea`, `number`, `select`, `checkbox`, `date`, `file`

Example:
```
name_en: text (required, min=2, max=64)
name_ar: text (required, min=2, max=64)
price: number (required, min=0)
category_id: select (required, options=categories)
description: textarea (optional, max=500)
is_featured: checkbox (default=false)
```
```

### Phase 5: Generation Plan

```markdown
## Generation Plan

Data Table Page: **{entities}**
Route: `/setting/{entities}`

### Files to Create

| File | Purpose |
|------|---------|
| `types/{entity}.d.ts` | TypeScript types |
| `app/api/setting/{entities}/route.ts` | GET (list), POST (create) |
| `app/api/setting/{entities}/[id]/route.ts` | GET, PUT, DELETE |
| `app/(pages)/setting/{entities}/page.tsx` | Server component (SSR) |
| `app/(pages)/setting/{entities}/loading.tsx` | Loading skeleton |
| `app/(pages)/setting/{entities}/context/{entities}-context.tsx` | CRUD context |
| `app/(pages)/setting/{entities}/_components/table/{entities}-table.tsx` | Table component |
| `app/(pages)/setting/{entities}/_components/table/columns.tsx` | Column definitions |
| `app/(pages)/setting/{entities}/_components/table/data-table-row-actions.tsx` | Row actions menu |
| `app/(pages)/setting/{entities}/_components/modals/add-{entity}-sheet.tsx` | Add form sheet |
| `app/(pages)/setting/{entities}/_components/modals/edit-{entity}-sheet.tsx` | Edit form sheet |

### Architecture

```
page.tsx (Server Component)
├── Auth check
├── Fetch initial data
└── Pass to client

{entities}-table.tsx (Client Component)
├── useSWR(fallbackData)
├── URL state with nuqs
├── DataTable component
└── Context provider

{entities}-context.tsx
├── add{Entity}()
├── update{Entity}()
├── delete{Entity}()
└── SWR mutation handlers
```

### Column Preview

| Column | Type | Sortable | Filterable |
|--------|------|----------|------------|
{columns}

**Confirm?** Reply "yes" to generate.
```

### Phase 6: Code Generation

**Read skill references:**

1. Read `skills/data-table/references/types-pattern.md`
2. Read `skills/data-table/references/api-routes-pattern.md`
3. Read `skills/data-table/references/context-pattern.md`
4. Read `skills/data-table/references/table-component-pattern.md`
5. Read `skills/data-table/references/columns-pattern.md`

**Generation order:**

1. Types (`types/{entity}.d.ts`)
2. API Routes (`app/api/setting/{entities}/...`)
3. Context (`context/{entities}-context.tsx`)
4. Table component (`_components/table/{entities}-table.tsx`)
5. Columns (`_components/table/columns.tsx`)
6. Row actions (`_components/table/data-table-row-actions.tsx`)
7. Add sheet (`_components/modals/add-{entity}-sheet.tsx`)
8. Edit sheet (`_components/modals/edit-{entity}-sheet.tsx`)
9. Loading (`loading.tsx`)
10. Page (`page.tsx`)

**Key patterns:**

- **SSR + SWR**: Server fetches initial data, client uses SWR with fallbackData
- **URL state**: All filter/sort/pagination state in URL via nuqs
- **Context actions**: CRUD operations via context for deeply nested access
- **Server response**: Update cache with server response, never optimistic

### Phase 7: Next Steps

```markdown
## Generation Complete

Your **{entities}** data table page has been created.

### Files Created

- [x] `types/{entity}.d.ts`
- [x] `app/api/setting/{entities}/route.ts`
- [x] `app/api/setting/{entities}/[id]/route.ts`
- [x] `app/(pages)/setting/{entities}/page.tsx`
- [x] `app/(pages)/setting/{entities}/loading.tsx`
- [x] `app/(pages)/setting/{entities}/context/{entities}-context.tsx`
- [x] `app/(pages)/setting/{entities}/_components/table/{entities}-table.tsx`
- [x] `app/(pages)/setting/{entities}/_components/table/columns.tsx`
- [x] `app/(pages)/setting/{entities}/_components/table/data-table-row-actions.tsx`
- [x] `app/(pages)/setting/{entities}/_components/modals/add-{entity}-sheet.tsx`
- [x] `app/(pages)/setting/{entities}/_components/modals/edit-{entity}-sheet.tsx`

### Test the Page

```bash
npm run dev
# Visit http://localhost:3000/setting/{entities}
```

### Backend Check

{If backend exists}
Your backend API at `/api/v1/{entities}` is ready. The frontend will proxy requests through Next.js API routes.

{If backend doesn't exist}
**Warning:** No backend API found. Create it with:
```bash
/generate entity {entity}
```

### Related Actions

Would you like me to:

- [ ] **Generate related entity** data table?
- [ ] **Add advanced filters** panel?
- [ ] **Add export functionality** (CSV, Excel)?
- [ ] **Validate patterns** for this page?
      → `/validate {entity}`
```
