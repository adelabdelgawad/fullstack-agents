#!/bin/sh
# Scratch dashboard on 127.0.0.1 whose herdr is session fsatest, never the live one.
set -eu
port=${1:-18766}
root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
bin=$(mktemp -d)
real=$(command -v herdr || true)
if [ -n "$real" ]; then
  printf '#!/bin/sh\nexec %s --session fsatest "$@"\n' "$real" > "$bin/herdr"
  chmod +x "$bin/herdr"
fi
PATH="$bin:$PATH" exec python3 "$root/plugins/fullstack-agents/scripts/fsa-dashboard" serve \
  --repo "$root" --host 127.0.0.1 --port "$port"
