#!/usr/bin/env bash
# Self-check for out-of-scope attribution. Run: bash scripts/lib/run-scope.test.sh
set -uo pipefail

source "$(dirname "$0")/run-scope.sh"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
runs="$tmp/runs" root="$tmp/repo" other="$tmp/other"
mkdir -p "$runs" "$root/.codex-briefs" "$other"
brief="$root/.codex-briefs/unit.md"
: > "$brief"

export CLAUDE_CONFIG_DIR="$tmp/config"
mkdir -p "$CLAUDE_CONFIG_DIR/projects/repo"

# run <id> <root> <start> <end|live> <allowed paths...>; touched paths go in <id>.post.txt via touch_paths.
run() {
  local id=$1 r=$2 start=$3 end=$4
  shift 4
  printf '%s\n' "$@" > "$runs/$id.allow"
  jq -n --arg root "$r" '{root: $root, session: "lead-1"}' > "$runs/$id.meta.json"
  : > "$runs/$id.pre.txt"
  touch -d "@$start" "$runs/$id.pre.txt"
  if [ "$end" != live ]; then
    : > "$runs/$id.post.txt"
    touch -d "@$end" "$runs/$id.post.txt"
  fi
}
touch_paths() {
  local id=$1 end
  shift
  end=$(date -r "$runs/$id.post.txt" +%s)
  printf 'h %s\n' "$@" | sort > "$runs/$id.post.txt"
  touch -d "@$end" "$runs/$id.post.txt"
}

now=$(date +%s)
iso() { date -u -d "@$1" +%Y-%m-%dT%H:%M:%S.000Z; }
edit() { jq -cn --arg ts "$(iso "$1")" --arg f "$2" --arg tool "${3:-Edit}" '{type: "assistant", timestamp: $ts, message: {content: [{type: "tool_use", name: $tool, input: {file_path: $f, command: $f}}]}}'; }
{
  edit $((now - 300)) "$root/docs/lead.md" Write
  edit $((now - 300)) "$root/src/lead_bash.rs" Bash
  edit $((now - 9000)) "$root/src/lead_before.rs"
} > "$CLAUDE_CONFIG_DIR/projects/repo/lead-1.jsonl"
run implement-1-me "$root" $((now - 600)) $((now - 60)) src/mine.rs
run implement-2-parallel "$root" $((now - 590)) $((now - 100)) src/parallel.rs
run implement-3-before "$root" $((now - 5000)) $((now - 4000)) src/before.rs
run implement-4-elsewhere "$other" $((now - 590)) $((now - 100)) src/elsewhere.rs
run implement-5-live "$root" $((now - 120)) live src/live.rs
touch_paths implement-1-me src/mine.rs src/parallel.rs src/before.rs src/elsewhere.rs src/live.rs \
  .codex-briefs/next.md src/unclaimed.rs docs/lead.md src/lead_bash.rs src/lead_before.rs

got=$(run_outside "$runs" implement-1-me "$root" "$brief" | tr '\n' ' ')
want="src/before.rs src/elsewhere.rs src/lead_bash.rs src/lead_before.rs src/unclaimed.rs "

fail=0
chk() {
    if [ "$2" = "$3" ]; then
        echo "ok   $1"
    else
        echo "FAIL $1 (want '$2', got '$3')"
        fail=1
    fi
}
chk "own, overlapping-run, live-run, brief and in-window lead-edit paths are claimed; the rest is out of scope" "$want" "$got"

run implement-6-clean "$root" $((now - 50)) $((now - 40)) src/clean.rs
touch_paths implement-6-clean src/clean.rs
chk "a run touching only its own paths has nothing out of scope" "" "$(run_outside "$runs" implement-6-clean "$root" "$brief")"

exit $fail
