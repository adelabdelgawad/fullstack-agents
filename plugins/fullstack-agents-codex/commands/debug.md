## Codex runtime binding

Follow the bundle's `AGENTS.md` and `fullstack-agents-task-flow`: Codex leads,
Claude audits bounded diffs through `scripts/handoff.py`. Read only relevant
skill sections once. Existing user authorization wins over historical approval
steps. Native Codex roles replace Claude tools/dispatchers/hooks below. Bundle
paths resolve from the bundle; skill paths resolve beside `SKILL.md`. Validate
explicitly; do not assume historical hooks or dashboards are running.

# Debug Command

> **Note:** All debug subcommands load the `debug` skill (`skills/fullstack-agents-debug/SKILL.md`) which enforces root-cause-first discipline: **REPRODUCE → INVESTIGATE → FIX → VERIFY**. No fixes without understanding the root cause.

Debug various issues in your application.

## Usage

```
$fullstack-agents-debug [type]
```

## Types

| Type | Agent | Description |
|------|-------|-------------|
| `error` | debug/error-diagnosis | Diagnose errors and stack traces |
| `logs` | debug/log-analysis | Analyze application logs |
| `performance` | debug/performance-profiling | Profile performance bottlenecks |
| `api` | debug/api-debugging | Debug API requests/responses |
| `batch` | batch-error-resolution | Resolve multiple errors systematically |

## Examples

```bash
# Diagnose an error (paste error after command)
$fullstack-agents-debug error
# Then paste your error/stack trace

# Analyze logs
$fullstack-agents-debug logs

# Profile performance
$fullstack-agents-debug performance

# Debug API issues
$fullstack-agents-debug api

# Resolve multiple errors systematically
$fullstack-agents-debug batch
```

## Debug Process

### Error Diagnosis

1. **Parse** - Extract error type, message, location
2. **Analyze** - Read related code
3. **Identify** - Find root cause
4. **Suggest** - Provide fix options

### Log Analysis

1. **Discover** - Find log files
2. **Extract** - Find errors, warnings, patterns
3. **Analyze** - Group by type, frequency, time
4. **Report** - Provide insights and recommendations

### Performance Profiling

1. **Identify** - Target endpoint or function
2. **Profile** - Add timing, analyze queries
3. **Measure** - Break down time by component
4. **Optimize** - Suggest improvements

### API Debugging

1. **Capture** - Request and response details
2. **Analyze** - Status codes, headers, body
3. **Diagnose** - Find issue (auth, CORS, validation, etc.)
4. **Fix** - Provide solution

## Debug Output

Each debug session produces:
- Problem identification
- Root cause analysis
- Code context
- Solution options
- Prevention recommendations

## Quick Debug Commands

```bash
# Check recent errors
$fullstack-agents-debug logs | grep error

# Profile specific endpoint
$fullstack-agents-debug performance GET /setting/products

# Debug CORS issue
$fullstack-agents-debug api cors

# Debug 500 error
$fullstack-agents-debug api 500
```
