#!/usr/bin/env bash
# Tests fsa_repin_stale_release: a stale release pin follows the loaded release; a current pin or a dev tree is untouched.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$HERE/../scripts/lib/plugin-pin.sh"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
fail=0; check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
release() {
  mkdir -p "$tmp/$1/plugins/fullstack-agents/.claude-plugin"
  printf '{"git_sha":"%s"}' "$1" > "$tmp/$1/RELEASE.json"
  printf '{"version":"%s"}' "$1" > "$tmp/$1/plugins/fullstack-agents/.claude-plugin/plugin.json"
  (cd "$tmp/$1/plugins/fullstack-agents" && pwd -P)
}
old=$(release 1.0.0); new=$(release 2.0.0); pin="$tmp/pin.json"
fsa_plugin_pin "$old" > "$pin"
out=$(fsa_repin_stale_release "$new" "$pin"); rc=$?
check "stale pin re-pins" '[ $rc -eq 0 ] && [ "$out" = 1.0.0 ] && [ "$(jq -r .root "$pin")" = "$new" ]'
fsa_repin_stale_release "$new" "$pin" > /dev/null; rc=$?
check "current pin is left alone" '[ $rc -eq 1 ]'
mkdir -p "$tmp/dev/.claude-plugin"; before=$(cat "$pin")
fsa_repin_stale_release "$tmp/dev" "$pin" > /dev/null; rc=$?
check "dev tree never re-pins" '[ $rc -eq 1 ] && [ "$(cat "$pin")" = "$before" ]'
fsa_repin_stale_release "$new" "$tmp/missing.json" > /dev/null; rc=$?
check "missing pin is not created" '[ $rc -eq 1 ] && [ ! -e "$tmp/missing.json" ]'
exit $fail
