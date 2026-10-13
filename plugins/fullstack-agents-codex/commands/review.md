## Codex runtime binding

Follow the bundle's `AGENTS.md` and `fullstack-agents-task-flow`: Codex leads,
Claude audits bounded diffs through `scripts/handoff.py`. Read only relevant
skill sections once. Existing user authorization wins over historical approval
steps. Native Codex roles replace Claude tools/dispatchers/hooks below. Bundle
paths resolve from the bundle; skill paths resolve beside `SKILL.md`. Validate
explicitly; do not assume historical hooks or dashboards are running.

# Review Command

Review code for various quality aspects.

## Usage

```
$fullstack-agents-review [type] [target]
```

## Types

| Type | Agent | Description |
|------|-------|-------------|
| `quality` | review/code-quality | Code quality, best practices, maintainability |
| `security` | review/security | Security vulnerabilities, OWASP top 10 |
| `performance` | review/performance | Performance issues, N+1 queries, bottlenecks |
| `patterns` | review/patterns-compliance | Architecture pattern compliance |

## Target Options

- Specific file: `$fullstack-agents-review quality api/services/user_service.py`
- Entity: `$fullstack-agents-review patterns product`
- Directory: `$fullstack-agents-review security api/`
- All: `$fullstack-agents-review quality` (reviews changed files or full codebase)

## Examples

```bash
# Code quality review
$fullstack-agents-review quality api/services/order_service.py

# Security audit
$fullstack-agents-review security

# Performance review
$fullstack-agents-review performance api/routers/setting/product_router.py

# Pattern compliance for entity
$fullstack-agents-review patterns product
```

## Review Output

Each review produces a report with:

### Quality Review
- Naming convention issues
- Function complexity
- Code duplication
- Error handling gaps
- Documentation gaps

### Security Review
- SQL injection risks
- Authentication gaps
- Authorization issues
- Sensitive data exposure
- Dependency vulnerabilities

### Performance Review
- N+1 query detection
- Missing indexes
- Memory issues
- Blocking operations
- Caching opportunities

### Pattern Compliance
- Session flow validation
- Schema inheritance check
- CRUD helper pattern compliance
- SSR + simplified pattern check
- Context pattern validation

## Severity Levels

- **Critical** - Must fix immediately
- **Error** - Should fix before deployment
- **Warning** - Should be addressed
- **Info** - Suggestions for improvement
