# Sourced by codex-task.sh: which changed paths a finished implement run cannot account for.

run_touched() {
  { comm -13 "$1/$2.pre.txt" "$1/$2.post.txt"; comm -23 "$1/$2.pre.txt" "$1/$2.post.txt"; } | cut -d' ' -f2- | sort -u
}

# A run without a post snapshot is still live, so its window ends now.
run_window() {
  local end
  end=$(date -r "$1/$2.post.txt" +%s 2>/dev/null || date +%s)
  printf '%s %s\n' "$(date -r "$1/$2.pre.txt" +%s)" "$end"
}

concurrent_allow() {
  local runs=$1 id=$2 root=$3 start end f oid os oe
  read -r start end < <(run_window "$runs" "$id")
  for f in "$runs"/implement-*.allow; do
    [ -f "$f" ] || continue
    oid=$(basename "$f" .allow)
    [ "$oid" != "$id" ] && [ -f "$runs/$oid.pre.txt" ] && [ -f "$runs/$oid.meta.json" ] || continue
    read -r os oe < <(run_window "$runs" "$oid")
    [ "$os" -le "$end" ] && [ "$oe" -ge "$start" ] || continue
    [ "$(jq -r '.root // ""' "$runs/$oid.meta.json")" = "$root" ] && cat "$f"
  done
  return 0
}

# Files the dispatching lead session wrote with its own edit tools while the run was live.
lead_edits() {
  local runs=$1 id=$2 root=$3 session transcript start end
  session=$(jq -r '.session // ""' "$runs/$id.meta.json" 2>/dev/null)
  [ -n "$session" ] || return 0
  transcript=$(ls "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"/projects/*/"$session.jsonl" 2>/dev/null | head -1)
  [ -n "$transcript" ] || return 0
  read -r start end < <(run_window "$runs" "$id")
  jq -r --argjson s "$start" --argjson e "$end" --arg root "$root/" '
    select(.type == "assistant" and (.timestamp | type) == "string")
    | select((.timestamp[:19] + "Z" | fromdateiso8601) as $t | $t >= $s and $t <= $e)
    | .message.content[]? | select(.type == "tool_use" and (.name | test("^(Edit|Write|MultiEdit|NotebookEdit)$")))
    | (.input.file_path // .input.notebook_path // "") | select(startswith($root)) | ltrimstr($root)' "$transcript" 2>/dev/null || true
}

run_outside() {
  local runs=$1 id=$2 root=$3 brief_dir claimed
  brief_dir=$(cd "$(dirname "$4")" && pwd)
  brief_dir=${brief_dir#"$root"/}
  claimed=$( { cat "$runs/$id.allow"; concurrent_allow "$runs" "$id" "$root"; lead_edits "$runs" "$id" "$root"; } | grep -E '\S' | sort -u || true)
  run_touched "$runs" "$id" | grep -vxF -f <(printf '%s\n' "$claimed") | awk -v p="$brief_dir/" 'index($0, p) != 1' || true
}
