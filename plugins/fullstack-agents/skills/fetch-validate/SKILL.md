---
name: fetch-validate
description: Audit fetch pattern compliance — checks server actions use /backend/ URLs, API routes use backendFetch with (token, headers), client uses api not fetchClient, and CSRF flows correctly.
---

# Fetch Validate

Validate that the codebase follows the correct fetch architecture. Run after code generation, during review, or when debugging data-flow issues.

## Usage

```
/fetch-validate                    # Full codebase audit
/fetch-validate server-actions     # Only check server actions
/fetch-validate api-routes         # Only check API routes
/fetch-validate client             # Only check client components
```

## Architecture Rules (Reference)

For full architecture details, see `fetch-architecture/SKILL.md`. Quick summary:

```
SERVER PATH (1 hop):  Server Action → directBackendFetch() → FastAPI
                      URLs: /backend/setting/users

CLIENT PATH (2 hops): Client → api.post() → /api/... → withAuth() → backendFetch() → FastAPI
```

| File | Who imports it |
|------|---------------|
| `lib/fetch/server.ts` | Server actions only (`lib/actions/`) |
| `lib/fetch/client.ts` | Client components only |
| `lib/fetch/backend.ts` | API routes only (`app/api/`) |
| `lib/fetch/api-route-helper.ts` | API routes only (`app/api/`) |

---

## Checks

Run these sequentially. Report violations with `file:line` references.

### Check 1: Server Actions — Direct Backend Calls

Scan all files in `lib/actions/` (and subdirectories).

**Rules:**
- URLs MUST use `/backend/` prefix (not `/api/`)
- MUST NOT import `backendFetch`
- MUST NOT import from `api-route-helper`

```
Grep pattern="serverGet|serverPost|serverPut|serverDelete" path="lib/actions/" output_mode="content"
→ Filter for lines containing '/api/' — each match is a violation

Grep pattern="from.*fetch/backend" path="lib/actions/"
→ Should return ZERO results

Grep pattern="from.*api-route-helper" path="lib/actions/"
→ Should return ZERO results
```

**Fix for violations:**
- `/api/setting/X` → `/backend/setting/X`
- Remove `backendFetch` imports — use `serverGet/Post/Put/Delete` instead

### Check 2: API Routes — Correct Imports and Patterns

Scan all files in `app/api/`.

**Rules:**
- Import `backendFetch` from `@/lib/fetch/backend` (NOT from `./server`)
- NO `backendGet/Post/Put/Delete` helper functions
- GET handlers use `(token)` callback
- Mutation handlers (POST/PUT/PATCH/DELETE) use `(token, headers)` callback
- Mutations pass `{ headers }` to `backendFetch`

```
Grep pattern="backendFetch.*from.*server" path="app/api/"
→ Should return ZERO results

Grep pattern="backendGet|backendPost|backendPut|backendDelete" path="app/api/"
→ Should return ZERO results

For each mutation route, check withAuth callback includes "headers":
Grep pattern="withAuth" path="app/api/" output_mode="content"
→ Review: POST/PUT/PATCH/DELETE handlers should have (token, headers)
```

**Fix for violations:**
- `from '@/lib/fetch/server'` → `from '@/lib/fetch/backend'`
- `backendGet('/path', token)` → `backendFetch('/path', token)`
- `backendPost('/path', token, body)` → `backendFetch('/path', token, { method: 'POST', body, headers })`
- `(token) =>` on mutations → `(token, headers) =>` and add `{ headers }` to options

### Check 3: Client Components — API Object Usage

Scan `app/` and `components/` for `.tsx` and `.ts` files.

**Rules:**
- NO `fetchClient` usage (deprecated)
- Use `api.get/post/put/patch/delete` which returns `T` directly
- NO `{ data: ... }` destructuring from API calls

```
Grep pattern="fetchClient" path="app/" glob="*.{ts,tsx}"
→ Should return ZERO results

Grep pattern="fetchClient" path="components/" glob="*.{ts,tsx}"
→ Should return ZERO results
```

**Fix for violations:**
- `fetchClient.get<T>(url)` → `api.get<T>(url)` (returns `T` directly)
- `const { data: result } = await fetchClient.put(...)` → `const result = await api.put(...)`

### Check 4: CSRF Compliance

Verify CSRF is wired through all three layers.

```
Grep pattern="getServerCsrfToken" path="lib/fetch/server.ts"
→ Must find the function

Grep pattern="csrfManager" path="lib/fetch/client.ts"
→ Must find csrfManager.getToken() usage

Grep pattern="X-CSRF-Token" path="lib/fetch/api-route-helper.ts"
→ Must find CSRF header forwarding
```

### Check 5: No SWR (Unless Justified)

```
Grep pattern="from ['\"]swr['\"]|useSWR" path="app/" glob="*.{ts,tsx}"
→ Should return ZERO results (Strategy A only)

Grep pattern="from ['\"]swr['\"]|useSWR" path="components/" glob="*.{ts,tsx}"
→ Should return ZERO results
```

---

## Report Format

```markdown
## Fetch Validation Report

### Summary
- **Passed**: X checks
- **Failed**: Y checks
- **Warnings**: Z checks

### Server Actions (lib/actions/)
- [x] All URLs use /backend/ prefix
- [x] No backendFetch imports
- [ ] FAIL: lib/actions/users.actions.ts:42 — uses /api/setting/users

### API Routes (app/api/)
- [x] All import from @/lib/fetch/backend
- [x] No backendGet/Post/Put/Delete helpers
- [ ] WARN: app/api/dialer/queue/leads/[id]/reset-stuck/route.ts:4 — POST uses (token) not (token, headers)

### Client Components
- [x] No fetchClient usage
- [x] No { data } destructuring

### CSRF
- [x] Server: getServerCsrfToken present
- [x] Client: csrfManager present
- [x] API Routes: forwardHeaders present

### Data Strategy
- [x] No SWR imports (Strategy A)
```

---

## Automated Script

For CI or quick checks, run the helper script from `src/frontend/`:

```bash
cd src/frontend/
python3 /path/to/fullstack-agents/skills/fetch-architecture/scripts/helper.py validate
```
