# Fullstack Agents

AI-powered fullstack development toolkit for Claude Code. **28 agents**, **8 commands**, **7 skills** for intelligent code generation, review, analysis, and optimization.

## Installation

```bash
# Add the marketplace
/plugin marketplace add https://github.com/adelabdelgawad/fullstack-agents

# Install the plugin
/plugin install fullstack-agents
```

## What's Included

### 28 Specialized Agents

| Category | Count | Purpose |
|----------|-------|---------|
| **Generate** | 7 | Smart code generation with interactive dialogue |
| **Review** | 4 | Code quality, security, performance, patterns |
| **Analyze** | 4 | Codebase, architecture, dependencies, patterns |
| **Scaffold** | 5 | Project and module scaffolding |
| **Debug** | 4 | Error diagnosis, log analysis, profiling |
| **Optimize** | 4 | Performance, cleanup, refactoring, queries |

### 8 Commands

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

### 7 Skill Domains

- **FastAPI** - Backend API patterns (model, schema, repository, service, router)
- **Next.js** - Frontend patterns (pages, components, server actions)
- **Data Table** - TanStack Table with CRUD operations
- **Fetch Architecture** - Client/server fetch utilities
- **Celery** - Background task patterns
- **Tasks Management** - APScheduler job patterns
- **Docker** - Container infrastructure patterns

## Supported Technologies

| Category | Technologies |
|----------|-------------|
| **Backend** | FastAPI, SQLAlchemy 2.0, Pydantic, Celery, APScheduler |
| **Frontend** | Next.js 15+, React 19, TanStack Table, SWR, Tailwind |
| **Infrastructure** | Docker, Docker Compose, Nginx, PostgreSQL, Redis |

## Key Features

### Smart Code Generation

Unlike static templates, our agents:
- **Detect existing patterns** in your codebase
- **Ask clarifying questions** about relationships and edge cases
- **Match your coding style** automatically
- **Suggest next steps** after generation

### Interactive Dialogue

```
/generate entity product

## Entity Configuration

I've analyzed your codebase and detected:
- Bilingual fields (name_en/name_ar): Yes
- Soft delete (is_active): Yes
- Audit fields: Yes

What fields should this entity have?
```

### Multi-Agent Orchestration

```
/generate fullstack order

# Orchestrates:
1. generate/fastapi-entity → Backend CRUD
2. generate/api-route → Next.js API routes
3. generate/nextjs-data-table → Management page
```

## Quick Start

```bash
# Check project status
/status

# Generate a backend entity
/generate entity product

# Generate a data table page
/generate data-table products

# Generate complete fullstack feature
/generate fullstack order

# Review code patterns
/review patterns product

# Analyze codebase
/analyze codebase
```

## Documentation

- [Agents Reference](docs/agents.md)
- [Commands Reference](docs/commands.md)
- [Skills Reference](docs/skills.md)
- [Getting Started Guide](docs/getting-started.md)

## Architecture

```
plugins/fullstack-agents/
├── agents/
│   ├── _core/          # Base patterns for all agents
│   ├── generate/       # Code generation agents
│   ├── review/         # Code review agents
│   ├── analyze/        # Analysis agents
│   ├── scaffold/       # Scaffolding agents
│   ├── debug/          # Debugging agents
│   └── optimize/       # Optimization agents
├── commands/           # Slash commands
└── skills/             # Domain knowledge
    ├── fastapi/
    ├── nextjs/
    ├── data-table/
    ├── fetch-architecture/
    ├── celery/
    ├── tasks-management/
    └── docker/
```

## Philosophy

> **Compounding Engineering**: Each unit of engineering work should make subsequent units of work easier—not harder.

This plugin embodies this philosophy by:
1. **Learning from your codebase** - Detecting and following your patterns
2. **Building on existing work** - Extending rather than replacing
3. **Automating the repetitive** - So you can focus on the unique

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

**Adel Abdelgawad**
- GitHub: [@adelabdelgawad](https://github.com/adelabdelgawad)
