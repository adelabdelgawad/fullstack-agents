#!/usr/bin/env bash
# Dispatch one implementer unit (headless Claude Sonnet by default; FSA_IMPLEMENTER=grok|codex swaps the engine); prints only the manifest.
set -euo pipefail

herdr_mode=0
[ "${1:-}" = "--herdr" ] && { herdr_mode=1; shift; }
mode=${1:-}; brief=${2:-}
[ -n "$mode" ] && [ -f "$brief" ] || { echo "usage: codex-task.sh [--herdr] investigate|plan|implement <brief-file>" >&2; exit 2; }
if [ "$herdr_mode" = 1 ]; then
  [ "${HERDR_ENV:-}" = 1 ] && [ -n "${HERDR_PANE_ID:-}" ] || { echo "--herdr needs a Herdr-managed pane (HERDR_ENV=1)" >&2; exit 2; }
fi

# Engine precedence: the brief's IMPLEMENTER: line (per task), then FSA_IMPLEMENTER (per session), then claude.
engine=$(sed -nE 's/^IMPLEMENTER:[[:space:]]*([a-z]+).*/\1/p' "$brief" | head -1)
engine=${engine:-${FSA_IMPLEMENTER:-claude}}
case "$engine:$mode" in
  codex:investigate) model=${FSA_CODEX_MODEL_INVESTIGATE:-gpt-5.6-luna}; sandbox=read-only ;;
  codex:plan)        model=${FSA_CODEX_MODEL_PLAN:-gpt-5.6-sol};         sandbox=read-only ;;
  codex:implement)   model=${FSA_CODEX_MODEL_IMPLEMENT:-gpt-5.6-sol};    sandbox=workspace-write ;;
  grok:investigate)  [ "${FSA_GROK_INVESTIGATE:-0}" = 1 ] || { echo "wide scans default to grep, ranged reads, then the bounded-extractor (Haiku); set FSA_GROK_INVESTIGATE=1 to spend Grok on one" >&2; exit 2; }
                     model=${FSA_GROK_MODEL_INVESTIGATE:-xai/grok-4.7}; sandbox=read-only ;;
  grok:plan)         echo "plan runs belong to Claude, the orchestrator; Grok only investigates or implements" >&2; exit 2 ;;
  grok:implement)    model=${FSA_GROK_MODEL_IMPLEMENT:-xai/grok-4.7};   sandbox=workspace-write ;;
  claude:implement)  model=${FSA_CLAUDE_MODEL_IMPLEMENT:-claude-sonnet-5}; sandbox=workspace-write ;;
  claude:investigate|claude:plan)
                     echo "the Claude engine only implements: plans are the lead's, wide scans go to the bounded-extractor (FSA_IMPLEMENTER=grok|codex for $mode runs)" >&2; exit 2 ;;
  *) echo "FSA_IMPLEMENTER must be claude|grok|codex and mode investigate|plan|implement" >&2; exit 2 ;;
esac
case "$engine" in
  codex) command -v codex > /dev/null || { echo "codex CLI not found" >&2; exit 2; } ;;
  claude) command -v claude > /dev/null || { echo "claude CLI not found" >&2; exit 2; } ;;
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
  max_paths=${FSA_MAX_ALLOWED_PATHS:-8}; path_count=$(grep -c . <<<"$allow")
  [ "$path_count" -le "$max_paths" ] || { echo "brief lists $path_count ALLOWED_PATHS, limit $max_paths: split it into sequential units (FSA_MAX_ALLOWED_PATHS overrides)" >&2; exit 2; }
  printf '%s\n' "$allow" > "$runs/$id.allow"
fi

# The implementer never loads Claude plugin skills, so an implement brief carries only the lane skills its paths need.
skill_files() {
  [ "$mode" = "implement" ] || return 0
  local dir="$here/../skills" names=() explicit
  explicit=$(sed -nE 's/^SKILLS:[[:space:]]*//p' "$brief" | head -1)
  if [ -n "$explicit" ]; then
    read -ra names <<<"${explicit//,/ }"
  else
    local tests='(^|/)tests?/|_tests?\.rs$|\.test\.tsx?$|\.spec\.tsx?$|(^|/)test_[^/]*\.py$'
    local src; src=$(grep -vE "$tests" <<<"$allow" | grep -v '/generated/' || true)
    grep -q '\.rs$' <<<"$src" && names+=(rust-correctness)
    grep -qE '(/repos?/|persistence|_repo\.rs$|sql[^/]*\.rs$|\.sql$)' <<<"$allow" && names+=(rust-sqlx)
    grep -E "$tests" <<<"$allow" | grep -q '\.rs$' && names+=(rust-testing)
    grep -qE '(/routes/|router\.rs$)' <<<"$src" && names+=(rust-axum-api)
    grep -qE 'openapi\.(ya?ml|json)$' <<<"$allow" && names+=(rust-nextjs-contract)
    grep -qE '\.tsx?$' <<<"$src" && grep -E '\.tsx?$' <<<"$src" | grep -qv '/lib/api/' && names+=(nextjs)
    grep -qE '/lib/api/[^/]*\.tsx?$' <<<"$src" && names+=(fetch-architecture)
    grep -q '\.py$' <<<"$src" && names+=(fastapi)
    local p; while IFS= read -r p; do
      [ -n "$p" ] && [ ! -e "$root/$p" ] && grep -qE '\.(rs|tsx?|py)$' <<<"$p" && { names+=(senior-engineer); break; }
    done <<<"$src"
  fi
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

allow_tests=${FSA_IMPLEMENTER_ALLOW_TESTS:-${FSA_GROK_ALLOW_TESTS:-0}}

conventions_preamble() {
  [ "$engine" = "codex" ] && return 0
  printf 'ROLE: you are the implementer; Claude planned this brief and will review your git diff and re-run the tests.\n'
  [ "$engine" = "claude" ] &&
    printf 'You are not the session lead or orchestrator: ignore manual text about planning, delegating, dispatching implementers or edit budgets, and never call scripts/codex-task.sh. Edit the files yourself.\n'
  printf 'CONVENTIONS: before editing, read and obey the repository manuals that apply to the paths you touch: CLAUDE.md, AGENTS.md (root and nested) and .claude/rules/ inside this repository. Never read or write outside the repository root; a denied tool call is final, so do not retry it. The brief wins on scope.\n'
  printf 'READING: locate with grep, then read only the line ranges you need (start at the file:line sites the brief names); never read a whole large file to change one spot, and do not re-read a range you already have.\n\n'
  [ "$mode" = "implement" ] &&
    printf 'SCOPE: the edit and write tools accept only the brief'"'"'s ALLOWED_PATHS; never change a file from bash. If the change needs another path, stop and name it in "open_risks".\n\n'
  [ "$mode" = "implement" ] && [ "$allow_tests" != 1 ] &&
    printf 'CHECKS: do not run test suites (test runners are denied); Claude runs the tests when it reviews your diff. At the end run only the brief'"'"'s BUILD command once (a compile or type check), filter its output to errors, fix what it reports, and list it in "tests".\n\n'
  return 0
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
  # The edit and write tools may touch only the brief's ALLOWED_PATHS; opencode refuses every other path.
  edit_rules='"deny"'
  [ -f "$runs/$id.allow" ] && edit_rules=$(jq -cRn '[inputs | select(length > 0)] | reduce .[] as $p ({"*": "deny"}; . + {($p): "allow"})' < "$runs/$id.allow")
  if [ "$sandbox" = "read-only" ]; then
    perms='{"edit":"deny","bash":"deny","webfetch":"deny","external_directory":"deny","doom_loop":"deny","task":"deny"}'
  elif [ "$allow_tests" = 1 ]; then
    perms='{"edit":'"$edit_rules"',"bash":"allow","webfetch":"deny","external_directory":"deny","doom_loop":"deny","task":"deny"}'
  else
    perms='{"edit":'"$edit_rules"',"bash":{"*":"allow","*cargo test*":"deny","*cargo nextest*":"deny","*test-backend.sh*":"deny","*vitest*":"deny","*jest*":"deny","*playwright*":"deny","*pytest*":"deny","*npm test*":"deny","*pnpm test*":"deny","*yarn test*":"deny","*bun test*":"deny"},"webfetch":"deny","external_directory":"deny","doom_loop":"deny","task":"deny"}'
  fi
  printf '{"$schema":"https://opencode.ai/config.json","permission":%s}\n' "$perms" > "$cfg"
  attach=""; while IFS= read -r f; do [ -n "$f" ] && attach+=" -f '$f'"; done <<<"$(skill_files)"
  cat > "$runner" <<EOF
set -o pipefail
cd '$root' && OPENCODE_CONFIG='$cfg' '$opencode_bin' run -m '$model'$attach -- "\$(cat '$prompt')" 2>&1 | tee '$log'
rc=\${PIPESTATUS[0]}
python3 '$here/lib/extract-result.py' '$log' '$last' || rc=1
exit \$rc
EOF
elif [ "$engine" = "claude" ]; then
  # Project settings only, so the user-scope plugin lead never loads; Edit/Write rules admit only ALLOWED_PATHS.
  args=(-p --model "$model" --setting-sources project,local --strict-mcp-config --permission-mode dontAsk
        --output-format stream-json --verbose --json-schema "$(cat "$schema")"
        --tools Read Grep Glob Edit Write Bash --allowedTools Read Grep Glob Bash)
  # Permission paths are gitignore globs, so Next.js segments like [id] must be escaped to match literally.
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    lit=$(sed -E 's/([][*?\\])/\\\1/g' <<<"/$root/$p")
    args+=("Edit($lit)" "Write($lit)")
  done < "$runs/$id.allow"
  args+=(--disallowedTools Agent Task WebFetch WebSearch NotebookEdit "Bash(*codex-task.sh*)")
  [ "$allow_tests" = 1 ] || args+=("Bash(*cargo test*)" "Bash(*cargo nextest*)" "Bash(*test-backend.sh*)" "Bash(*vitest*)"
    "Bash(*jest*)" "Bash(*playwright*)" "Bash(*pytest*)" "Bash(*npm test*)" "Bash(*pnpm test*)" "Bash(*yarn test*)" "Bash(*bun test*)")
  dirs=$(skill_files | xargs -r -n1 dirname | sort -u)
  [ -n "$dirs" ] && { args+=(--add-dir); while IFS= read -r d; do args+=("$d"); done <<<"$dirs"; }
  cat > "$runner" <<EOF
set -o pipefail
export BASH_DEFAULT_TIMEOUT_MS=\${BASH_DEFAULT_TIMEOUT_MS:-600000} BASH_MAX_TIMEOUT_MS=\${BASH_MAX_TIMEOUT_MS:-1800000}
cd $(printf %q "$root") && FSA_IMPLEMENTER_RUN=$(printf %q "$id") claude $(printf '%q ' "${args[@]}") < '$prompt' 2>&1 | tee '$log'
rc=\${PIPESTATUS[0]}
jq -nRe '[inputs | fromjson? | select(.type == "result")] | last | select(.is_error | not) | .structured_output // empty' '$log' > '$last' || { : > '$last'; rc=1; }
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
# A shared tree also shows other sessions' edits here, so this flags paths for the audit rather than failing the run.
if [ "$mode" = "implement" ] && [ -n "$touched" ]; then
  outside=$(grep -vxF -f "$runs/$id.allow" <<<"$touched" || true)
  [ -n "$outside" ] && printf 'STATUS=OUT_OF_SCOPE (changed outside ALLOWED_PATHS during the run; confirm the author before auditing):\n%s\n' "$outside"
fi
noop=0; [ "$mode" = "implement" ] && [ -z "$touched" ] && { noop=1; echo "STATUS=NO_CHANGES (the run changed no file; read the summary before re-briefing)"; }
[ "$codex_exit" -eq 0 ] && [ -s "$last" ] && [ "${summary_len:-0}" -lt 11500 ] && [ -z "${outside:-}" ] && [ "$noop" = 0 ] && echo "STATUS=OK (audit the diff before trusting it)"
exit 0
