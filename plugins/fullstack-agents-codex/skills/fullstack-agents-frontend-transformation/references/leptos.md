# Target: Leptos

Read with `SKILL.md`: fidelity rules are unchanged; only the target idioms differ. The Leptos code is
Rust, so `rust-correctness` and `rust-quality-gates` apply to it, and the source's skills (`nextjs`,
`data-table`, `fetch-architecture`) describe what is being replicated, not how to write the target.
The API names below are Leptos 0.8 (the version a 10-03 evaluation pinned, 0.8.21 with router 0.8.16);
check the current release and its migration notes before starting.

## Decide the rendering mode first

| Mode | Build | Data | Fits when |
|---|---|---|---|
| CSR | Trunk, `wasm32-unknown-unknown` | the browser calls the existing REST API | the backend API stays as is; the evaluation used this |
| SSR + hydrate | `cargo-leptos`, Axum integration | `#[server]` functions or the REST API | first paint must come from the server |

Either way the backend contract does not change: the same endpoints, parameters, payloads, CSRF and
refresh flow. Server functions never re-implement backend rules (validation, permissions, scope
filtering, counts); the client renders what the API returns. Port page by page behind a path prefix
(`public_url = "/leptos/"` in `Trunk.toml`, routed by the proxy) so both frontends run side by side.

## Concept map

| Next.js / React | Leptos |
|---|---|
| `page.tsx`, `layout.tsx`, nested layouts | `#[component]` functions; `<Router>`, `<Routes>`, `<ParentRoute>` + `<Outlet/>` |
| dynamic segment `[id]`, `useParams` | `path!("/campaigns/:id")`, `use_params_map()` |
| `useSearchParams`, `router.replace` | `use_query_map()`, `use_navigate()` with `NavigateOptions { replace: true, .. }` |
| `useState` | `signal()` / `RwSignal::new` |
| `useMemo`, derived values | `Memo::new` or a closure over signals |
| `useEffect` | `Effect::new` for side effects only, never for derived state; cleanup in `on_cleanup` |
| context providers | `provide_context` / `use_context` |
| `{cond && <X/>}` | `<Show when=... fallback=...>` |
| `items.map(...)` | `<For each=... key=...>` keyed by the record id, never the index |
| SWR / fetch on mount | `LocalResource` (CSR) or `Resource` (SSR) inside `<Suspense>` |
| keep old rows while refetching | `<Transition>` instead of `<Suspense>` |
| server action, `useMutation` | `Action::new` (pending state, latest value) calling the API or a `#[server]` fn |
| `next/link` | `<A href=...>` |
| shadcn / Base UI component | no equivalent: port its rendered DOM (below) |
| lucide icon component | inline SVG with the published paths, `aria-hidden="true"` |
| `Intl.DateTimeFormat` | `js_sys::Intl::DateTimeFormat` with an explicit `timeZone` |

## Fidelity method

- Capture the source page's rendered DOM into a reference file, indexed by section, and port the
  markup from it: element structure, classes, `role`, `aria-*`, `data-slot`/`data-state` attributes and
  inline SVG. Copy component markup verbatim; never rebuild it from memory.
- Styling: keep the class names. Either serve the source's compiled CSS (then only classes present in
  it exist) or run Tailwind with content globs that include `*.rs`.
- Requests: same endpoints and query mapping, same debounce, refresh and reconnect constants; the
  URL stays the single source of truth for list state. Record every intentional difference (for
  example one shared `EventSource` instead of two).
- A side-by-side screenshot audit is required; the evaluation's first port drifted in fixed column
  widths and truncation, header resizer markup, the row-actions overflow menu, and switch markup
  (`data-*` state, `aria-disabled`, `tabindex`, Space/Enter activation).
- Inventory Arabic/RTL, accessibility and long-session memory explicitly: the evaluation did not
  cover them.

## Rust and WASM rules

- No `unwrap()`/`expect()` on fallible JS interop, no `unsafe`, no `#[allow]`; `clippy -D warnings`
  must pass (dead fields are removed, not allowed).
- Use the web-sys `set_*` setters (`RequestInit::set_method`, `EventSourceInit::set_with_credentials`);
  the builder forms are deprecated. Every web-sys type used is listed in the crate's `features`.
- Never `Closure::forget()`: store timer, interval and `EventSource` closures and drop them after
  clearing the timer, in `Drop` or `on_cleanup`.
- Auth: CSRF token cached in memory with one refetch-and-retry on a CSRF 403; one in-flight refresh
  shared by concurrent 401s, then one retry; a failed refresh redirects to `/login?next=`.
- `EventSource` does not reopen once `CLOSED`: own the reconnect backoff and reset it on `open`.
- Release profile: `opt-level = "z"`, `lto = true`, `codegen-units = 1`, `panic = "abort"`; Trunk
  `filehash = true`.

## Measure before deciding

The evaluation (keep-connect `reports/2026-10-03-leptos-vs-nextjs-campaigns-comparison.md`) found, on
one list page: data painted about 4× sooner, 6× less main-thread script, and 0–13 ms against 52–96 ms
to apply an update. Live-update latency was equal (the gateway dominates), and reconnect time followed
each retry schedule, not the framework. Most early per-interaction gaps were defects in the Next.js
code, fixed before the comparison. Keep three categories apart in any comparison: framework,
source-implementation defects, environment; fix and re-measure the source before crediting the target.
