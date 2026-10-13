#!/usr/bin/env bash
# Explicit checks: no auto-installs, no guessed service roots, no silent skips.
set -euo pipefail
lane=${1:-}; root=${2:-}
if [[ -z "$root" || ! -d "$root" ]]; then
  echo 'usage: validate.sh python|rust|frontend SERVICE_ROOT' >&2
  exit 2
fi
cd "$root"
case "$lane" in
  python)
    if command -v uv >/dev/null 2>&1; then
      uv run --no-sync --offline ruff check .
      uv run --no-sync --offline mypy .
    else
      ruff check .
      mypy .
    fi
    ;;
  rust)
    cargo fmt --all --check
    cargo clippy --workspace --all-targets -- -D warnings
    cargo test --workspace
    ;;
  frontend)
    if [[ ! -x node_modules/.bin/tsc ]]; then
      echo 'missing local TypeScript compiler; install project dependencies first' >&2
      exit 2
    fi
    node_modules/.bin/tsc --noEmit
    # Project-specific lint runners supersede this npm default.
    npm run lint
    ;;
  *) echo "unknown lane: $lane" >&2; exit 2 ;;
esac
