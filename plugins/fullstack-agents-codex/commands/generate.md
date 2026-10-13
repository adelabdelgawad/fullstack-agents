## Codex runtime binding

Follow the bundle's `AGENTS.md` and `fullstack-agents-task-flow`: Codex leads,
Claude audits bounded diffs through `scripts/handoff.py`. Read only relevant
skill sections once. Existing user authorization wins over historical approval
steps. Native Codex roles replace Claude tools/dispatchers/hooks below. Bundle
paths resolve from the bundle; skill paths resolve beside `SKILL.md`. Validate
explicitly; do not assume historical hooks or dashboards are running.

# Generate Command

Generate code using intelligent agents with pattern detection and interactive dialogue.

## Usage

```
$fullstack-agents-generate [type] [name]
```

## Types

| Type | Agent | Description |
|------|-------|-------------|
| `entity` | generate/fastapi-entity | FastAPI CRUD entity (model, schema, CRUD helpers, router) |
| `page` | generate/nextjs-page | Next.js page with SSR and server actions |
| `data-table` | generate/nextjs-data-table | Next.js data table page with full CRUD |
| `api-route` | generate/api-route | Next.js API routes proxying to backend |
| `fetch` | fetch-plan + fetch-implement | Plan and scaffold fetch layer (server actions + API routes) for an entity |
| `task` | generate/celery-task | Celery background task |
| `job` | generate/scheduled-job | APScheduler scheduled job |
| `docker-service` | generate/docker-service | Docker service in docker-compose |
| `websocket` | generate/nextjs-page | WebSocket connection with rooms and message protocol |
| `fullstack` | orchestration | Complete fullstack feature (backend + frontend) |

## Examples

```bash
# Generate FastAPI entity
$fullstack-agents-generate entity product

# Generate Next.js data table page
$fullstack-agents-generate data-table products

# Generate complete fullstack feature
$fullstack-agents-generate fullstack order

# Generate Celery task
$fullstack-agents-generate task sync-inventory

# Generate scheduled job
$fullstack-agents-generate job daily-report

# Generate fetch layer for entity
$fullstack-agents-generate fetch schedules setting

# Generate fetch layer for management entity
$fullstack-agents-generate fetch campaigns management

# Generate WebSocket feature
$fullstack-agents-generate websocket notifications
```

## Interactive Process

1. **Detection** - Detect project type and existing patterns
2. **Dialogue** - Ask clarifying questions about fields, relationships, features
3. **Confirmation** - Show generation plan before creating files
4. **Generation** - Create files following detected patterns
5. **Next Steps** - Suggest related actions

## Smart Features

- **Pattern Detection** - Analyzes existing code to match your style
- **Relationship Handling** - Asks about foreign keys and relationships
- **Edge Cases** - Considers soft delete, audit fields, bilingual support
- **Orchestration** - Chain multiple agents for fullstack generation
- **Fetch Pattern Compliance** — When generating `api-route` or `fetch`, first loads `fetch-plan` to determine required files, then `fetch-implement` for scaffolding templates. Ensures correct patterns (direct backend calls for server actions, (token, headers) for API route mutations, backendFetch from backend.ts)
- **WebSocket Patterns** — When generating `websocket`, loads the `websocket` skill references (`skills/fullstack-agents-websocket/SKILL.md`) for connection manager, rooms, message protocol, receive loop, and error handling patterns

## Default Behavior

If no type specified, shows interactive menu:

```bash
$fullstack-agents-generate

# Shows:
# 1. FastAPI Entity
# 2. Next.js Page
# 3. Data Table Page
# 4. API Route
# 5. Celery Task
# 6. Scheduled Job
# 7. Docker Service
# 8. WebSocket Feature
# 9. Fullstack Feature
```
