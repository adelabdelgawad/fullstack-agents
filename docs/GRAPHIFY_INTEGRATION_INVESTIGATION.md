# Graphify Integration Investigation

**Date:** 2026-11-02
**Scope:** read-only investigation. Can Graphify's code or ideas improve how FSA understands a codebase?
**Status:** proposal awaiting approval. Nothing is implemented.

## Revisions inspected

| Repository | Revision | Notes |
|---|---|---|
| FSA | `b04e79b` (main, plugin 3.77.0) | Tree unchanged apart from this report. The untracked files belonging to another session were not touched. |
| Graphify | `32e5efe935e6844ef39a5e33409e4efe848f2172` (2026-11-01) | Package `graphifyy` 0.9.100. The `graphify/` package is 119,310 lines. Cloned to a scratchpad with `core.hooksPath=/dev/null`. |

**Evidence labels used below:**
- **[src]** read in source.
- **[repro]** observed in the bounded experiment (§9).
- **[claim]** documentation claim that was not verified.

## 1. Summary

- **Recommendation: Option C, a small FSA-native code map built in phases.** Priority 1 (freshness and fallback) has to be
  FSA-owned under every option: Graphify's `built_at_commit` stamps HEAD rather than content, the CLI never warns about a stale
  graph, and a symbol added since the build fails silently with rc=4 [repro].
- Graphify's tree-sitter graph also does not cover priority 2, fullstack tracing (Next.js → FastAPI/Axum → service → DB/Celery).
  - It has no route, HTTP or queue recognizers [src]. In the experiment it left the `fetch("/api/items")` ↔
    `@router.post("/api/items")` pair unlinked, while `rg` found both ends in 19 ms [repro].
  - It also misses the `.delay()` call edge, the `Depends()` edge and the env-var reader edges [repro].
- **Graphify is still useful as an optional phase-4 adapter** for symbol-level call and import graphs in large repositories. FSA
  would call it as an external CLI behind an opt-in binding, and never through its installer, hooks or CLAUDE.md block.
- **Do not vendor it.** The core is about 119k lines with ~25 grammar pins and an AST cache schema at version 34 that churns
  often. Vendoring would also bring Apache-2.0 §4 obligations.
- **No efficiency claim is made.** The only timings collected come from an 8–9 file synthetic sample, n=1 each.

## 2. FSA today (confirmed)

**Retrieval has no index.** There is no graph, LSP, ctags or tree-sitter anywhere in the plugin [src: grep across
`plugins/fullstack-agents`]. The retrieval ladder lives in `skills/task-flow/references/skill-guide.md:276` ("Scanning wide"):
1. `rg`
2. ranged reads
3. a delegated scan by `bounded-extractor` under a `FILES:` + `REPORT:` table contract

**Enforcement:**
- `hooks/scan-gate` (PreToolUse Agent|Task) refuses delegated scans that lack `FILES:`/`REPORT:` (lines 50–61) or that ask
  "why/assess/recommend". It is on only when `.claude/fsa-team.conf` sets `scan_gate=on`.
- `hooks/read-guard` blocks unranged reads above `read_range_max`.
- Both hooks resolve the root per worktree with `git -C <cwd> rev-parse --show-toplevel` (`scan-gate:20`, `read-guard:20`).
- Bindings are typed keys in `scripts/lib/team_conf.py:67-81`: `read_range_max`, `gated_extensions`, `carve_outs`, `scan_gate`,
  `generated_globs` and others. This is the pattern for a new opt-in key.

**Context management:**
- The `context-handoff` hook and `fsa-usage` script.
- Bounded reads. The lead re-reads every cited fact (lead prompt, "Authority").

**Decisions:**
- Every checkpoint must carry `decisions {id,text,source}` (`scripts/lib/task_checkpoint.py:20`, validated at `:161`).
- Project principles live in a constitution file (`skills/codebase-scanning/SKILL.md:30-31`; precedence is "Constitution >
  codebase patterns > skill references").
- Decisions are already separate from any generated artefact. Requirement "keep decisions separate" is therefore met and must
  stay that way.

**Verification:**
- `skills/task-flow/SKILL.md:55` says "affected test targets first".
- `skills/debug/SKILL.md:74` says "Run related tests: `pytest <test_file>`".
- Nothing discovers related tests automatically. This is a **gap**.

**Repository checks (from configuration; this investigation did not run them):**
- Test suites:
  - `python3 -m unittest discover -s tests/codex -v`
  - `python3 -m unittest discover -s tests/dashboard -v`
  - `python3 -m unittest discover -s tests/experiment -v`
- Hook tests: `bash plugins/fullstack-agents/hooks/<name>.test.sh`.
- Library tests: `bash plugins/fullstack-agents/scripts/lib/{run-scope,task-row}.test.sh`.
- Lint: `post-edit-validate` runs `ruff`/`rustfmt` on edited files.
- There is no CI, no `pyproject` and no repository-level type-check.
- `scripts/fsa-release` only does `git archive` export and hash `verify`. It runs no tests.
- `integrations/codex/scripts/build.py` renders the Codex bundle from the shared content (`docs/codex.md:80`). Any new skill text
  reaches Codex through it.

**Dependencies:** `scripts/lib/*.py` imports only the standard library plus sibling modules [src: import scan of 28 files]. A
new Python dependency would break that precedent.

**Vendoring precedent:** `scripts/lib/vendor/xterm/` ships `LICENSE` and `VERSION` beside the vendored code.

**Confirmed gaps:**
1. No structural relationships beyond what `rg` hits show.
2. No route ↔ client, task ↔ enqueue or env ↔ reader linking.
3. No related-test discovery.
4. No freshness notion, because nothing is cached.

## 3. Graphify's actual architecture

**Pipeline** (`ARCHITECTURE.md`; `extractors/engine.py` ~11k lines, `extract.py` 11.7k, `resolution.py` 4.4k) [src]:

| Stage | What happens |
|---|---|
| detect | Builds the in-scope file set, honouring `.graphifyignore` and `.gitignore` |
| extract | Per-language tree-sitter AST pass, plus an optional LLM semantic pass for docs, papers and images |
| build | Builds a NetworkX graph |
| cluster | Leiden or Louvain clustering |
| analyze / report | Writes `GRAPH_REPORT.md` |
| export | Writes `graph.json` (node-link), plus html, obsidian and cypher exports |

- **Output** goes to `graphify-out/` in the scan root, overridable with `GRAPHIFY_OUT` (`paths.py:4-53`).
- **Runtime dependencies:** networkx, numpy, rapidfuzz, pyyaml, `tree-sitter` 0.25 and ~25 `tree-sitter-<lang>` grammar packages.
  Optional extras: mcp/starlette, neo4j, watchdog and leiden.

**Graph schema:**
- Node: `{id, label, source_file, source_location "L42"}`.
- Edge: `{source, target, relation, confidence}`.
- Relations: `imports`, `imports_from`, `calls`, `indirect_call`, `contains`, `references`, `inherits`, `extends`,
  `instantiates`, `re_exports`, `uses_component`.
- `reads_from`/`writes_to` come only from `.sql` files. `route` is emitted only for Dart and Razor [src].

**Direct vs inferred edges:**
- The AST path emits only `EXTRACTED` and `INFERRED`.
- `AMBIGUOUS` comes only from the LLM pass (`skill.md:793`).
- Export scores confidence as 1.0, 0.55 and 0.2 (`export.py:213`).
- Resolution is conservative. Unknown types, conflicting assignments and shadowed names emit no call edge (`ARCHITECTURE.md`).
- **A missing edge therefore does not mean there is no dependency.** In the experiment, `globals()[...]` dispatch produced no edge
  [repro], which is correct but silent.

**LLM and network use:**
- `llm.py` holds the backends (Anthropic, OpenAI, Gemini, Ollama, Bedrock and others; base URLs at `llm.py:145-210`). It is used
  only by the semantic pass.
- `extract <path> --code-only` is "pure local AST, no key" (`cli.py:4140-4154`). `update` is a code-only rebuild
  (`cli.py:2885-2943`).
- Other network paths: `prs.py` (gh), `ingest.py` (URLs) and `security.safe_fetch`.
- The query log is off unless `GRAPHIFY_QUERY_LOG[_ENABLE]` is set (`querylog.py:17-35`).
- LLM input is wrapped as untrusted (`llm.py:631-657`).

**Queries:**
- The MCP server `serve.py` exposes `query_graph` (BFS/DFS, depth 1–6, `token_budget` default 2000), `get_node`,
  `get_neighbors`, `shortest_path`, `god_nodes` and PR tools.
- Seeds are scored by term, IDF and trigram over labels (`serve.py:222-580`), then the budget cuts the output (`:1125`, `:1316`).
- The CLI offers `query "<q>" --budget N`, `affected "<node>" [--relation R] [--depth N]`, `path` and `explain`.
- Exit codes: 3 when a name is ambiguous (rivals are listed, `serve.py:1938-2115`), 4 when nothing is found.
- `affected` walks reverse edges over `DEFAULT_AFFECTED_RELATIONS` (`affected.py:12-30`: calls, indirect_call, references,
  imports, imports_from, dynamic_import, re_exports, inherits, extends, implements, uses …), depth 2 by default.

**Freshness and updates:**
- **Content hashing.**
  - `cache.py` keeps a per-file sha256 with a size+mtime fast path and a racily-clean rule (`:290-315`).
  - The AST cache is keyed by extractor version, `_AST_CACHE_SCHEMA=34` and a grammar fingerprint (`cache.py:36-78`).
  - `manifest.json` stores `{mtime, seen, ast_hash, semantic_hash}` per file [repro].
- **Build stamp** (`watch.py:1732-1830`):
  - It records the epoch, scan root, a digest of the in-scope path set (which catches renames, deletes and ignore changes),
    flags and env knobs.
  - It is written only once `graph.json` is complete.
- **Concurrency and atomic writes.**
  - Rebuilds take an advisory `flock` lock that is released when the process dies (`watch.py:190-240`).
  - `graph.json` is written to a temp file and renamed into place (`watch.py:2653-2660`, `paths.py:84-216`).
  - The reconcile step fails closed on an unreadable graph, and a shrink guard refuses silent shrinkage (`watch.py:996-1040`,
    `:1483`).
- **Stale nodes.** Nodes whose source left the corpus are pruned (`cli.py:441-623`, `:854`).
- **Commit stamp.**
  - `graph.json` carries `built_at_commit` (`export.py:505`).
  - Only the MCP stats tool compares it with HEAD and warns (`serve.py:2900-2921`).
- **Git hooks** (`hooks.py`): post-commit, post-checkout (full rebuild on a branch switch, `:299`), post-merge and post-rewrite.
  The installer writes them into `core.hooksPath`, which is shared across worktrees (`:398`).

**Assistant integration (`install.py:477-520`):**
- It writes a block into `~/.claude/CLAUDE.md` or the project's `.claude/CLAUDE.md`.
- It copies a skill into `~/.claude/skills`.
- It adds PreToolUse hooks: `Bash|Grep` → `hook-guard search`, and `Read|Glob` → `hook-guard read`. Strict mode **denies** the
  first raw Read in each session (`cli.py:1143-1310`).
- The hooks inject labels taken from the repository into the agent's context, sanitised only by `sanitize_label`
  (`cli.py:231-287`).
- This directly conflicts with FSA's grep-first ladder and its read-before-edit rule.

**Fullstack tracing is absent [src + repro]:**
- There are no FastAPI, Celery, Axum or Next.js recognizers (grep).
- JS `app.get("/", handler)` becomes an `indirect_call` to the file, without the path (`engine.py:10712-10726`).
- `callflow_html.py:500-520` sorts nodes into api/ui/test by keyword for a visualisation only.
- Env vars appear only through `mcp_ingest` (`build.py:1307`).

**Limitations reproduced (§9):**
- `send_welcome.delay()` gives only an import edge and no call edge.
- `Depends(get_session)` gives no edge.
- A module that only reads `os.environ` yields no symbols.
- A test that reaches a route through `TestClient(app).post("/api/items")` is invisible to `affected post_item`.

## 4. Integration options

| Dimension | A: external CLI | B: vendor modules | C: FSA-native layer |
|---|---|---|---|
| Effort | Small: a subprocess adapter, env scrubbing and output parsing | Large: untangling `engine.py`/`extract.py`/`resolution.py` (~27k lines) from the CLI and installer | Medium: one stdlib module, `re` patterns per framework, a manifest |
| Maintenance | Pin a version and re-run the evaluation on each bump | High: cache schema at v34, frequent extractor changes, ~25 grammar ABI pins | Owned by FSA and small; patterns need updating per framework |
| Dependencies | Optional per-host venv, about 30 packages (18.6 s install [repro]) | Same packages, shipped with or required by the plugin | None (stdlib + `git`, already required). `code_map` never calls `rg`, which is a shell function absent from the subprocess `PATH` on this host |
| Licensing | Nothing redistributed, so no obligations | Apache-2.0 §4 applies: LICENSE copy, NOTICE text and modification notices (§10) | None |
| Portability | Python 3.10+ with grammar wheels; not tried on the host's Python 3.14, ran under uv 3.12 | Same, plus the Codex bundle copies via `build.py` | Same as FSA today |
| Upgrades | Bump the pin; FSA freshness logic stays independent | Manual merges against a fast-moving upstream | Not applicable |
| Likely performance | ≈0.3–0.6 s per query and ≈0.6–1 s per incremental update on 8 files, including interpreter start [repro]; large repositories not measured | Same | Measured on a 12,976-file export: cold build 6.2 s, no-op refresh 0.37 s, one-file edit 0.55 s, branch switch over 340 paths 0.44 s (`docs/code-map-eval/`) |
| Fullstack priority 2 | Not covered | Not covered | Covered by design (route-literal, enqueue and env joins) |

**Recommendation: C in phases 1–3, with A as an optional phase-4 adapter if the evaluation shows symbol-graph value. Reject B.**
- B costs more to maintain than the whole of FSA's `scripts/lib` and still lacks the fullstack edges.
- A is cheap and leaves upstream ownership with Graphify. It must run with `--code-only`, with `*_API_KEY` removed from the
  environment and with `GRAPHIFY_OUT` set outside the worktree.

## 5. Capability matrix

| Capability | Label | Why |
|---|---|---|
| Incremental updates from file hashes and revision metadata | Reusable with changes | Missing in FSA. Graphify's manifest and stamp design is sound [src], but `built_at_commit` records HEAD, not content. The graph held uncommitted edits under an unchanged stamp [repro]. FSA needs its own content-hash manifest; the stat fast path plus sha256 is the idea to borrow. |
| Task-scoped queries with token budgets | Unnecessary for the first phase | Only Graphify (A) has it, and A is optional. `--budget 200` gave 1,123 chars and `--budget 2000` gave 3,399 chars (whole graph) [repro]. FSA's `REPORT:` tables already bound delegated output, and §7's row budget covers the native layer. |
| Source locations and reads before edits | Already available | Lead prompt "Authority" plus the `scan-gate` `file:line` contract. Graphify nodes carry `source_file:L<n>` [repro], which fits the evidence envelope. |
| Fullstack tracing: UI → API client → route → service → DB | Missing | Absent in both FSA and Graphify. No route or HTTP linking in Graphify [src+repro]. Native route-literal join is phase 1. |
| Workers, queues, config and external integrations | Missing | Absent in both FSA and Graphify. `.delay()` produced only an import edge, env reads produced nothing [repro]. Native enqueue ↔ task and env-var ↔ reader joins. |
| Impact analysis (callers, consumers, contracts, schemas, tests) | Missing | Graphify (A) covers only calls and imports. `affected` found direct callers and direct-call tests but missed HTTP-client tests [repro]. Contracts and schemas are missing in both. |
| Fallback to search when results are weak, incomplete or stale | Missing | The rule must be FSA-owned. CLI `query`/`affected` print no staleness warning after HEAD moved and return rc=4 "No matching nodes" for a symbol added since the build [repro]. FSA must treat rc 3/4, empty or stale results as a cue to fall back to `rg`. |
| Repository and worktree isolation, including uncommitted changes | Reusable with changes | FSA hooks already resolve the root per worktree. Graphify writes `graphify-out/` inside the tree, where it shows up untracked [repro] and collides with FSA's "untracked = another session" rule. Its git hooks share `core.hooksPath` across worktrees [src]. |
| Separate, source-backed project decisions | Already available | Checkpoint `decisions {id,text,source}` plus the constitution. The code map must never be written into them. |

## 6. Freshness and failure design (native layer; the adapter inherits it)

**Store:**
- Location: `${XDG_CACHE_HOME:-~/.cache}/fullstack-agents/code-map/<sha1(toplevel)>/`, as `plan_usage.py` does. It sits outside every worktree and is keyed by
  `git rev-parse --show-toplevel`, the same root the hooks use.
- Contents: one `index.json` of `{path: {size, mtime_ns, sha256, facts}}`, plus `HEAD`, the format and extractor versions
  and a `complete` flag.

| Event | Detection | Action |
|---|---|---|
| File edit, including uncommitted | stat differs, then the hash differs | Re-scan that file only, on the next query (lazy) |
| Rename or delete | The path set from `git ls-files -co --exclude-standard` differs | Drop the old entries and scan the new paths |
| Branch switch | `HEAD` differs and many paths differ | Same per-file rule, with no full-rebuild threshold: 340 changed paths refreshed in 0.44 s. No git hooks are installed. |
| Separate worktree | Different toplevel | Separate store; nothing shared |
| Interrupted indexing | `complete` flag missing; lock held by a dead PID | Write to a temp file and rename; take an `flock` lock as Graphify does; ignore a partial store and rebuild |
| Format or extractor change | Format or extractor version differs | Discard and rebuild |
| Lock busy, timeout, crash, git unavailable, invalid `fsa-team.conf` | Exception inside `query()` | **Warn once and fall back to the current ladder.** Never block an edit, hook or reply. |

**Rules for repository content:**
- Repository content is data.
- Labels, strings and comments reach the lead only as quoted values inside a table row, never as instructions.
- No hook injects code-map text into context. Only an explicit lead query does.

## 7. Minimal retrieval workflow

1. **Trigger.** Only a full-path task, a cross-layer question or an impact question, with the opt-in key `code_map=on`. A
   light-path edit with known sites skips it entirely (`rg` stays rung 0).
2. **Query.** The lead names the seeds: symbols, a route literal, a task name or an env key. Each query states a depth (default
   1) and a row budget (default 40 rows).
3. **Evidence envelope.** One row per relationship:
   `kind | from path:line | to path:line | relation | provenance (pattern id or graphify relation + EXTRACTED/INFERRED) | fresh (yes/stale/unknown)`.
4. **Expand only when needed.** The lead reads the cited ranges itself, the same rule that applies to worker output today.
   - It widens depth or the budget only for a named unresolved edge.
   - It falls back to `rg` or `bounded-extractor` when no row is joined (both `from` and `to` set) or the status is
     `fallback` (CLI exit code 3). Rows are never stale: every query refreshes the store first.
5. **Tests.** Rows with relation `tests` list test files that reference the route, env key, table or task. These become the "affected
   test targets first" input for `test-runner`.

## 8. Phased plan (each phase independently testable)

| Phase | Deliverable | Acceptance |
|---|---|---|
| 0 | Baseline evaluation on a real fullstack repository with current FSA (§9 protocol, arm "current") | Tasks, revision and scoring sheet frozen; results recorded |
| 1 | `scripts/lib/code_map.py` (stdlib), with tests in `tests/dashboard/test_code_map.py`: manifest, freshness, lock, fallback | Unit tests cover edit, rename, delete, branch switch, interrupted run, format bump, git missing, lock busy and invalid conf → fallback; the tree stays clean; it is a no-op when the key is off |
| 2 | Framework joins: route literal (FastAPI `@router.<verb>`, Axum `.route`, Next.js `fetch`/server actions), enqueue ↔ task (`.delay`/`.apply_async`/`send_task`), env key ↔ readers, test references | Each join tested on fixtures, including documented misses (template literals, base-URL prefixes, `{id}` vs `${id}`); the envelope matches §7 |
| 3 | Opt-in key `code_map` in `team_conf.py`; one paragraph in `skill-guide.md` "Scanning wide"; Codex render via `build.py` | Hook and unit tests green; the key is off by default and nothing changes when it is off |
| 4 (optional) | Graphify adapter (`code_graph=graphify`): `--code-only`, env scrubbed, `GRAPHIFY_OUT` outside the tree, FSA freshness check, rc 3/4 → fallback, stdout captured | Adapter tests with a fake binary; evaluation shows a gain over phase 2 on at least one task class, otherwise it is dropped |

**Outcome (2026-11-02, `docs/code-map-eval/README.md`):**
- Phases 0–3 are built and checked. Phase 2 recovers no missed `must` site on the deterministic proxy, but its rows are
  far more precise than rung 0's. Keep or drop is decided by the LLM arm (P0b), which is not run yet.
- Phase 4 was probed and dropped. Graphify recovered no missed `must` site on T1–T3. It binds no edge for a cross-crate
  module-path call (`rustpbx_call_group_repo::dialed_number_exists(...)`), so no adapter was built.

## 9. Evaluation

**Collected [repro], n=1 each, synthetic sample:**
- Sample: 8 code files (Next.js page and client, FastAPI router, service, SQLAlchemy model, Celery task, env config, test).
- Environment: Python 3.12 uv venv, HOME and XDG redirected into the scratchpad.

| Measurement | Result |
|---|---|
| Install dependencies (uv, cold cache) | 18.6 s |
| Initial `extract . --code-only` | 2.17 s; 27 nodes, 35 edges |
| No-op `update` / one-file edit / rename / delete | 0.93 s / 1.00 s / 0.88 s / 0.59 s |
| `query --budget 600` / `affected` | 0.56 s / 0.30–0.43 s |
| `rg` over the same five seeds | 0.019 s, 15 hits; found both ends of `/api/items` |
| Output size | `graphify-out/` 140 KB |

**Reproduced behaviour:**
- **Correct:**
  - Edit, rename and delete updates were correct: new `notify()` → `send_welcome` call edge, old `api/tasks.py` nodes gone,
    deleted test nodes gone.
  - JSX `onClick={onSave}` resolved to `ItemsPage → createItem`.
- **Missed:**
  - The cross-layer edge was missing.
  - `.delay()` and `Depends()` produced no call edges.
  - The env-only module produced no symbols.
  - The HTTP-client test was missed, including after `api/main.py` (`include_router`) completed the fixture.
  - There was no stale warning from the CLI.

**Proposed experiment (not run):**
- **Setup:**
  - Same repository revision for every arm. Arms: current FSA, FSA + native map (phase 2), and FSA + Graphify adapter.
  - Run on a real Next.js + FastAPI (or Axum) repository chosen by the user.
  - Reuse the `tests/experiment/` runner pattern (`docs/EXPERIMENT_RUNNER.md`), with 3 runs per arm.
- **Tasks:**
  1. Navigation: "where is X defined and who calls it".
  2. Cross-layer feature: add a field from the UI through the DB.
  3. Indirect-dependency bug: a Celery task or env change that breaks a route.
  4. Control case where `rg` should win: rename a string constant.
- **Measures:**
  - Correctness against a hand-written answer key.
  - Missed dependencies (key edges not cited).
  - Tokens (`fsa-usage`) and elapsed time.
  - Initial index time and update time after a one-file edit and after a branch switch.
- **Decision rule:** keep a phase only if it cuts missed dependencies without raising tokens on tasks 1 and 4.

## 10. Licensing (Graphify @ `32e5efe`)

**Files found:**
- `LICENSE` is Apache-2.0.
- `LICENSE-MIT` reads "Copyright 2026 Safi Shamsi".
- `NOTICE` says some portions were contributed under MIT before the relicence, without naming which.
- `graphify/` and `tools/` have no SPDX or Copyright headers [src: grep, 0 files].
- No other LICENSE or NOTICE files are in the repository.

**Dependency licences** (dist-info metadata in the experiment venv):
- `tree-sitter` and every grammar: MIT. `tree-sitter-elixir` contradicts itself (`License: Apache-2.0`, MIT classifier).
- networkx: BSD-3-Clause.
- numpy: BSD-3-Clause plus bundled MIT, 0BSD and Zlib.
- rapidfuzz and pyyaml: MIT.

**Obligations:**
- **Option A:** nothing is redistributed, so there are no obligations. Pin and document the version.
- **Option B** (Apache-2.0 §4) requires all of the following:
  - a copy of `LICENSE`;
  - the `NOTICE` text;
  - a prominent notice on each modified file;
  - keeping existing attributions.
  - Since the MIT-era portions are unidentified, `LICENSE-MIT` should be shipped too. The `vendor/xterm/{LICENSE,VERSION}`
    layout fits.
- **Option C:** no code is copied, so there are no obligations. Ideas (hash fast path, lock, atomic rename) are not copyrightable
  expression. Write them fresh, without copying code.

## 11. Suggested permanent rules (only where justified)

- One rule for the lead prompt or the `task-flow` skill, rather than CLAUDE.md:
  "Code-map or graph rows are leads: read the cited range before relying on one; an absent edge never proves an absent
  dependency." This is justified by the silent rc=4 and the missing `.delay`/HTTP edges [repro].
- No CLAUDE.md rule is needed until phase 3 ships.
- Never run `graphify install` or `hook-guard` in an FSA project. This belongs in the adapter's documentation, not CLAUDE.md.

## 12. Unresolved questions (cannot be answered from the repositories)

1. Which real fullstack repository and revision should the phase 0 and §9 evaluation use? Answered: keep-connect at
   `b93cac20e` ("use ours").
2. Is an optional per-host Python venv acceptable for phase 4, or should FSA stay stdlib-only for good? Answered: either,
   chosen by measured performance and stability. It is moot because phase 4 was dropped.

## 13. Commands run and checks not performed

**Commands run:**
- **Session 1, all read-only:**
  - FSA: `git rev-parse/status/ls-files`, plus `grep`/`sed` reads of the files cited above.
  - Graphify: `git clone` with hooks disabled, then `grep`/`sed` reads.
- **Session 2:**
  - Ranged reads that closed the remaining source questions.
  - Global config hashes taken before and after the experiment.
  - `uv venv --python 3.12` and `uv pip install -r requirements` (Graphify's dependencies only). Graphify itself was not
    installed; it ran from a copied package via `PYTHONPATH`.
  - The `graphify` commands `extract --code-only`, `update`, `query --budget` and `affected`.
  - `rg`.
- Every experiment command and its exit code and timing are logged in the session scratchpad `commands.log` (51 lines). Two
  commands failed: `unshare -rn` (denied) and the first write of `tests/test_items_http.py` (the `tests/` directory had been
  removed by the delete probe; the log line for it does not show the failure). The stale-symbol probes returned rc=4 as intended.

**Side effects verified:**
- These hashes are unchanged before and after the experiment:
  - `~/.claude/settings.json`
  - `~/.claude/CLAUDE.md`
  - `~/.claude-anthropic/settings.json`
  - global `core.hooksPath` (unset)
  - `~/.claude/skills`
- The redirected HOME holds only uv's Python marker files.
- FSA `git status` shows only this report on top of the pre-existing untracked files.

**Checks not performed:**
- **No network isolation.** `unshare -rn` was denied. No-LLM operation rests on `--code-only` [src], and no API keys were present
  in the environment (count 0).
  - `GRAPHIFY_TELEMETRY=0` was set but is not a real Graphify setting. The query log is off by default [src].
- **Source-verified only, not reproduced:** interrupted indexing, format change, worktree isolation and the git-hook behaviour.
- **Not exercised:** the MCP server and the LLM pass.
- **Not run:** FSA's own test suites, because no FSA code changed.
- **Not measured:** large-repository performance and README/BENCHMARKS claims [claim].
