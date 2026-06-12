---
name: rust-correctness
description: Rust language correctness reference — ownership and borrowing, lifetimes, async concurrency hazards, smart pointer selection, panic-vs-Result philosophy, and exhaustive pattern matching, with detectors for the forbidden patterns behind common compiler errors (E0382, E0499, E0502, E0597) and async bugs. Use when writing any non-trivial Rust, fixing borrow-checker or Send/Sync errors, or reviewing Rust for correctness. Do not use for Python.
---

# Rust Correctness Reference

The language-level discipline behind every Rust skill. Organized as forbidden
patterns with fixes — these are the bugs that compile (or almost compile) and
bite later.

## Ownership & Borrowing

Rules: every value has one owner; any number of `&` XOR exactly one `&mut`;
references never outlive their referent.

| Forbidden | Fix |
|---|---|
| `.clone()` to silence a borrow error | Restructure: shorten the borrow's scope, or split the struct |
| `&` and `&mut` to the same data alive together (E0502) | Narrow the shared borrow's lifetime (NLL ends a borrow at last use) |
| Returning a reference to a local (E0515) | Return the owned value |
| Moving out of a borrowed value (E0507) | `std::mem::take`/`replace`, clone deliberately, or take ownership |
| `&Vec<T>` / `&String` parameters | `&[T]` / `&str` — accept slices |
| Two `&mut` to the same data (E0499) | Split borrows per field, or reorder operations |

## Panic vs Result

- `Result` for ALL fallible operations — propagate with `?`.
- `panic!`/`unwrap`/`expect` ONLY in: tests, `main()` bootstrap, and genuinely
  unreachable invariants (with a message saying why).
- NEVER in handlers, use cases, repositories, or library code.
- `let Some(x) = opt else { return Err(...) }` — `let else` for early returns.

## Async Concurrency (Tokio)

| Forbidden | Why | Fix |
|---|---|---|
| `std::sync::MutexGuard` held across `.await` | Future becomes `!Send` — won't spawn | Drop the guard before awaiting, or `tokio::sync::Mutex` |
| `Rc`/`RefCell` in spawned tasks | `!Send` | `Arc` / `Arc<Mutex<T>>` |
| Blocking calls (`std::fs`, heavy CPU, `reqwest::blocking`) in async | Starves the runtime | `tokio::task::spawn_blocking` or async equivalents |
| Inconsistent lock acquisition order | Deadlock | One canonical order, documented |
| `.lock().unwrap()` everywhere | Poisoned mutex panics cascade | Handle `PoisonError` or use tokio Mutex (no poisoning) |
| DB connection held across unrelated `.await`s | Pool exhaustion | Acquire late, release early |

Channels (`mpsc`, `broadcast`, `watch`) over shared state where the data flows
one way.

## Smart Pointer Selection

| Need | Use |
|---|---|
| Heap allocation / recursive type | `Box<T>` |
| Shared ownership, single thread | `Rc<T>` |
| Shared ownership, multi-thread / async | `Arc<T>` |
| Interior mutability, single thread | `RefCell<T>` (runtime-checked) |
| Interior mutability, multi-thread | `Mutex<T>` / `RwLock<T>` (tokio variants in async) |
| Breaking reference cycles | `Weak<T>` |

`Arc<Mutex<T>>` with no writer is a smell — `Arc<T>` suffices for read-only.

## Lifetimes

- Let elision work; annotate only when the compiler asks.
- A named lifetime ties OUTPUT to INPUT: `fn first<'a>(s: &'a str) -> &'a str`.
- `'static` means "lives forever or owned" — don't reach for it to silence
  E0597; restructure ownership instead.

## Traits & Generics

- `impl Trait` in argument/return position for single concrete types; generics
  `<T: Trait>` when the caller chooses; `dyn Trait` when you need runtime
  dispatch or heterogeneous collections (ports use `Arc<dyn Repo>`).
- Implement `From`, get `Into` free — never implement both.
- Object safety: `async fn` in traits needs `#[async_trait]` for `dyn` use.

## Pattern Matching

- `match` must be exhaustive — avoid `_ =>` on YOUR OWN enums; adding a variant
  should break compilation everywhere it matters.
- `if let` for single-variant interest; `let else` for extract-or-return.
- `matches!()` for boolean checks.

## Iterators & Collections

- Iterator chains over index loops: `filter`/`map`/`collect` — lazy until consumed.
- `with_capacity` when the size is known.
- `entry()` API for HashMap upsert: `map.entry(k).or_insert_with(Vec::new).push(v)`.
- Closures: default borrow capture; `move` for spawned tasks and returns.

## Unsafe

Forbidden in application services. If FFI or a sound abstraction genuinely
requires it: isolate in one module, document the safety contract on every
`unsafe` block, and test the invariants. Never `transmute` as a shortcut.

## Compiler Error Quick-Route

| Error | Section |
|---|---|
| E0382 (use after move), E0499, E0502, E0505, E0507 | Ownership & Borrowing |
| E0106, E0515, E0597 (lifetime) | Lifetimes |
| "future cannot be sent between threads" | Async Concurrency |
| E0038 (not object safe) | Traits & Generics |
| non-exhaustive match | Pattern Matching |

When MULTIPLE compiler errors cascade: fix in dependency order, rebuild ONCE
(see batch-error-resolution).
