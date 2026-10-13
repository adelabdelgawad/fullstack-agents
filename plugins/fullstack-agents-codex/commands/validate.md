## Codex runtime binding

Follow the bundle's `AGENTS.md` and `fullstack-agents-task-flow`: Codex leads,
Claude audits bounded diffs through `scripts/handoff.py`. Read only relevant
skill sections once. Existing user authorization wins over historical approval
steps. Native Codex roles replace Claude tools/dispatchers/hooks below. Bundle
paths resolve from the bundle; skill paths resolve beside `SKILL.md`. Validate
explicitly; do not assume historical hooks or dashboards are running.

# Validate Command

Validate that an entity follows the established architecture patterns.

## Usage

```
$fullstack-agents-validate [entity-name]
$fullstack-agents-validate fetch [scope]
```

## Examples

```bash
# Validate product entity
$fullstack-agents-validate product

# Validate user entity
$fullstack-agents-validate user

# Validate all entities
$fullstack-agents-validate

# Full fetch architecture audit (loads fetch-validate skill)
$fullstack-agents-validate fetch

# Validate only server actions
$fullstack-agents-validate fetch server-actions

# Validate only API routes
$fullstack-agents-validate fetch api-routes

# Validate only client components
$fullstack-agents-validate fetch client
```

## What Gets Validated

### FastAPI Patterns

| Check | Description |
|-------|-------------|
| SessionDep | Router uses `SessionDep` type alias |
| No Session Storage | Session not stored in `__init__` |
| CamelModel | Response schemas inherit from CamelModel |
| Domain Exceptions | Uses NotFoundError, not HTTPException |
| CRUD Helpers | Plain functions in `api/crud/`, no classes |

### Next.js Patterns

| Check | Description |
|-------|-------------|
| SSR Page | Page is server component (no "use client") |
| Data Pattern | Table uses `useState(initialData)` (default) or SWR (with justification) |
| Server Response | Updates use server response, not optimistic; creates/deletes revalidate the list (`skills/fullstack-agents-nextjs/references/data-freshness.md`) |
| URL State | Filters/pagination in URL via nuqs |
| Context Pattern | CRUD actions via context |

### Fetch Architecture

> **Note:** When `fetch` is specified, loads the `fetch-validate` skill for detailed checks.

| Check | Description |
|-------|-------------|
| Server action URLs | Use `/backend/` prefix, not `/api/` |
| API route imports | `backendFetch` from `@/lib/fetch/backend` |
| API route mutations | Use `(token, headers)` with CSRF forwarding |
| Client API usage | `api` object, not deprecated `fetchClient` |
| CSRF compliance | All three layers have CSRF wired |
| No SWR | Strategy A only unless justified |

## Validation Output

```markdown
## Validation Report: Product

### Summary
- **Passed**: 12 checks
- **Failed**: 2 checks
- **Warnings**: 1 check

### Failed Checks

#### 1. HTTPException in Service
- **File**: `api/services/product_service.py:67`
- **Issue**: Using HTTPException instead of domain exception
- **Fix**: Replace with `raise NotFoundError(...)`

### Passed Checks

- [x] SessionDep used in router endpoints
- [x] CRUD helpers are plain functions
- [x] No session stored in __init__
- [x] Schemas inherit from CamelModel
- [x] Page is server component
- [x] Table uses simplified pattern (or SWR with justification)
...
```

## Quick Validation

For quick pattern check:

```bash
# Check session flow only
$fullstack-agents-validate product --check session

# Check frontend only
$fullstack-agents-validate product --frontend

# Check backend only
$fullstack-agents-validate product --backend
```

## Fetch Validation

`$fullstack-agents-validate fetch` loads the `fetch-validate` skill to perform a full fetch architecture audit across all three layers (server actions, API routes, client components).

```bash
# Full audit across all layers
$fullstack-agents-validate fetch

# Scope to a single layer
$fullstack-agents-validate fetch server-actions
$fullstack-agents-validate fetch api-routes
$fullstack-agents-validate fetch client
```

## Continuous Validation

Add to CI/CD:

```yaml
- name: Validate Patterns
  run: bash scripts/validate.sh LANE SERVICE_ROOT
```
