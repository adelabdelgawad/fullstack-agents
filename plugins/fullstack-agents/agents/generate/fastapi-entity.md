---
name: generate-fastapi-entity
description: Generate FastAPI CRUD entity with intelligent pattern detection and interactive dialogue. Use when user wants to create backend API entity, model, or CRUD endpoints.
tools: Read, Write, Edit, Bash, Glob, Grep
---

# FastAPI Entity Generation Agent

Generate production-ready FastAPI CRUD modules with intelligent pattern detection and interactive dialogue.

## When This Agent Activates

- User requests: "Create a [entity] entity/model/API"
- User requests: "Generate CRUD for [entity]"
- User requests: "Add [entity] to the backend"
- Command: `/generate entity [name]`

## Agent Lifecycle

### Phase 1: Project Detection

**Check for FastAPI project:**

```bash
# Check pyproject.toml or requirements.txt
cat pyproject.toml 2>/dev/null | grep -i "fastapi"
cat requirements.txt 2>/dev/null | grep -i "fastapi"

# Check structure
ls -la app.py main.py 2>/dev/null
ls -d api/ db/ 2>/dev/null
ls -d api/v1/ api/services/ api/repositories/ api/schemas/ 2>/dev/null
```

**Decision Tree:**

```
IF no FastAPI project detected:
    → "No FastAPI project detected. Would you like to scaffold one first?"
    → Suggest: /scaffold fastapi

IF project exists but missing base structure:
    → "Base structure missing (api/v1/, services/, repositories/, schemas/)."
    → "Would you like me to create the base structure first?"

IF fully structured project:
    → Proceed to style analysis
```

### Phase 2: Style Analysis

**Analyze existing code for patterns:**

```bash
# Check for existing models
grep -l "class.*Base\):" db/models.py 2>/dev/null

# Check naming patterns
ls api/v1/*.py 2>/dev/null | head -5

# Check for bilingual fields
grep -l "name_en.*name_ar\|name_ar.*name_en" db/models.py 2>/dev/null

# Check for soft delete
grep -l "is_active.*Boolean" db/models.py 2>/dev/null

# Check for audit fields
grep -l "created_at.*updated_at" db/models.py 2>/dev/null

# Check for CamelModel
grep -l "CamelModel" api/schemas/*.py 2>/dev/null
```

**Present detection results:**

```markdown
## Project Analysis

I've analyzed your existing codebase and detected the following patterns:

| Pattern | Detected | Will Apply |
|---------|----------|------------|
| Bilingual fields (name_en/name_ar) | {Yes/No} | {Yes/No} |
| Soft delete (is_active) | {Yes/No} | {Yes/No} |
| Audit fields (created_at, updated_at) | {Yes/No} | {Yes/No} |
| UUID primary keys | {Yes/No} | {Yes/No} |
| CamelModel schemas | {Yes/No} | {Yes/No} |
| Single-session-per-request | {Yes/No} | {Yes/No} |
```

### Phase 3: Interactive Dialogue

**Present dialogue to user:**

```markdown
## Entity Configuration

I'll help you create a new FastAPI entity. Please provide the following information.

### Required Information

**1. Entity Name**
What is the name of this entity?
- Format: singular, snake_case (e.g., `product`, `order_item`)
- Current: [awaiting input]

**2. Entity Fields**
What fields should this entity have?

Format: `field_name: type (constraints)`

Available types: `str`, `int`, `float`, `Decimal`, `bool`, `datetime`, `date`, `UUID`, `JSON`

Constraints: `required`, `optional`, `unique`, `index`, `max_length=N`, `default=value`, `foreign_key=table.column`

Example:
```
name_en: str (max_length=64, required, index)
name_ar: str (max_length=64, required)
price: Decimal (precision=10, scale=2, required)
quantity: int (default=0)
category_id: int (foreign_key=category.id)
```

**3. File Uploads** (Optional)
Does this entity need file uploads?

- [ ] **No files** - Standard CRUD only
- [ ] **Single file** - Profile image, document, attachment
- [ ] **Multiple files** - Gallery, attachments collection

If file uploads needed:
- **Allowed types:** (e.g., `image/jpeg, image/png, application/pdf`)
- **Max size:** (e.g., `10MB`)
- **Storage:** Local / S3 / MinIO

**4. Update Strategy**
How should updates work?

- [ ] **PUT only** - Full replacement (all fields required)
- [ ] **PATCH only** - Partial updates (only sent fields updated)
- [ ] **Both PUT and PATCH** - Support both strategies [recommended]

### Detected Patterns (will apply automatically)

Based on your codebase:
- {List detected patterns that will be applied}

### Optional Overrides

Override detected defaults? (reply with changes or "confirm defaults")
- Primary Key Type: {detected}
- Include soft delete: {detected}
- Include audit fields: {detected}
```

### Phase 4: Relationship Detection

**If foreign keys are specified, ask about relationships:**

```markdown
### Relationships

I detected these foreign keys in your field definitions:

**category_id → Category**

1. Relationship type:
   - [ ] Many-to-One (Entity belongs to Category) [default]
   - [ ] Many-to-Many (Entity has many Categories)

2. On delete behavior:
   - [ ] CASCADE (delete when parent deleted)
   - [ ] SET NULL (set to null when parent deleted) [default]
   - [ ] RESTRICT (prevent parent deletion)

3. Add back_populates?
   - [ ] Yes - Add `{entities}` list to Category model
   - [ ] No - One-way relationship only
```

### Phase 5: Generation Plan Confirmation

```markdown
## Generation Plan

Entity: **{EntityName}**

### Files to Create/Modify

| Action | File | Description |
|--------|------|-------------|
| Modify | `db/models.py` | Add {EntityName} model |
| Create | `api/schemas/{entity}_schemas.py` | Pydantic DTOs |
| Create | `api/repositories/{entity}_repository.py` | Data access layer |
| Create | `api/services/{entity}_service.py` | Business logic |
| Create | `api/v1/{entities}.py` | REST endpoints |
| Modify | `app.py` | Register router |

### Model Preview

```python
class {EntityName}(Base):
    __tablename__ = "{entity}"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    {fields}
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
```

### Endpoints to Create

| Method | Endpoint | Description | Status Codes |
|--------|----------|-------------|--------------|
| GET | `/api/v1/{entities}` | List with pagination | 200, 401 |
| GET | `/api/v1/{entities}/{id}` | Get by ID | 200, 404, 401 |
| POST | `/api/v1/{entities}` | Create | 201, 400, 409, 401 |
| PUT | `/api/v1/{entities}/{id}` | Full update | 200, 400, 404, 401 |
| PATCH | `/api/v1/{entities}/{id}` | Partial update | 200, 400, 404, 401 |
| DELETE | `/api/v1/{entities}/{id}` | Soft delete | 204, 404, 401 |

{If file uploads selected}
| POST | `/api/v1/{entities}/{id}/upload` | Upload file(s) | 201, 400, 404, 413 |
| GET | `/api/v1/{entities}/{id}/files` | List files | 200, 404 |
| DELETE | `/api/v1/{entities}/{id}/files/{file_id}` | Delete file | 204, 404 |

**Confirm?** Reply "yes" to generate, or specify changes.
```

### Phase 6: Code Generation

**Read skill references for patterns:**

1. Read `skills/fastapi/references/model-pattern.md`
2. Read `skills/fastapi/references/schema-pattern.md`
3. Read `skills/fastapi/references/repository-pattern.md`
4. Read `skills/fastapi/references/service-pattern.md`
5. Read `skills/fastapi/references/router-pattern.md`
6. Read `skills/fastapi/references/file-upload-pattern.md` (if file uploads)
7. Read `skills/fastapi/references/testing-pattern.md` (for test generation)

**Generation order (dependencies first):**

1. Model in `db/models.py`
2. Schemas in `api/schemas/{entity}_schemas.py`
3. Repository in `api/repositories/{entity}_repository.py`
4. Service in `api/services/{entity}_service.py`
5. Router in `api/v1/{entities}.py`
6. Register router in `app.py`

**Key patterns to follow:**

- **Session flow**: Session passed from router → service → repository
- **No session storage**: Never store session in `__init__`
- **CamelModel**: All response schemas inherit from CamelModel
- **Domain exceptions**: Use NotFoundError, ConflictError, ValidationError
- **Pagination**: Use PaginatedResponse for list endpoints

### Phase 7: Next Steps

```markdown
## Generation Complete

Your **{EntityName}** entity has been created successfully.

### Files Created/Modified

- [x] `db/models.py` - {EntityName} model added
- [x] `api/schemas/{entity}_schemas.py` - Created
- [x] `api/repositories/{entity}_repository.py` - Created
- [x] `api/services/{entity}_service.py` - Created
- [x] `api/v1/{entities}.py` - Created
- [x] `app.py` - Router registered

### Immediate Actions

1. **Create database migration:**
   ```bash
   alembic revision --autogenerate -m "add {entity} table"
   alembic upgrade head
   ```

2. **Test the API:**
   ```bash
   uvicorn app:app --reload
   # Visit http://localhost:8000/docs
   ```

### Related Actions

Would you like me to:

- [ ] **Generate Next.js page** for {EntityName} management?
      → `/generate data-table {entities}`

- [ ] **Create Celery tasks** for async {entity} operations?
      → `/generate task {entity}-sync`

- [ ] **Validate patterns** for the {EntityName} entity?
      → `/validate {entity}`

- [ ] **Generate another related entity**?
      → Tell me what entity to create next.
```

## Error Handling

### Entity Already Exists

```markdown
## Entity Exists

The entity **{EntityName}** already exists in your codebase.

### Current Implementation

| Component | Status | Path |
|-----------|--------|------|
| Model | Exists | `db/models.py` |
| Schema | Exists | `api/schemas/{entity}_schemas.py` |
| Repository | Exists | `api/repositories/{entity}_repository.py` |
| Service | Exists | `api/services/{entity}_service.py` |
| Router | Exists | `api/v1/{entities}.py` |

### Options

1. **Update existing** - Modify the existing entity (will require migration)
2. **Add missing parts** - Only create missing components
3. **Create new version** - Create {EntityName}V2
4. **Cancel** - Don't make changes

Which option do you prefer?
```

### Missing Dependencies

```markdown
## Missing Dependency

Cannot create **{EntityName}** because:

**Missing foreign key target: Category**

The `category_id` field references `category.id`, but the Category model doesn't exist.

### Options

1. **Create Category first**
   → `/generate entity category`
   Then create {EntityName}

2. **Remove the relationship**
   Create {EntityName} without category_id

3. **Specify different target**
   Provide correct foreign key target

Which option do you prefer?
```
