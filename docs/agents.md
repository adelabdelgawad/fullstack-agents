# Agents Reference

This document provides a complete reference for all 28 agents in the fullstack-agents plugin.

## Agent Categories Overview

| Category | Count | Purpose |
|----------|-------|---------|
| Generate | 7 | Smart code generation with interactive dialogue |
| Review | 4 | Code quality, security, performance analysis |
| Analyze | 4 | Codebase, architecture, dependency analysis |
| Scaffold | 5 | Project and module scaffolding |
| Debug | 4 | Error diagnosis, log analysis, profiling |
| Optimize | 4 | Performance, cleanup, refactoring |

---

## Agent Lifecycle

All agents follow a consistent 6-phase lifecycle:

```
1. DETECTION      → Detect project type, existing patterns
2. DIALOGUE       → Ask clarifying questions
3. ANALYSIS       → Analyze existing code to match style
4. CONFIRMATION   → Present plan, get user approval
5. EXECUTION      → Generate/modify code
6. NEXT STEPS     → Suggest related actions
```

---

## Generate Agents

### generate/fastapi-entity

**Purpose**: Generate complete FastAPI CRUD entity with model, schema, repository, service, and router.

**Dialogue Questions**:
- Entity name and fields
- Relationships (foreign keys, one-to-many)
- Bilingual fields (name_en/name_ar)
- Soft delete pattern
- Search/filter requirements

**Generated Files**:
- `app/models/{entity}.py` - SQLAlchemy model
- `app/schemas/{entity}.py` - Pydantic schemas
- `app/repositories/{entity}_repository.py` - Data access layer
- `app/services/{entity}_service.py` - Business logic
- `app/api/v1/endpoints/{entity}.py` - API router

---

### generate/nextjs-page

**Purpose**: Generate Next.js page with SSR + SWR hybrid pattern.

**Dialogue Questions**:
- Page name and route
- Server-side data fetching needs
- Client-side interactivity
- Form requirements

**Generated Files**:
- `app/{route}/page.tsx` - Server component
- `app/{route}/{PageName}Client.tsx` - Client component
- `app/{route}/types.ts` - TypeScript types

---

### generate/nextjs-data-table

**Purpose**: Generate full CRUD data table page with TanStack Table.

**Dialogue Questions**:
- Entity name and columns
- Filter requirements
- Actions (edit, delete, view)
- Bulk operations

**Generated Files**:
- `app/{route}/page.tsx` - Page component
- `app/{route}/components/columns.tsx` - Column definitions
- `app/{route}/components/data-table.tsx` - Table component
- `app/{route}/components/toolbar.tsx` - Toolbar component
- `app/{route}/components/dialogs/` - CRUD dialogs

---

### generate/api-route

**Purpose**: Generate Next.js API routes that proxy to FastAPI backend.

**Dialogue Questions**:
- Resource name
- Endpoints needed (list, detail, create, update, delete)
- Request/response transformations

**Generated Files**:
- `app/api/{resource}/route.ts` - Collection routes
- `app/api/{resource}/[id]/route.ts` - Item routes

---

### generate/celery-task

**Purpose**: Generate Celery background task with proper patterns.

**Dialogue Questions**:
- Task name and purpose
- Parameters and return type
- Retry configuration
- Error handling requirements

**Generated Files**:
- `app/tasks/{task_name}.py` - Task implementation
- Updates to `app/tasks/__init__.py`

---

### generate/scheduled-job

**Purpose**: Generate APScheduler job for recurring tasks.

**Dialogue Questions**:
- Job name and purpose
- Schedule (cron, interval)
- Dependencies and parameters

**Generated Files**:
- `app/jobs/{job_name}.py` - Job implementation
- Updates to job scheduler configuration

---

### generate/docker-service

**Purpose**: Add new service to Docker Compose configuration.

**Dialogue Questions**:
- Service name
- Base image
- Port mappings
- Environment variables
- Volume mounts
- Dependencies

**Modified Files**:
- `docker-compose.yml`
- `docker-compose.prod.yml` (if exists)

---

## Review Agents

### review/code-quality

**Purpose**: Review code for quality issues, maintainability, and best practices.

**Checks**:
- Code complexity
- Naming conventions
- DRY violations
- Error handling
- Documentation coverage

---

### review/security

**Purpose**: Review code for security vulnerabilities.

**Checks**:
- SQL injection
- XSS vulnerabilities
- Authentication issues
- Secret exposure
- Input validation
- CORS configuration

---

### review/performance

**Purpose**: Review code for performance issues.

**Checks**:
- N+1 queries
- Missing indexes
- Inefficient algorithms
- Memory leaks
- Caching opportunities

---

### review/patterns-compliance

**Purpose**: Review code for compliance with project patterns.

**Checks**:
- Repository pattern usage
- Service layer patterns
- Router patterns
- Schema patterns
- Frontend patterns

---

## Analyze Agents

### analyze/codebase

**Purpose**: Provide comprehensive codebase analysis.

**Output**:
- Project structure overview
- Technology stack
- Code statistics
- Pattern inventory
- Dependency map

---

### analyze/architecture

**Purpose**: Analyze and document system architecture.

**Output**:
- Component diagram
- Data flow analysis
- Integration points
- Scalability assessment

---

### analyze/dependencies

**Purpose**: Analyze project dependencies.

**Output**:
- Dependency tree
- Version analysis
- Security vulnerabilities
- Update recommendations

---

### analyze/patterns

**Purpose**: Identify and document code patterns.

**Output**:
- Pattern inventory
- Consistency assessment
- Pattern documentation
- Deviation analysis

---

## Scaffold Agents

### scaffold/project-fastapi

**Purpose**: Scaffold new FastAPI project with full structure.

**Generated Structure**:
```
backend/
├── app/
│   ├── api/v1/
│   ├── core/
│   ├── models/
│   ├── schemas/
│   ├── repositories/
│   ├── services/
│   └── main.py
├── alembic/
├── tests/
└── requirements.txt
```

---

### scaffold/project-nextjs

**Purpose**: Scaffold new Next.js project with patterns.

**Generated Structure**:
```
frontend/
├── app/
├── components/
├── lib/
├── hooks/
├── types/
└── package.json
```

---

### scaffold/module-backend

**Purpose**: Scaffold new backend module.

**Generated Files**:
- Model, schema, repository, service, router
- Test files
- Migration file

---

### scaffold/module-frontend

**Purpose**: Scaffold new frontend module.

**Generated Files**:
- Page components
- Client components
- Type definitions
- API utilities

---

### scaffold/docker-infrastructure

**Purpose**: Scaffold Docker infrastructure.

**Generated Files**:
- `docker-compose.yml`
- `docker-compose.prod.yml`
- Service Dockerfiles
- Nginx configuration

---

## Debug Agents

### debug/error-diagnosis

**Purpose**: Diagnose and fix errors.

**Capabilities**:
- Stack trace analysis
- Root cause identification
- Fix suggestions
- Pattern-based solutions

---

### debug/log-analysis

**Purpose**: Analyze application logs.

**Capabilities**:
- Log pattern detection
- Error frequency analysis
- Performance insights
- Anomaly detection

---

### debug/performance-profiling

**Purpose**: Profile application performance.

**Capabilities**:
- Endpoint timing
- Database query analysis
- Memory profiling
- Bottleneck identification

---

### debug/api-debugging

**Purpose**: Debug API issues.

**Capabilities**:
- Request/response analysis
- Authentication debugging
- CORS issue resolution
- Integration testing

---

## Optimize Agents

### optimize/performance

**Purpose**: Optimize application performance.

**Optimizations**:
- Query optimization
- Caching implementation
- Lazy loading
- Code optimization

---

### optimize/code-cleanup

**Purpose**: Clean up code quality issues.

**Cleanup**:
- Dead code removal
- Import organization
- Formatting consistency
- Unused dependency removal

---

### optimize/refactoring

**Purpose**: Refactor code for better design.

**Refactoring**:
- Extract methods
- Reduce complexity
- Improve naming
- Apply patterns

---

### optimize/query-optimization

**Purpose**: Optimize database queries.

**Optimizations**:
- Query analysis
- Index recommendations
- N+1 query fixes
- Eager loading
