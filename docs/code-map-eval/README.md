# Code-map evaluation (P0)

Frozen evaluation set for the FSA-native code map (`docs/GRAPHIFY_INTEGRATION_INVESTIGATION.md` §8–§9).

## Corpus

- keep-connect at `b93cac20e`, tree `579c1d9065bc7fdbc1b93ab7e58fec5d1871f59e`, 14,471 files.
- Evaluated on an export, never the live checkout:
  `git -C keep-connect archive b93cac20e | tar -x && git init && git add -f . && git commit`.
  `git add -f` is required: 619 tracked files match keep-connect's `.gitignore`. Without it the export tree differs.
- `rung0.py` refuses to run when the corpus tree hash differs from `tasks.json`.

## Tasks (`tasks.json`)

| ID | Class | Seeds (from the task wording only) |
|---|---|---|
| T1 | Navigation: definition, callers, HTTP endpoints | `dialed_number_exists` |
| T2 | Cross-layer feature: add a call-group field from the form to the DB and the engine | `call_group`, `call-group`, `CallGroup` |
| T3 | Indirect dependency: `RUSTPBX_RECORDINGS_DIR` readers, dependent routes, engine counterpart | `RUSTPBX_RECORDINGS_DIR` |
| T4 | Control, where `rg` should win: rename a validation code | `ring_timeout_secs_out_of_range` |

- **D5:** T3 uses keep-connect `env::var` readers. The Celery enqueue join is not evaluated here. It stays in P2 with fixture
  tests, and autodialer-pro@22a5fd89 is the fallback corpus for it.
- **Answer keys were written by reading the code, not from search output.** Each entry is a `path` plus a line range
  (`lines`), `must` or `should`, with the reason. The range spans the enclosing function or block up to the relevant line, so
  citing either the definition or the exact line counts. T4 is the exception: its key is the complete `git grep -F` result, which is the correct answer for a
  rename.
- **Generated files** (`generated: true`, here `schema.d.ts`) are `should` entries only and never count toward recall.

## Rung-0 baseline (`rung0-results.json`)

**This is rung 0, not the "current FSA" arm.** It is fixed-string `rg --sort path -n -F` over the frozen seeds, with no
model, no follow-up searches and no reads. An LLM arm (P0b) needs the experiment runner, a dedicated token and spend.

- Run with: `python3 -I docs/code-map-eval/rung0.py <export> --rg <path-to-rg>`. ripgrep 15.1.0; median of 3 runs. stdin is
  closed and the path `.` is explicit, because `rg` with no path reads an inherited stdin and hangs.
- **Measures:**
  - `site_recall`: share of `must` entries with at least one hit inside their line range.
  - `file_recall`: share of `must` files hit.
  - `file_precision`: share of hit files that appear anywhere in the key.

| Task | Site recall | File recall | Hits / files | File precision | Median s |
|---|---|---|---|---|---|
| T1 | 0.385 | 0.5 | 5 / 3 | 1.0 | 0.132 |
| T2 | 0.636 | 0.818 | 1132 / 190 | 0.068 | 0.377 |
| T3 | 0.462 | 0.6 | 29 / 22 | 0.409 | 0.130 |
| T4 | 1.0 | 1.0 | 8 / 4 | 1.0 | 0.127 |

**What rung 0 misses:**
- **T1 and T3:** the handler → router hops (`router.rs`), because route registration never names the seed. T3 also misses
  the engine's `recorder_path` (`services/rustpbx/src/config.rs:297`).
- **T2:** 6.8% file precision, so the lead has to sift 190 files for 22 `must` sites. The seeds miss the form's
  field-level lines and both locale files (`callGroups.json`), which no compiler checks.
- **Decision rule (§9):** a code-map phase is kept only if it cuts missed `must` sites on T1–T3 without lowering T4 recall or
  raising cost on T1 and T4.
- **Host note:** `rg` is a shell function on this host and is absent from the subprocess `PATH`, so `--rg` is explicit.

## Rung-0 + map arm (P2), protocol frozen before the first run

- **Seeds:** the same frozen seeds as rung 0. No expansion from hits, no second query.
- **Query:** `code_map.match(index, seeds, budget=40)` at depth 1 on a fresh full index of the pinned export
  (`code_map_joins` extractor, cache under the scratchpad via `XDG_CACHE_HOME`).
- **Fallback:** when no returned row is joined (both `from` and `to` set), the map contributes nothing, as `query()` does.
- **Hits:** rung-0 hits plus every `from`/`to` site of the returned rows. Scored with `rung0.score`, unchanged.
- **Also reported:** map rows, `truncated`, and the map's own sites scored alone (`map_only`).
- **Timings** run on a `git clone` of the export, never the export itself: cold build, no-op refresh, one-file edit,
  branch switch (a branch that edits 300, deletes 20 and adds 20 eligible files). Median of 3 where repeatable.
- **Expected before running:** little or no recall gain on T1–T3. The frozen seeds already appear on both ends of the
  route and table joins, and the T1/T3 misses are handler → router hops through a call graph the map does not model.

## Rung-0 + map results (`map-arm-results.json`)

Run with `python3 -I docs/code-map-eval/map_arm.py <export> --rg <path-to-rg> --work <scratch dir>`.

| Task | Map rows (joined) | Site recall: rung 0 → +map | File precision: rung 0 → +map | Map alone: site recall / sites / file precision |
|---|---|---|---|---|
| T1 | 0 (falls back) | 0.385 → 0.385 | 1.0 → 1.0 | none |
| T2 | 40, truncated | 0.636 → 0.636 | 0.068 → 0.068 | 0.182 / 44 / 0.312 |
| T3 | 18 | 0.462 → 0.462 | 0.409 → 0.409 | 0.462 / 9 / 1.0 |
| T4 | 0 (falls back) | 1.0 → 1.0 | 1.0 → 1.0 | none |

- **Recall:** no missed `must` site recovered on T1–T3, as predicted. By the §9 rule this deterministic proxy gives no reason
  to keep P2. The deciding run is the LLM arm (P0b), where the measure is tokens and missed sites, not raw hits.
- **Precision:** the map's own rows are far narrower than rung 0. On T3, 9 cited sites reach rung 0's recall with every file
  in the key, against 29 hits in 22 files. On T2, 44 sites in 16 files against 1,133 hits in 190 files.
- **T4 control:** unchanged. No map row matches the seed, so the arm falls back to rung 0.

| Timing on the 12,976-file clone | Seconds | Files rescanned |
|---|---|---|
| Cold build | 6.22 | 12,976 |
| No-op refresh (median of 3) | 0.37 | 0 |
| One-file edit (median of 3) | 0.55 | 1 |
| Branch switch (300 edited, 20 deleted, 20 added) | 0.44 | 320 (20 dropped) |

Store: 4.2 MB `index.json`, outside the worktree.

Rerun after the FastAPI decorator fix (extractor `d7758e702ee2`, against `a7b5e120ebd1` in the JSON): every task's rows,
recall and precision are identical. The export has no FastAPI routes. Timings under host load 14–22 on 16 cores: cold 7.35 s,
no-op 0.41 s, one-file edit 0.50 s, branch switch 0.55 s. The recorded file is kept as the idle-host measurement.

## Documented misses of `code_map_joins` (each pinned by a fixture in `tests/dashboard/test_code_map_joins.py` where testable)

- A URL built only from variables (`api.get(url)`, `` `${BASE_URL}${path}` ``, `` `${basePath}/${id}` ``) emits no fact; nor
  does the root route `/` or any all-parameter path.
- Prefix stripping is global: one `.nest("/v1")`, `prefix="/v1"` or `BASE_URL = "/v1"` strips `/v1` from every route key.
- SQL in `.rs`/`.py`/`.ts` counts only uppercase keywords; lowercase SQL there is missed (`.sql` is case-insensitive).
  `INSERT INTO t(cols)` with no space reads as a function call and is missed.
- Celery canvas (`.s()`, `.si()`, `signature()`) is not an enqueue.
- Comment-only lines are skipped for env, table and task facts; route facts are not comment-filtered.
- Rust inline `#[cfg(test)]` modules are not test files; only test paths are.
- Next.js `export { handler as GET }` and server actions called as functions are not modelled.
- A TS server route outside Next.js route handlers (Express `router.get("/x", h)`) reads as a client call, not a provider.
- Calls between functions (handler → service → repository) are not modelled. These are the T1 and T3 misses.

## Graphify probe (P4), protocol frozen before the first run

- **Question:** does Graphify's code-only graph recover a `must` site that both rung 0 and the rung-0 + map arm miss?
  An adapter (`code_graph=graphify`) is built only if it does on at least one of T1–T3 without lowering T4 recall.
- **Tool:** Graphify `32e5efe` (package `graphifyy` 0.9.100), installed from a local clone into a scratchpad venv.
- **Corpus:** a fresh `git clone` of the export in the scratchpad, tree hash checked before and after; the export itself
  is never read by Graphify. P0 C1 reruns afterwards as the export tripwire.
- **Environment:** `env -i` with only `PATH`, `HOME` and `GRAPHIFY_OUT` in the scratchpad; no `*_API_KEY` variable reaches
  the process.
- **Build:** `graphify extract . --code-only` under `timeout 600`. An install failure, a build failure or the timeout ends
  the probe as "P4 skipped", with the log as evidence and no retry.
- **Arm:** for each frozen seed, `graphify affected "<seed>" --depth 2` and `graphify query "<seed>" --budget 2000`, both
  on the built graph. Hits are every `path:line` printed by `affected` and every `src=<path> loc=L<n>` printed by `query`,
  with paths made relative to the clone. Scored with `rung0.score`, unchanged; also scored as the union with rung 0.
- **Recovery:** a `must` entry missed by both `rung0-results.json` and `map-arm-results.json` and covered by Graphify's
  hits.
- **Expected before running:** little or no recovery. The T1/T3 misses are router registrations that pass the handler as a
  value (`get(handler)`) in another file, and Graphify binds calls within a file (D14); its cross-file `references` edges
  are untested here.

## Graphify probe results (`graphify-arm-results.json`)

Run with `python3 -I docs/code-map-eval/graphify_arm.py <clone> --graphify <venv>/bin/graphify --rg <path-to-rg> --home <dir>
--out <dir>`. Build: 171.8 s, rc 0, 89,621 nodes; 1,328 `.sql` files contributed nothing (`tree_sitter_sql` not installed).

| Task | Graphify alone: site recall / hits / files / file precision | With rung 0: site recall | Recovered |
|---|---|---|---|
| T1 | 0.077 / 53 / 13 / 0.154 | 0.385 | none |
| T2 | 0.091 / 184 / 51 / 0.137 | 0.636 | none |
| T3 | 0.0 / 34 / 13 / 0.0 | 0.462 | none |
| T4 | 0.0 / 55 / 51 / 0.02 | 1.0 | none |

- **Decision:** no `must` site recovered on T1–T3, so no adapter is built and P4 is skipped. The clone tree was unchanged.
- **Why, T1:** `affected dialed_number_exists` finds no callers. The services call the free function across crates by
  module path (`rustpbx_call_group_repo::dialed_number_exists(...)`, `call_groups_service.rs:298` and `:397`), and Graphify
  binds no edge for that call. This answers D14's open cross-file question for this corpus.
- **Budget check, outside the frozen protocol:** T1 `query` truncates at 60 of 120 nodes under `--budget 2000`. At
  `--budget 8000` all 120 print, and none falls inside a missed `must` range.
- `affected` exits 3 or 4 (no unique node) for 4 of 7 seeds and finds no nodes for a fifth (T1); each command costs 8–12 s
  on this graph.
