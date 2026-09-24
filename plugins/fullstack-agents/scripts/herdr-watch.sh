#!/usr/bin/env bash
# Shows a background worker's transcript live in a herdr grid pane; no model reads it.
set -euo pipefail

file=${1:-}; label=${2:-worker}
[ -n "$file" ] || { echo "usage: herdr-watch.sh <transcript-file> [label]" >&2; exit 2; }
[ "${HERDR_ENV:-}" = 1 ] && [ -n "${HERDR_PANE_ID:-}" ] || { echo "herdr-watch.sh needs a Herdr-managed pane (HERDR_ENV=1)" >&2; exit 2; }

lib="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib"
. "$lib/herdr-grid.sh"

pane=$(herdr_worker_pane "$PWD")
herdr pane rename "$pane" "$label" > /dev/null
herdr pane run "$pane" "tail -F -n +1 '$file' 2>/dev/null | jq -Rr --unbuffered -f '$lib/herdr-transcript.jq'" > /dev/null
printf 'herdr_pane=%s (close it after the audit: herdr pane close %s)\n' "$pane" "$pane"
