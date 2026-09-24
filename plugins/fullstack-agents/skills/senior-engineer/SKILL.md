---
name: senior-engineer
description: Senior-engineer discipline for architecture, modularity, and duplication prevention with YAGNI — search-before-implement, build only what is asked, composition over monoliths, SOLID boundaries, aggressive complexity reduction, and leave-it-cleaner refactoring. Use before writing, modifying, or refactoring ANY application code, and when asked to refactor, clean up, reduce duplication, or extract shared logic. Do not use for docs-only, config-only, or dependency-bump changes.
---

# Senior Engineer: Architecture, Modularity, and Duplication Prevention

## Objective

Continuously improve code structure, maintainability, and long-term scalability by reducing duplication, lowering complexity, and maximizing reuse of existing components.

**This skill is RIGID.** The Required Workflow below is not advisory — it runs before every implementation, the same way codebase-scanning does.

## Required Workflow Before Any Implementation

```
1. INVESTIGATE  -> Understand the existing architecture around the change
2. SEARCH       -> Find existing implementations, helpers, and patterns (recipe below)
3. ASSESS       -> Identify duplication risks; decide reuse vs extract vs create
4. PLACE        -> Decide whether the functionality belongs in an existing module
5. DESIGN       -> Choose the smallest maintainable solution
6. IMPLEMENT    -> Use existing patterns; compose, don't accumulate
7. REFACTOR     -> If the task's own code duplicates existing logic, extract it NOW; report wider duplication
8. VERIFY       -> Behavior unchanged unless change was explicitly requested
```

**Do NOT skip to step 6.** Steps 1–5 are what make the difference between a senior
implementation and a fast one.

### The Search Recipe (step 2, concrete)

Before writing a function, helper, component, or utility, run targeted searches:

```bash
# Does this already exist by name or concept?
grep -ri "validate.*email\|email.*valid" --include="*.py" --include="*.ts"
grep -ri "def format_\|function format" api/ lib/

# Where do shared helpers live in THIS project?
ls api/utils/ api/services/ lib/ lib/utils/ components/ hooks/ 2>/dev/null

# Is there a similar entity/feature to copy the SHAPE from (not the code)?
ls api/crud/ api/schemas/ "app/(pages)/setting/" 2>/dev/null

# Who already solves the adjacent problem?
grep -rl "the-domain-term" --include="*.py" --include="*.tsx" | head -10
```

Adapt the patterns to the task. The point is non-negotiable: **two minutes of
searching beats two hours of refactoring duplicated logic later.**

## Core Principles

### 1. Prefer Small, Cohesive Modules

- Organize code into focused modules with a single clear responsibility.
- Avoid large files that mix unrelated concerns.
- Split functionality into logical packages, services, hooks, utilities, components, or libraries.
- Design modules to be independently understandable and reusable.

### 2. Composition Over Monoliths

- Build behavior by composing small, specialized components.
- Avoid creating large classes, services, or modules that accumulate multiple responsibilities.
- Favor explicit composition and dependency injection over tightly coupled implementations.

### 3. Enforce SOLID and Clean Architecture

- Maintain clear separation between:
  - Presentation layer (routers, pages, components)
  - Application/business logic layer (services)
  - Domain layer (models, schemas)
  - Data access/infrastructure layer (CRUD helpers, fetch utilities)
- Dependencies always point inward toward business logic.
- Introduce an interface or abstraction only when a second real implementation or a test
  double needs it today — never for hypothetical flexibility.
- Prevent framework, transport, or storage concerns from leaking into domain logic.

### 4. Reduce Complexity Aggressively

- Use guard clauses and early returns.
- Minimize nested conditionals — never exceed 4 levels.
- Eliminate unnecessary branching.
- Simplify control flow whenever possible.
- Optimize for readability before cleverness.

### 5. Eliminate Duplication

Before implementing any new functionality:

1. Search the entire codebase for existing implementations (Search Recipe above).
2. Identify reusable utilities, services, helpers, hooks, libraries, or components.
3. Reuse existing functionality whenever practical.
4. If similar logic exists in multiple locations:
   - Extract the common behavior into the smallest shared function that serves them.
   - Migrate the consumers the task touches; list the rest rather than widening the diff.

**Never knowingly introduce duplicated business logic.**

### 5a. YAGNI — Build Only What Is Asked

- Implement the requested behavior and nothing speculative: no unused parameters,
  options, config flags, feature toggles, plugin points, generic type parameters or
  "for later" branches.
- One use is not a pattern. Abstract on the second real use, found by search, not
  an imagined one.
- Delete, don't preserve: no commented-out code, no dead fallbacks, no compatibility
  shims nobody calls.
- Scope is the request. An improvement the task does not need goes in the report as
  a suggestion, not into the diff.

### 6. Centralize Shared Functionality

Evaluate existing shared libraries BEFORE creating new code for common concerns:
validation, formatting, parsing, serialization, error handling, authentication
helpers, authorization helpers, API utilities, database utilities, configuration
management. In this plugin's architecture these typically live in `api/utils/`,
`api/services/`, `core/`, `lib/`, and `components/` — check the codebase-scanning
profile for the project's actual locations.

### 7. Design for Testability

- Keep units small and focused.
- Ensure functions have clear inputs and outputs.
- Avoid hidden side effects.
- Isolate infrastructure concerns from business logic.
- Structure code so unit testing is straightforward.

### 8. Prefer Self-Documenting Code

- Use descriptive names.
- Make intent obvious through structure.
- Add comments only when explaining rationale, constraints, or non-obvious decisions.
- Avoid comments that merely restate code behavior.

### 9. Control File Size and Cognitive Load

Hard limits (senior-engineer discipline — keep new growth within these):

| Unit | Limit |
|------|-------|
| Function | < 50 lines |
| File | < 800 lines (200–400 typical) |
| Nesting | <= 4 levels |

- Split files that become difficult to navigate.
- Avoid "god files" and "god modules."
- Optimize for maintainability by future engineers.

### 10. Improve Existing Code During Modifications

When touching existing code:

- Reuse what exists instead of adding a parallel version.
- Improve naming and control flow in the lines you are already changing.
- **Leave the codebase cleaner than it was found** — scoped to the code you touch;
  do not turn a one-line fix into an unrequested rewrite. Wider cleanups are reported,
  not done.

## Rationalization Prevention

These thoughts mean STOP — you're rationalizing skipping the discipline:

| Thought | Reality |
|---|---|
| "It's faster to copy the existing function" | Copying forks the logic forever. Extract or import — the shared version costs minutes, the fork costs every future change twice. |
| "I'll extract the duplication later" | Later never comes. Step 7 says NOW, while both copies are in your head. |
| "A small private helper here won't hurt" | Three small private helpers in three files IS the duplication problem. Search first. |
| "This file is already huge, one more function won't matter" | Growth in a god file compounds. Place it where it belongs or split. |
| "An abstraction would be overkill for two uses" | Maybe — then reuse without abstracting. But you can't know until you've found the other use. Search first. |
| "The existing helper almost fits but not quite" | Extend the helper with a parameter before writing a parallel one. |
| "Refactoring the consumers is out of scope" | If you created the shared abstraction, migrating the touched consumers IS the scope; list the rest. |
| "We'll probably need this option later" | Then add it later, when the need is real. Unused options are code to maintain and test now. |
| "Let me make this generic while I'm here" | Generic for one caller is speculation. Write the concrete version. |
| "I'll clean up this nearby code too" | Not asked, not in the diff. Report it. |
| "This is a prototype, structure doesn't matter" | Prototypes ship. Apply at least limits and placement. |

## Definition of Done (per change)

- [ ] Searched for existing implementations before writing new code
- [ ] No knowingly duplicated business logic introduced
- [ ] New code placed in the architecturally correct layer/module
- [ ] Functions < 50 lines, files < 800 lines, nesting <= 4 levels
- [ ] No framework/transport/storage concerns inside domain logic
- [ ] Discovered duplication extracted and the touched consumers migrated
- [ ] Nothing speculative: no unused parameter, option, flag, abstraction or branch
- [ ] Diff limited to what the task needs; wider improvements reported, not made
- [ ] Touched code left cleaner than found (naming, control flow, boundaries)
- [ ] Behavior unchanged unless the change was explicitly requested

## Expected Outcomes

- Reduced duplication and higher code reuse
- Smaller and more maintainable modules
- Clear architectural boundaries
- Easier testing and lower cognitive load
- Improved long-term scalability and maintainability
