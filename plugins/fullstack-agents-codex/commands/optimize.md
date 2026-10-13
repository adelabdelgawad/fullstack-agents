## Codex runtime binding

Follow the bundle's `AGENTS.md` and `fullstack-agents-task-flow`: Codex leads,
Claude audits bounded diffs through `scripts/handoff.py`. Read only relevant
skill sections once. Existing user authorization wins over historical approval
steps. Native Codex roles replace Claude tools/dispatchers/hooks below. Bundle
paths resolve from the bundle; skill paths resolve beside `SKILL.md`. Validate
explicitly; do not assume historical hooks or dashboards are running.

# Optimize Command

Optimize your codebase for performance, cleanliness, or maintainability.

## Usage

```
$fullstack-agents-optimize [type] [target]
```

## Types

| Type | Agent | Description |
|------|-------|-------------|
| `performance` | optimize/performance | Performance optimization (queries, caching) |
| `cleanup` | optimize/code-cleanup | Remove dead code, unused imports |
| `refactor` | optimize/refactoring | Improve code structure |
| `queries` | optimize/query-optimization | Database query optimization |

## Examples

```bash
# Optimize performance
$fullstack-agents-optimize performance api/routers/setting/products.py

# Clean up code
$fullstack-agents-optimize cleanup api/services/

# Refactor code
$fullstack-agents-optimize refactor api/services/order_service.py

# Optimize database queries
$fullstack-agents-optimize queries
```

## Optimization Types

### Performance Optimization

- Fix N+1 queries with eager loading
- Add Redis caching
- Optimize query column selection
- Add pagination
- Implement connection pooling

### Code Cleanup

- Remove unused imports
- Delete dead code
- Remove commented-out code
- Fix deprecated patterns
- Clean empty files

### Code Refactoring

- Extract methods
- Replace conditionals with polymorphism
- Introduce parameter objects
- Replace magic numbers with constants
- Improve naming

### Query Optimization

- Analyze execution plans
- Add missing indexes
- Fix N+1 queries
- Optimize JOIN operations
- Add partial indexes

## Output

Each optimization produces:
- List of changes made
- Before/after comparison
- Performance metrics (if applicable)
- Migration files (for indexes)
- Recommendations for further improvement

## Safe Mode

By default, optimizations show a preview before applying:

```
$fullstack-agents-optimize performance

## Optimization Plan

1. Add eager loading in product_service.py
2. Add index on product.category_id
3. Add caching for category list

Confirm? (yes/no)
```

## Bulk Optimization

Optimize entire codebase:

```bash
# Clean up entire codebase
$fullstack-agents-optimize cleanup

# Optimize all queries
$fullstack-agents-optimize queries
```
