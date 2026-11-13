# Fullstack Agents

A Claude Code plugin that makes the AI work like a careful senior engineer: **one lead takes
responsibility for every task and follows a fixed workflow**. It is built for web apps with Python
(FastAPI) or Rust (Axum) backends and a Next.js frontend. The rules are not just advice — **the
plugin blocks the AI when it tries to skip a step**. And it is **cheap to run**: expensive thinking
goes only where it is needed.

```bash
/plugin marketplace add https://github.com/adelabdelgawad/fullstack-agents
/plugin install fullstack-agents
```

There is also a version for Codex: see [Codex setup](docs/codex.md).

## The rules

1. **One lead is responsible.** The lead finds the cause, makes the plan, checks the work and gives
   the answer. It can hand out work, but never the thinking or the final decision.
2. **Helpers give facts, not answers.** The lead checks every claim against the real code before it
   acts. Test results count only after the lead reads them itself.
3. **Cheapest tool first.** A plain search comes before any AI. Helpers are asked for facts, never
   for opinions.
4. **Know-how before code.** For each request, the plugin picks the right guides. The AI cannot
   edit code until it has read them. Python, Rust and frontend rules never mix.
5. **Plan, build, check.** Small changes the lead makes itself. Bigger ones go to a helper with a
   strict written job. The lead reviews the whole change once, after the tests pass. If a fix fails
   twice, it stops and reports.
6. **Your project's rules win.** Each project can set its own rules, and they always come first.
7. **Safe with other sessions.** Several AI sessions can share one project without stepping on
   each other. If you say "do not deploy", nothing deploys until you say so.

## The workflow

| Path | When | What happens |
|------|------|--------------|
| **Short** | Questions, research, small safe fixes | Read the right guide, fix, check, review the change |
| **Full** | Bigger work, risky files, database changes, releases | Written plan (reviewed when risky), task list, helpers working in parallel, full test run, one final review |

## Helpers

The lead hands out **work, never the thinking**. Each helper gets a narrow job and returns a short
list of facts. The lead checks those facts before it uses them.

```text
Lead (strongest model) ── finds the cause · plans · reviews · decides
 │
 ├─ fact finder    (smallest model)  reads given files    → short list of facts
 ├─ web researcher (mid model)       public docs only     → facts with links
 ├─ test runner    (mid model)       runs the tests       → full results saved for the lead
 ├─ reviewer       (mid model)       security · UX · code · plan → list of problems
 └─ implementer    (mid model, or Codex / Grok on request)
                                     strict job, allowed files only → the code change
 │
 └─► Lead checks every fact, reads the change and the test results, then decides
```

- **A clear job**: each implementer gets the goal, the plan, the exact files it may touch, and the
  checks that prove it is done.
- **A fence**: the implementer cannot change files outside its list. The lead does not touch those
  files while the implementer works.
- **In parallel**: jobs that touch different files run at the same time.
- **No blind trust**: "finished" is not "accepted". The lead reviews every change. After two failed
  fixes it stops and reports.
- **Code review on demand**: `/review` runs four review agents — quality, patterns, performance and
  security.
- **Watch live**: say "use herdr" to see each helper work in its own window.

More: [Agents](docs/agents.md).

## Long tasks do not lose their way

AI conversations get slow and forgetful when they grow too long. Before that happens, the plugin
hands the task to a fresh conversation with nothing lost.

```text
 conversation gets too long  ──►  lead saves progress     ──►  short hand-over note
                                  (task list + evidence)       goal · done · next step
                                                                        │
 fresh conversation loads the note  ◄──  you approve (or it is approved for you)
 → same task list, same checks, continues where it stopped
```

- **At the right moment**: after a big investigation, it can hand over as soon as the plan is
  ready, so the building starts with a clean slate.
- **Never mid-job**: it waits until no helper or test is still running.
- **Your instructions carry over**: a "do not deploy" stays in force in the new conversation.
- **Survives restarts**: after a restart or a shortened conversation, the task list comes back.

## A task list you can see

Bigger tasks keep a written task list, one line per piece of work. It shows on the dashboard, it
moves to the new conversation at a hand-over, and **the AI cannot just stop while items are still
open** — it must finish them or say what it is waiting for.

## It saves money

Every step re-reads the whole conversation, so the plugin keeps the conversation small and gives
each job to the cheapest model that can do it.

| How | Result |
|-----|--------|
| **Guides load in small pieces** | Only a short summary loads first; details load when needed. The ten largest guides load **83% less text** at the start |
| **The right model for each job** | The strongest model only thinks and decides; fact finding, tests, reviews and coding go to cheaper models |
| **Search before AI** | Plain search tools answer what they can; helpers return short lists, not whole files |
| **Short path by default** | Small jobs skip the paperwork |
| **Only what matters** | Long files and test logs stay on disk; only the important lines enter the conversation |
| **Fresh start before overload** | Long tasks move to a clean conversation instead of an overloaded one |

More: [Token efficiency](docs/token-efficiency.md).

## The rules are enforced

| The plugin stops the AI from... |
|---------------------------------|
| Editing code before it read the right guides |
| Changing more files by hand than the project allows, or touching off-limit files |
| Editing files a helper is still working on |
| Reading huge files whole, or sending a helper out without a clear list of files and questions |
| Leaving style errors behind (Python and Rust code is checked after every edit) |
| Stopping while the task list still has open items |
| Deploying after you said "do not deploy", or while another session is deploying |
| Running out of room in a long conversation without saving its progress |

## Safe for teams

- A **shared board** shows which session works on what. Sessions take turns for releases, restarts
  and database changes, and a deploy is blocked while another session is deploying.
- Each session works on **its own copy of the code**, or follows the project's own branch rules.
- A project can write down its **main principles** in one short file (a "constitution"); the plugin
  checks work against it.

## Try it

Open a project and ask in plain words:

```text
add a "deleted" flag to products and hide deleted products from the list
the campaigns page takes 4 seconds to open, find out why
/review security src/api/
```

`/dashboard` opens a live view of every AI session and helper on your machine.

## What it knows

| Area | Tools |
|------|-------|
| Python | FastAPI, SQLAlchemy, Pydantic, Celery |
| Rust | Axum, SQLx, Tokio |
| Frontend | Next.js, React, TanStack Table, Tailwind |
| Servers | Docker, PostgreSQL, Redis, Nginx |

Plus debugging, moving an app to a new framework, safe changes to live data and browser call audio —
33 guides in all: [full list](docs/skills.md).

## More

[Getting started](docs/getting-started.md) · [Agents](docs/agents.md) · [Commands](docs/commands.md) ·
[Skills](docs/skills.md) · [Token efficiency](docs/token-efficiency.md)

Author: [Adel Abdelgawad](https://github.com/adelabdelgawad) · License: MIT
