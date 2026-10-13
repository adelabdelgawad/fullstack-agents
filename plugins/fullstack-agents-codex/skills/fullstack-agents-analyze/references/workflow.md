# Analyze Command

Analyze various aspects of your codebase.

## Usage

```
$fullstack-agents-analyze [target]
```

## Targets

| Target | Agent | Description |
|--------|-------|-------------|
| `codebase` | analyze/codebase | Full codebase analysis - structure, entities, health |
| `architecture` | analyze/architecture | System architecture, component relationships, data flow |
| `dependencies` | analyze/dependencies | Dependencies, versions, vulnerabilities |
| `patterns` | analyze/patterns | Coding patterns, conventions, styles |
| `scanning` | codebase-scanning | Auto-detect project patterns and coding style |

## Examples

```bash
# Full codebase overview
$fullstack-agents-analyze codebase

# Architecture analysis
$fullstack-agents-analyze architecture

# Check for outdated/vulnerable dependencies
$fullstack-agents-analyze dependencies

# Document coding patterns
$fullstack-agents-analyze patterns

# Scan codebase for patterns before generation
$fullstack-agents-analyze scanning
```

## Notes

The `scanning` type loads the `codebase-scanning` skill which detects project structure, naming conventions, and existing patterns. This is automatically triggered before the first code generation in any session, but can be run manually.

## Default Behavior

If no target specified, runs codebase analysis:

```bash
$fullstack-agents-analyze
# Equivalent to: $fullstack-agents-analyze codebase
```

## Process

1. **Detect project type** - FastAPI, Next.js, Docker, etc.
2. **Gather information** - Structure, files, patterns
3. **Analyze** - Based on target type
4. **Report** - Generate detailed report with recommendations

## Output

Each analysis produces a detailed markdown report including:
- Summary statistics
- Findings
- Recommendations
- Next steps
