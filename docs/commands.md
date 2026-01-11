# Commands Reference

This document provides a complete reference for all 8 slash commands in the fullstack-agents plugin.

## Command Overview

| Command | Description |
|---------|-------------|
| `/generate` | Generate code with pattern detection and dialogue |
| `/review` | Review code for quality, security, performance |
| `/analyze` | Analyze codebase, architecture, dependencies |
| `/scaffold` | Scaffold new projects or modules |
| `/debug` | Debug errors, logs, performance issues |
| `/optimize` | Optimize performance, cleanup, refactor |
| `/validate` | Validate entity follows patterns |
| `/status` | Show project status and available actions |

---

## /generate

Generate code with smart pattern detection and interactive dialogue.

### Usage

```bash
# Generate FastAPI entity
/generate entity <name>

# Generate Next.js page
/generate page <name>

# Generate data table
/generate data-table <name>

# Generate complete fullstack feature
/generate fullstack <name>

# Generate Celery task
/generate task <name>

# Generate scheduled job
/generate job <name>

# Generate Docker service
/generate service <name>
```

### Examples

```bash
# Generate product entity with full CRUD
/generate entity product

# Generate orders data table page
/generate data-table orders

# Generate complete user management feature
/generate fullstack user
```

### Behavior

1. **Detects project type** - FastAPI, Next.js, or both
2. **Analyzes existing patterns** - Matches your coding style
3. **Asks clarifying questions** - Fields, relationships, features
4. **Presents generation plan** - Confirms before generating
5. **Generates code** - Creates all necessary files
6. **Suggests next steps** - Related actions to continue

---

## /review

Review code for quality, security, and performance issues.

### Usage

```bash
# Review code quality
/review quality <path>

# Review security
/review security <path>

# Review performance
/review performance <path>

# Review pattern compliance
/review patterns <entity>
```

### Examples

```bash
# Review quality of product module
/review quality app/services/product_service.py

# Review security of entire API
/review security app/api/

# Review patterns for user entity
/review patterns user
```

### Output

- Issue identification with severity
- Code location references
- Specific fix recommendations
- Pattern violation details

---

## /analyze

Analyze codebase, architecture, and dependencies.

### Usage

```bash
# Analyze entire codebase
/analyze codebase

# Analyze architecture
/analyze architecture

# Analyze dependencies
/analyze dependencies

# Analyze patterns
/analyze patterns
```

### Examples

```bash
# Get comprehensive codebase overview
/analyze codebase

# Analyze system architecture
/analyze architecture

# Check dependency health
/analyze dependencies
```

### Output

- Structured analysis report
- Visual diagrams (text-based)
- Recommendations
- Action items

---

## /scaffold

Scaffold new projects or modules.

### Usage

```bash
# Scaffold FastAPI project
/scaffold fastapi <name>

# Scaffold Next.js project
/scaffold nextjs <name>

# Scaffold backend module
/scaffold module-backend <name>

# Scaffold frontend module
/scaffold module-frontend <name>

# Scaffold Docker infrastructure
/scaffold docker
```

### Examples

```bash
# Create new FastAPI backend
/scaffold fastapi my-api

# Create new Next.js frontend
/scaffold nextjs my-app

# Add new backend module
/scaffold module-backend orders

# Set up Docker infrastructure
/scaffold docker
```

### Behavior

1. **Checks for existing project** - Avoids overwriting
2. **Asks configuration questions** - Database, auth, features
3. **Creates directory structure** - Complete project layout
4. **Generates boilerplate** - Ready-to-run code
5. **Provides setup instructions** - Next steps to run

---

## /debug

Debug errors, logs, and performance issues.

### Usage

```bash
# Diagnose error
/debug error <error-message-or-path>

# Analyze logs
/debug logs <path>

# Profile performance
/debug performance <endpoint>

# Debug API issue
/debug api <endpoint>
```

### Examples

```bash
# Diagnose a specific error
/debug error "AttributeError: 'NoneType' object has no attribute 'id'"

# Analyze application logs
/debug logs logs/app.log

# Profile slow endpoint
/debug performance /api/v1/products

# Debug API authentication issue
/debug api /api/v1/users/me
```

### Output

- Root cause analysis
- Step-by-step diagnosis
- Fix recommendations
- Prevention strategies

---

## /optimize

Optimize performance, cleanup code, and refactor.

### Usage

```bash
# Optimize performance
/optimize performance <path>

# Cleanup code
/optimize cleanup <path>

# Refactor code
/optimize refactor <path>

# Optimize queries
/optimize queries <path>
```

### Examples

```bash
# Optimize product service performance
/optimize performance app/services/product_service.py

# Cleanup unused code
/optimize cleanup app/

# Refactor complex function
/optimize refactor app/services/order_service.py:process_order

# Optimize database queries
/optimize queries app/repositories/
```

### Behavior

1. **Analyzes current state** - Identifies issues
2. **Proposes optimizations** - With impact assessment
3. **Confirms changes** - Before applying
4. **Applies optimizations** - Safely with rollback info
5. **Measures improvement** - Before/after comparison

---

## /validate

Validate that an entity follows project patterns.

### Usage

```bash
# Validate entity
/validate <entity>

# Validate with auto-fix
/validate <entity> --fix
```

### Examples

```bash
# Validate product entity
/validate product

# Validate and fix issues
/validate user --fix
```

### Checks

- **Model**: Correct base class, fields, relationships
- **Schema**: CamelModel usage, field validators
- **Repository**: Pattern compliance, session handling
- **Service**: Business logic patterns
- **Router**: Endpoint patterns, dependency injection
- **Frontend**: Component patterns, type safety

### Output

```
## Validation Results: product

✅ Model: Passed
✅ Schema: Passed
⚠️  Repository: 1 warning
   - Line 45: Consider using async context manager
❌ Service: 1 error
   - Line 23: Missing session parameter in method signature
✅ Router: Passed

Total: 4 passed, 1 warning, 1 error
```

---

## /status

Show project status and available actions.

### Usage

```bash
# Show status
/status
```

### Output

```
## Project Status

### Detected Stack
- Backend: FastAPI (detected)
- Frontend: Next.js (detected)
- Database: PostgreSQL
- Cache: Redis

### Entities
| Entity | Model | Schema | Repo | Service | Router | Frontend |
|--------|-------|--------|------|---------|--------|----------|
| User   | ✅    | ✅     | ✅   | ✅      | ✅     | ✅       |
| Product| ✅    | ✅     | ✅   | ✅      | ✅     | ❌       |
| Order  | ✅    | ⚠️     | ✅   | ❌      | ❌     | ❌       |

### Suggested Actions
1. Complete Order entity: `/generate entity order --continue`
2. Add Product frontend: `/generate data-table products`
3. Review patterns: `/review patterns`
```

---

## Command Shortcuts

| Shortcut | Full Command |
|----------|--------------|
| `/gen` | `/generate` |
| `/rev` | `/review` |
| `/dbg` | `/debug` |
| `/opt` | `/optimize` |
| `/val` | `/validate` |

---

## Best Practices

1. **Start with /status** - Understand current state
2. **Use /generate for new code** - Don't write from scratch
3. **Run /review after changes** - Catch issues early
4. **Use /validate before commit** - Ensure pattern compliance
5. **Run /optimize periodically** - Keep code clean
