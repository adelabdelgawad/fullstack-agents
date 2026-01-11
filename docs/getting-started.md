# Getting Started

This guide will help you get started with the fullstack-agents plugin.

## Installation

### 1. Add the Marketplace

```bash
/plugin marketplace add https://github.com/adelabdelgawad/fullstack-agents
```

### 2. Install the Plugin

```bash
/plugin install fullstack-agents
```

### 3. Verify Installation

```bash
/status
```

You should see the fullstack-agents plugin detected and ready to use.

---

## Quick Start

### Check Project Status

Start by understanding your current project:

```bash
/status
```

This will show:
- Detected technology stack
- Existing entities and their completeness
- Suggested next actions

### Generate Your First Entity

Create a complete FastAPI entity with CRUD operations:

```bash
/generate entity product
```

The agent will:
1. Detect your project patterns
2. Ask about fields and relationships
3. Show you the generation plan
4. Create all necessary files
5. Suggest next steps

### Review Code Quality

Review your code for issues:

```bash
/review quality app/services/
```

### Validate Patterns

Ensure your entity follows project patterns:

```bash
/validate product
```

---

## Common Workflows

### Building a New Feature (Fullstack)

1. **Generate backend entity**
   ```bash
   /generate entity order
   ```

2. **Generate frontend data table**
   ```bash
   /generate data-table orders
   ```

3. **Validate the feature**
   ```bash
   /validate order
   ```

### Starting a New Project

1. **Scaffold backend**
   ```bash
   /scaffold fastapi my-backend
   ```

2. **Scaffold frontend**
   ```bash
   /scaffold nextjs my-frontend
   ```

3. **Add Docker infrastructure**
   ```bash
   /scaffold docker
   ```

### Debugging Issues

1. **Diagnose error**
   ```bash
   /debug error "TypeError: Cannot read property..."
   ```

2. **Analyze logs**
   ```bash
   /debug logs logs/app.log
   ```

3. **Profile performance**
   ```bash
   /debug performance /api/v1/products
   ```

### Code Maintenance

1. **Review security**
   ```bash
   /review security app/
   ```

2. **Optimize performance**
   ```bash
   /optimize performance app/services/
   ```

3. **Cleanup code**
   ```bash
   /optimize cleanup app/
   ```

---

## Understanding Agent Dialogue

The agents use interactive dialogue to understand your needs. Here's an example:

```
/generate entity product

## Entity Configuration

I've analyzed your codebase and detected:
- Database Pattern: SQLAlchemy 2.0 AsyncSession
- Bilingual Support: YES (name_en/name_ar found)
- Soft Delete: YES (is_active pattern found)
- Audit Fields: YES (created_at, updated_at)

### Required Information

1. **Fields**: What fields should this entity have?
   - Example: name_en: str, price: Decimal, category_id: int

2. **Relationships**: Any foreign key relationships?
   - Example: category_id -> categories.id

### Optional (will use detected patterns)

- Primary Key: Integer (override? y/n)
- Include bilingual fields? (yes)
- Include soft delete? (yes)

Reply with your field definitions or "confirm" to proceed with defaults.
```

### Responding to Dialogue

You can respond naturally:

```
Fields:
- name_en: str
- name_ar: str
- price: Decimal
- category_id: int (FK to categories)
- is_featured: bool = False

Relationships:
- Many products to one category
```

---

## Best Practices

### 1. Always Start with /status

```bash
/status
```

Understand your project state before making changes.

### 2. Use /generate Instead of Manual Code

```bash
# Instead of writing model, schema, repo, service, router manually
/generate entity customer
```

The agent will match your existing patterns.

### 3. Run /validate Before Committing

```bash
/validate customer
```

Catch pattern violations early.

### 4. Use /review for Code Quality

```bash
/review quality app/services/customer_service.py
```

### 5. Let Agents Suggest Next Steps

After generation, the agent will suggest related actions:

```
## Generation Complete

Customer entity created successfully.

### Next Steps
1. Create migration: `alembic revision --autogenerate`
2. Test API at: http://localhost:8000/docs

### Related Actions
Would you like me to:
- Generate frontend page? → /generate data-table customers
- Add Celery task? → /generate task customer-sync
```

---

## Troubleshooting

### Plugin Not Detected

If `/status` doesn't show the plugin:

1. Verify installation:
   ```bash
   /plugin list
   ```

2. Reinstall if needed:
   ```bash
   /plugin uninstall fullstack-agents
   /plugin install fullstack-agents
   ```

### Patterns Not Detected

If agents don't detect your patterns:

1. Ensure you're in the project root
2. Check that standard directory structure exists
3. Verify at least one complete entity exists for pattern detection

### Generation Errors

If code generation fails:

1. Check error message for specific issue
2. Ensure required dependencies are installed
3. Verify database connection if entity-related

---

## Next Steps

- Read the [Agents Reference](agents.md) for detailed agent documentation
- Read the [Commands Reference](commands.md) for all available commands
- Read the [Skills Reference](skills.md) for pattern documentation

---

## Getting Help

- GitHub Issues: [Report a bug](https://github.com/adelabdelgawad/fullstack-agents/issues)
- Documentation: [Full documentation](https://github.com/adelabdelgawad/fullstack-agents/docs)
