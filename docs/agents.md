# Agents Reference

| Agent | Role |
|-------|------|
| `fullstack-agent` | Session lead: intake, plan, delegation, audit and the conclusion |
| `bounded-extractor` | Mechanical extraction from a known file list into a `file:line` table |
| `test-runner` | Runs the exact test and build commands it is given and saves full logs |
| `diff-reviewer` | Independent review of a saved diff through one lens (security, ux or code) |
| `web-researcher` | Public web sources only; returns a table of facts with source URLs |

The four review agents below back the `/review` command.

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
