#!/usr/bin/env bash
# Dispatch one implementer unit (Grok via opencode by default, Codex on FSA_IMPLEMENTER=codex); prints only the manifest.
set -euo pipefail

herdr_mode=0
[ "${1:-}" = "--herdr" ] && { herdr_mode=1; shift; }
mode=${1:-}; brief=${2:-}
[ -n "$mode" ] && [ -f "$brief" ] || { echo "usage: codex-task.sh [--herdr] investigate|plan|implement <brief-file>" >&2; exit 2; }
if [ "$herdr_mode" = 1 ]; then
  [ "${HERDR_ENV:-}" = 1 ] && [ -n "${HERDR_PANE_ID:-}" ] || { echo "--herdr needs a Herdr-managed pane (HERDR_ENV=1)" >&2; exit 2; }
fi

engine=${FSA_IMPLEMENTER:-grok}
case "$engine:$mode" in
  codex:investigate) model=${FSA_CODEX_MODEL_INVESTIGATE:-gpt-5.6-luna}; sandbox=read-only ;;
  codex:plan)        model=${FSA_CODEX_MODEL_PLAN:-gpt-5.6-sol};         sandbox=read-only ;;
  codex:implement)   model=${FSA_CODEX_MODEL_IMPLEMENT:-gpt-5.6-sol};    sandbox=workspace-write ;;
  grok:investigate)  [ "${FSA_GROK_INVESTIGATE:-0}" = 1 ] || { echo "wide scans default to grep, ranged reads, then the bounded-extractor (Haiku); set FSA_GROK_INVESTIGATE=1 to spend Grok on one" >&2; exit 2; }
                     model=${FSA_GROK_MODEL_INVESTIGATE:-xai/grok-4.7}; sandbox=read-only ;;
  grok:plan)         echo "plan runs belong to Claude, the orchestrator; Grok only investigates or implements" >&2; exit 2 ;;
  grok:implement)    model=${FSA_GROK_MODEL_IMPLEMENT:-xai/grok-4.7};   sandbox=workspace-write ;;
  *) echo "FSA_IMPLEMENTER must be grok|codex and mode investigate|plan|implement" >&2; exit 2 ;;
esac
case "$engine" in
  codex) command -v codex > /dev/null || { echo "codex CLI not found" >&2; exit 2; } ;;
  grok)  opencode_bin=${FSA_OPENCODE_BIN:-$(command -v opencode || echo "$HOME/.opencode/bin/opencode")}
         [ -x "$opencode_bin" ] || { echo "opencode CLI not found (the Grok engine runs through opencode)" >&2; exit 2; }
         oc_auth=${XDG_DATA_HOME:-$HOME/.local/share}/opencode/auth.json
         [ -n "${XAI_API_KEY:-}" ] || jq -e 'has("xai")' "$oc_auth" > /dev/null 2>&1 ||
           { echo "no xAI credential: run 'opencode auth login' (xAI) or export XAI_API_KEY" >&2; exit 2; } ;;
esac

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root=${FSA_CODEX_ROOT:-$(git rev-parse --show-toplevel)}
runs=${FSA_CODEX_RUNS_DIR:-$HOME/.codex/fsa-runs}; mkdir -p "$runs"
schema="$root/.claude/codex-result.schema.json"; [ -f "$schema" ] || schema="$here/codex-result.schema.json"
id="$mode-$(date +%Y%m%d-%H%M%S)-$$"
last="$runs/$id.last.txt"; log="$runs/$id.log"

# An implement brief is the audit scope and the edit gate's allowlist, so both lines are mandatory.
if [ "$mode" = "implement" ]; then
  plan_ref=$(sed -nE 's/^PLAN:[[:space:]]*//p' "$brief" | head -1)
  [ -n "$plan_ref" ] || { echo "brief needs a 'PLAN: <plan-run-id|none: reason>' line" >&2; exit 2; }
  case "$plan_ref" in
    none:*) : ;;
    *) [ -f "$runs/$plan_ref.last.txt" ] || { echo "PLAN references unknown run: $plan_ref" >&2; exit 2; } ;;
  esac
  allow=$(sed -n '/^ALLOWED_PATHS:/,/^$/p' "$brief" | sed '1d' | sed -E 's/^[-*[:space:]]+//' | grep -E '\S' || true)
  [ -n "$allow" ] || { echo "brief needs an 'ALLOWED_PATHS:' block listing every file Codex may touch" >&2; exit 2; }
  printf '%s\n' "$allow" > "$runs/$id.allow"
fi

# The implementer never loads Claude plugin skills, so an implement brief carries the lane's skill files.
skill_files() {
  [ "$mode" = "implement" ] || return 0
  grep -q '^SKILLS' "$brief" && return 0
  local dir="$here/../skills" names=()
  grep -q '\.rs$' <<<"$allow" && names+=(rust-correctness rust-sqlx rust-testing)
  grep -qE '(/routes/|router\.rs$)' <<<"$allow" && names+=(rust-axum-api)
  grep -qE 'openapi\.(ya?ml|json)$' <<<"$allow" && names+=(rust-nextjs-contract)
  grep -qE '\.tsx?$' <<<"$allow" && names+=(nextjs)
  grep -qE '/lib/api/.*\.tsx?$' <<<"$allow" && names+=(fetch-architecture)
  grep -q '\.py$' <<<"$allow" && names+=(fastapi)
  [ ${#names[@]} -gt 0 ] || return 0
  names+=(senior-engineer)
  local n; for n in "${names[@]}"; do [ -f "$dir/$n/SKILL.md" ] && printf '%s/SKILL.md\n' "$(cd "$dir/$n" && pwd)"; done
}

# Codex reads the skill paths itself; Grok receives them as opencode attachments because reads outside the repo are denied.
skills_preamble() {
  local files; files=$(skill_files); [ -n "$files" ] || return 0
  if [ "$engine" = "grok" ]; then
    printf 'SKILLS: the attached SKILL.md files are binding lane rules; the project manuals and the brief win on conflict.\n\n'
  else
    printf 'SKILLS (read before editing; binding, but the project manuals and the brief win on conflict):\n'
    printf -- '- %s\n' $files
    printf '\n'
  fi
}

# An investigate brief is context relief, never the conclusion: files to read and a table shape.
if [ "$mode" = "investigate" ]; then
  files=$(sed -n '/^FILES:/,/^$/p' "$brief" | sed '1d' | sed -E 's/^[-*[:space:]]+//' | grep -E '\S' || true)
  [ -n "$files" ] || { echo "brief needs a 'FILES:' block naming every file to read" >&2; exit 2; }
  report=$(sed -nE 's/^REPORT:[[:space:]]*//p' "$brief" | head -1)
  [ -n "$report" ] || { echo "brief needs a 'REPORT: <table columns>' line: file:line plus values, never prose" >&2; exit 2; }
fi

# Content hashes, not status lines: a file already dirty before the run must still register.
snapshot() {
  { git -C "$root" diff HEAD --name-only; git -C "$root" ls-files -o --exclude-standard; } | sort -u |
  while IFS= read -r f; do printf '%s %s\n' "$(git -C "$root" hash-object -- "$root/$f" 2>/dev/null || echo absent)" "$f"; done | sort
}

base=$(git -C "$root" rev-parse HEAD)
snapshot > "$runs/$id.pre.txt"

. "$here/lib/herdr-grid.sh"

conventions_preamble() {
  [ "$engine" = "grok" ] || return 0
  printf 'ROLE: you are the implementer; Claude planned this brief and will review your git diff and re-run the tests.\n'
  printf 'CONVENTIONS: before editing, read and obey the repository manuals that apply to the paths you touch: CLAUDE.md, AGENTS.md (root and nested) and .claude/rules/ inside this repository. Never read or write outside the repository root; a denied tool call is final, so do not retry it. The brief wins on scope.\n'
  printf 'READING: locate with grep, then read only the line ranges you need (start at the file:line sites the brief names); never read a whole large file to change one spot, and do not re-read a range you already have.\n\n'
}

# opencode has no output schema, so the Grok engine is told to end with the schema's JSON and it is extracted after the run.
result_contract() {
  [ "$engine" = "grok" ] || return 0
  printf '\n\nFINAL ANSWER CONTRACT: end your final message with exactly one fenced ```json block holding one object that validates against this JSON Schema, and write no fenced block after it:\n'
  cat "$schema"
}

prompt="$runs/$id.prompt.md"; runner="$runs/$id.runner.sh"
{ conventions_preamble; skills_preamble; cat "$brief"; result_contract; } > "$prompt"

if [ "$engine" = "grok" ]; then
  cfg="$runs/$id.opencode.json"
  if [ "$sandbox" = "read-only" ]; then perms='{"edit":"deny","bash":"deny","webfetch":"deny","external_directory":"deny","doom_loop":"deny","task":"deny"}'; else perms='{"edit":"allow","bash":"allow","webfetch":"deny","external_directory":"deny","doom_loop":"deny","task":"deny"}'; fi
  printf '{"$schema":"https://opencode.ai/config.json","permission":%s}\n' "$perms" > "$cfg"
  attach=""; while IFS= read -r f; do [ -n "$f" ] && attach+=" -f '$f'"; done <<<"$(skill_files)"
  cat > "$runner" <<EOF
set -o pipefail
cd '$root' && OPENCODE_CONFIG='$cfg' '$opencode_bin' run -m '$model'$attach -- "\$(cat '$prompt')" 2>&1 | tee '$log'
rc=\${PIPESTATUS[0]}
python3 '$here/lib/extract-result.py' '$log' '$last' || rc=1
exit \$rc
EOF
else
  cat > "$runner" <<EOF
set -o pipefail
codex exec --cd '$root' -m '$model' -s '$sandbox' --output-schema '$schema' -o '$last' - < '$prompt' 2>&1 | tee '$log'
exit \${PIPESTATUS[0]}
EOF
fi

herdr_pane=""
run_in_herdr_pane() {
  local status="$runs/$id.exit"
  herdr_pane=$(herdr_worker_pane "$root") || return 2
  herdr pane rename "$herdr_pane" "$engine $(basename "$brief" .md)" > /dev/null
  herdr pane run "$herdr_pane" "bash '$runner'; echo \$? > '$status'" > /dev/null || return 2
  until [ -f "$status" ]; do sleep 5; done
  return "$(cat "$status")"
}

set +e
if [ "$herdr_mode" = 1 ]; then
  run_in_herdr_pane
else
  bash "$runner" > /dev/null
fi
codex_exit=$?
set -e

snapshot > "$runs/$id.post.txt"
touched=$( { comm -13 "$runs/$id.pre.txt" "$runs/$id.post.txt"; comm -23 "$runs/$id.pre.txt" "$runs/$id.post.txt"; } | cut -d' ' -f2- | sort -u )

printf 'run=%s\nengine=%s\nmodel=%s\ncodex_exit=%s\nbase=%s\nlast_message=%s\nlog=%s\ntouched_by_this_run:\n%s\n' \
  "$id" "$engine" "$model" "$codex_exit" "$base" "$last" "$log" "${touched:-(none)}"
[ "$mode" = "implement" ] && printf 'allowed_paths=%s\n' "$runs/$id.allow"
[ -n "$herdr_pane" ] && printf 'herdr_pane=%s (close it after the audit: herdr pane close %s)\n' "$herdr_pane" "$herdr_pane"

# A truncated or empty result is a red result: re-brief once, then hand the user the failure.
summary_len=$(jq -r '(.summary // "") | length' 2>/dev/null < "$last" || echo 0)
[ "$codex_exit" -eq 0 ] && [ -s "$last" ] || echo "STATUS=FAILED (read the log tail before auditing)"
[ "${summary_len:-0}" -ge 11500 ] && echo "STATUS=TRUNCATED (summary hit the schema cap; re-brief asking for a narrower scope)"
exit 0
