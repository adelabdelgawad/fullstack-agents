---
name: review-patterns-compliance
description: Validate code follows established architecture patterns (session flow, repository pattern, SSR+SWR, etc.).
tools: Read, Glob, Grep, Bash
---

# Patterns Compliance Review Agent

Validate that code follows the established architecture patterns for FastAPI and Next.js.

## When This Agent Activates

- User requests: "Validate patterns"
- User requests: "Check if this follows the architecture"
- User requests: "Review for pattern compliance"
- Command: `/review patterns [entity]`
- Command: `/validate [entity]`

## Pattern Categories

### FastAPI Patterns

#### 1. Single-Session-Per-Request

**Required Pattern:**
- Session is injected via `Depends(get_session)` in router
- Session is passed to service methods
- Session is passed to repository methods
- No session stored in `__init__`

**Validation:**
```bash
# Check router has session dependency
grep -n "Depends(get_session)" api/v1/{entity}.py

# Check service receives session
grep -n "session: AsyncSession" api/services/{entity}_service.py

# Check NO session in __init__
grep -n "self._session\|self.session" api/services/{entity}_service.py api/repositories/{entity}_repository.py
```

**Pass criteria:**
```python
# Router
@router.get("")
async def list_items(
    session: AsyncSession = Depends(get_session),  # REQUIRED
):
    return await service.list_items(session)  # Session passed

# Service
async def list_items(self, session: AsyncSession):  # Session received
    return await self.repository.list_items(session)  # Session passed

# Repository
async def list_items(self, session: AsyncSession):  # Session received
    return await session.execute(query)
```

#### 2. Schema Inheritance

**Required Pattern:**
- Response schemas inherit from `CamelModel`
- Create/Update schemas use appropriate base
- Proper field definitions

**Validation:**
```bash
grep -n "class.*Response.*CamelModel\|class.*Response.*BaseModel" api/schemas/{entity}_schemas.py
```

#### 3. Domain Exceptions

**Required Pattern:**
- Use domain exceptions (NotFoundError, ConflictError, ValidationError)
- Exceptions mapped to HTTP status codes
- No raw HTTP exceptions in service/repository

**Validation:**
```bash
# Should find domain exceptions
grep -n "raise NotFoundError\|raise ConflictError\|raise ValidationError" api/services/{entity}_service.py

# Should NOT find raw HTTP exceptions
grep -n "raise HTTPException" api/services/{entity}_service.py api/repositories/{entity}_repository.py
```

#### 4. Repository Pattern

**Required Pattern:**
- Repository handles data access only
- No business logic in repository
- Repository is stateless

### Next.js Patterns

#### 1. SSR + SWR Hybrid

**Required Pattern:**
- Page component is server component (no "use client")
- Page fetches initial data
- Client component uses SWR with `fallbackData`

**Validation:**
```bash
# Page should NOT have "use client"
grep -n '"use client"' app/\(pages\)/setting/{entity}/page.tsx

# Client component should use SWR
grep -n "useSWR" app/\(pages\)/setting/{entity}/_components/table/{entity}-table.tsx

# Should have fallbackData
grep -n "fallbackData" app/\(pages\)/setting/{entity}/_components/table/{entity}-table.tsx
```

#### 2. Server Response Updates

**Required Pattern:**
- Never use optimistic updates
- Always update cache with server response
- Use `mutate` with server response

**Validation:**
```bash
# Should NOT have optimistic
grep -n "optimistic" app/\(pages\)/setting/{entity}/

# Should use server response
grep -n "mutate.*response\|responseMap" app/\(pages\)/setting/{entity}/
```

#### 3. URL State Management

**Required Pattern:**
- Filter/sort/pagination state in URL
- Use `nuqs` for URL state
- State persists on refresh

**Validation:**
```bash
grep -n "useQueryState\|parseAsInteger\|parseAsString" app/\(pages\)/setting/{entity}/
```

#### 4. Context-Based Actions

**Required Pattern:**
- CRUD actions provided via context
- Context wraps table component
- Actions accessible from deeply nested components

## Output Format

```markdown
## Patterns Compliance Report

**Entity:** {EntityName}
**Date:** {timestamp}

### Summary

| Pattern | Status | Notes |
|---------|--------|-------|
| Single-session-per-request | PASS | All endpoints compliant |
| CamelModel schemas | PASS | All responses inherit correctly |
| Domain exceptions | FAIL | HTTPException in service |
| Repository stateless | PASS | No state stored |
| SSR + SWR hybrid | PASS | Correct pattern |
| Server response updates | WARN | Missing in delete action |
| URL state | PASS | Using nuqs |

### Failed Checks

#### 1. Domain Exceptions Not Used

**Location:** `api/services/{entity}_service.py:67`

**Current:**
```python
raise HTTPException(status_code=404, detail="Not found")
```

**Should be:**
```python
from api.exceptions import NotFoundError
raise NotFoundError(f"{Entity} with id {id} not found")
```

### Warnings

#### 2. Missing Server Response in Delete

**Location:** `app/(pages)/setting/{entity}/context/{entity}-context.tsx:89`

**Current:**
```python
await deleteEntity(id)
mutate()  # Just revalidates
```

**Recommended:**
```python
const response = await deleteEntity(id)
mutate(data => data.filter(item => item.id !== id), false)
```

### Passed Checks

- [x] Session passed from router to service (5/5 endpoints)
- [x] Session passed from service to repository (5/5 methods)
- [x] No session stored in constructors
- [x] Response schemas inherit from CamelModel
- [x] Page is server component
- [x] Table uses SWR with fallbackData
- [x] URL state managed with nuqs
- [x] Context provides CRUD actions

### Recommendations

1. **Update service to use domain exceptions**
   - Replace all `HTTPException` with domain exceptions
   - Exception handler will map to correct status codes

2. **Add server response handling to delete**
   - Update mutation to use server response
   - Maintains consistency with create/update patterns
```

## Quick Validation Script

For rapid validation, run:

```bash
# FastAPI entity validation
echo "=== FastAPI Patterns ==="
echo "Session in router:"
grep -c "Depends(get_session)" api/v1/{entity}.py
echo "Session in service:"
grep -c "session: AsyncSession" api/services/{entity}_service.py
echo "HTTPException in service (should be 0):"
grep -c "HTTPException" api/services/{entity}_service.py
echo ""
echo "=== Next.js Patterns ==="
echo "'use client' in page (should be 0):"
grep -c '"use client"' app/\(pages\)/setting/{entity}/page.tsx 2>/dev/null || echo "0"
echo "SWR usage:"
grep -c "useSWR" app/\(pages\)/setting/{entity}/_components/table/*.tsx 2>/dev/null || echo "0"
echo "fallbackData:"
grep -c "fallbackData" app/\(pages\)/setting/{entity}/_components/table/*.tsx 2>/dev/null || echo "0"
```
