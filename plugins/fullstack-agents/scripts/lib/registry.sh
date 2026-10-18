# Sourced by codex-task.sh: run record v2 (additive to v1 meta.json), lifecycle events and instruction hashes.

fsa_sha256() { [ -f "$1" ] && sha256sum "$1" | cut -d' ' -f1 || printf 'absent'; }

# Project instruction files every engine may load; hashed at dispatch and completion so a mid-run change is flagged.
fsa_instruction_hashes() {
  local root=$1 f
  {
    for f in "$root/AGENTS.md" "$root/CLAUDE.md" "$root"/.claude/rules/*.md; do
      f=${f#"$root"/}
      [ -f "$root/$f" ] && printf '%s\t%s\n' "$f" "$(fsa_sha256 "$root/$f")"
    done
    true
  } | jq -Rn '[inputs | select(length > 0) | split("\t") | {path: .[0], sha256: .[1]}]'
}

# Plugin identity of the scripts actually executing: version from the manifest, revision when it is a git tree.
fsa_plugin_identity() {
  local here=$1 plugin version sha="" dirty=null
  plugin=$(cd "$here/.." && pwd)
  version=$(jq -r '.version // ""' "$plugin/.claude-plugin/plugin.json" 2>/dev/null || true)
  if sha=$(git -C "$plugin" rev-parse HEAD 2>/dev/null); then
    [ -z "$(git -C "$plugin" status --porcelain -- . 2>/dev/null)" ] && dirty=false || dirty=true
  fi
  jq -n --arg root "$plugin" --arg version "$version" --arg sha "$sha" --argjson dirty "$dirty" \
    '{root: $root, version: $version, git_sha: (if $sha == "" then null else $sha end), dirty: $dirty}'
}

fsa_event() {
  local runs=$1 id=$2 state=$3 detail=${4:-}
  jq -cn --arg at "$(date -u +%FT%TZ)" --arg state "$state" --arg detail "$detail" \
    '{at: $at, state: $state} + (if $detail == "" then {} else {detail: $detail} end)' >> "$runs/$id.events.jsonl"
}

# fsa_meta_merge <runs> <id> <json-object>: shallow-merge fields into meta.json atomically.
fsa_meta_merge() {
  local meta="$1/$2.meta.json" tmp
  tmp=$(mktemp "$meta.XXXXXX") || return 0
  if jq --argjson add "$3" '. + $add' "$meta" > "$tmp" 2>/dev/null; then mv "$tmp" "$meta"; else rm -f "$tmp"; fi
}

# Engine session ids: Codex prints `session id:` in its log; opencode sessions are titled with the run id.
fsa_engine_session_id() {
  local engine=$1 log=$2 id=$3 root=$4 opencode_bin=${5:-opencode}
  case "$engine" in
    codex) sed -nE 's/^session id:[[:space:]]*([0-9a-f-]+).*/\1/p' "$log" 2>/dev/null | head -1 ;;
    grok) (cd "$root" && timeout 20 "$opencode_bin" session list --format json -n 50 2>/dev/null) |
            jq -r --arg t "$id" '[.[]? | select(.title == $t)] | first | .id // empty' 2>/dev/null ;;
  esac
  return 0
}
