---
description: Validate entity follows architecture patterns
allowed-tools: Read, Glob, Grep, Bash
---

# Validate Command

Validate that an entity follows the established architecture patterns.

## Usage

```
/validate [entity-name]
```

## Examples

```bash
# Validate product entity
/validate product

# Validate user entity
/validate user

# Validate all entities
/validate
```

## What Gets Validated

### FastAPI Patterns

| Check | Description |
|-------|-------------|
| Session Flow | Session passed from router → service → repository |
| No Session Storage | Session not stored in `__init__` |
| CamelModel | Response schemas inherit from CamelModel |
| Domain Exceptions | Uses NotFoundError, not HTTPException |
| Repository Pattern | Repository is stateless, handles data access only |

### Next.js Patterns

| Check | Description |
|-------|-------------|
| SSR Page | Page is server component (no "use client") |
| SWR Usage | Table uses SWR with fallbackData |
| Server Response | Updates use server response, not optimistic |
| URL State | Filters/pagination in URL via nuqs |
| Context Pattern | CRUD actions via context |

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

- [x] Session passed to service methods
- [x] Session passed to repository methods
- [x] No session stored in __init__
- [x] Schemas inherit from CamelModel
- [x] Page is server component
- [x] SWR uses fallbackData
...
```

## Quick Validation

For quick pattern check:

```bash
# Check session flow only
/validate product --check session

# Check frontend only
/validate product --frontend

# Check backend only
/validate product --backend
```

## Continuous Validation

Add to CI/CD:

```yaml
- name: Validate Patterns
  run: claude /validate --all --strict
```
