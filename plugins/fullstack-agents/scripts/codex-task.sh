#!/usr/bin/env bash
# Dispatch one implementer unit (headless Claude Sonnet by default; FSA_IMPLEMENTER=grok|codex swaps the engine); prints only the manifest.
set -euo pipefail

# `release <run-id> [--confirm]`: free a run's paths only when no process can still edit for it (lib/liveness.py).
if [ "${1:-}" = "release" ]; then
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  . "$here/lib/runs-dir.sh"
  [ -n "${2:-}" ] || { echo "usage: codex-task.sh release <run-id> [--confirm]" >&2; exit 2; }
  root=${FSA_CODEX_ROOT:-$(git rev-parse --show-toplevel)}
  while IFS= read -r d; do
    [ -f "$d/$2.meta.json" ] && exec python3 -I "$here/lib/liveness.py" release "$d" "$2" "${@:3}"
  done < <(fsa_runs_read_dirs "$root")
  echo "run $2 not found in the registry" >&2
  exit 2
fi

# Run immutability: verify the plugin against its release manifest or the session pin, copy the dispatcher and its
# helpers into the run's lib dir, and re-execute from that copy so later plugin edits cannot change this run.
if [ -z "${FSA_DISPATCH_LIB:-}" ]; then
  src="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
  . "$src/lib/runs-dir.sh"
  . "$src/lib/plugin-pin.sh"
  pin_now=$(fsa_plugin_pin "$src/..")
  case "$(jq -r .mode <<<"$pin_now")" in
    release)
      rel=$(jq -r .release_root <<<"$pin_now")
      python3 -I "$src/fsa-release" verify "$rel" > /dev/null ||
        { echo "STATUS=PLUGIN_TAMPERED (release $rel no longer matches RELEASE.json)"; exit 2; } ;;
    dev)
      if [ -n "${FSA_SESSION_PIN:-}" ] && [ -s "$FSA_SESSION_PIN" ]; then
        pinned=$(jq -r .fingerprint "$FSA_SESSION_PIN")
        if [ "$pinned" != "$(jq -r .fingerprint <<<"$pin_now")" ] && [ "${FSA_ACCEPT_PLUGIN_CHANGE:-0}" != 1 ]; then
          echo "STATUS=PLUGIN_CHANGED pinned=$(jq -r .git_sha "$FSA_SESSION_PIN") current=$(jq -r .git_sha <<<"$pin_now") (the plugin source changed since this session started; FSA_ACCEPT_PLUGIN_CHANGE=1 only for explicit plugin development)"
          exit 2
        fi
      else
        echo "fullstack-agents: no session pin; dispatching from the live plugin source $src/.." >&2
      fi ;;
  esac
  root0=${FSA_CODEX_ROOT:-$(git rev-parse --show-toplevel)}
  runs0=$(fsa_runs_dir "$root0"); mkdir -p "$runs0"
  stamp=$(date +%Y%m%d-%H%M%S)
  lib="$runs0/dispatch-$stamp-$$.lib"
  mkdir -p "$lib/lib"
  cp "$src/codex-task.sh" "$src/codex-result.schema.json" "$src/fsa-skill-map" "$lib/"
  find "$src/lib" -maxdepth 1 -type f \( -name '*.sh' -o -name '*.py' -o -name '*.jq' -o -name allowed-paths-fence \) \
    -exec cp {} "$lib/lib/" \;
  [ -d "$src/lib/roles" ] && cp -r "$src/lib/roles" "$lib/lib/"
  # Copies from a read-only release stay private run files: writable, so cleanup and retention can remove them.
  chmod -R u+w "$lib"
  FSA_DISPATCH_LIB="$lib" FSA_PLUGIN_SRC="$(cd "$src/.." && pwd -P)" FSA_DISPATCH_STAMP="$stamp" FSA_PLUGIN_PIN="$pin_now" \
    exec bash "$lib/codex-task.sh" "$@"
fi
plugin_src=${FSA_PLUGIN_SRC:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)}
# The copy's private variables never reach engines or nested dispatches.
dispatch_lib=${FSA_DISPATCH_LIB:-}; dispatch_stamp=${FSA_DISPATCH_STAMP:-}; plugin_pin=${FSA_PLUGIN_PIN:-}
unset FSA_DISPATCH_LIB FSA_PLUGIN_SRC FSA_DISPATCH_STAMP FSA_PLUGIN_PIN
# A dispatch refused before its run record exists removes only its own copied lib dir.
trap 'case "$dispatch_lib" in */dispatch-*-$$.lib) rm -rf "$dispatch_lib" 2> /dev/null ;; esac; true' EXIT

herdr_mode=0
[ "${1:-}" = "--herdr" ] && { herdr_mode=1; shift; }
mode=${1:-}; brief=${2:-}
[ -n "$mode" ] && [ -f "$brief" ] || { echo "usage: codex-task.sh [--herdr] investigate|plan|implement <brief-file>" >&2; exit 2; }
if [ "$herdr_mode" = 1 ]; then
  [ "${HERDR_ENV:-}" = 1 ] && [ -n "${HERDR_PANE_ID:-}" ] || { echo "--herdr needs a Herdr-managed pane (HERDR_ENV=1)" >&2; exit 2; }
fi

# Engine precedence: the brief's IMPLEMENTER: line (per task), then FSA_IMPLEMENTER (per session), then claude.
engine=$(sed -nE 's/^IMPLEMENTER:[[:space:]]*([a-z]+).*/\1/p' "$brief" | head -1)
engine_source=brief; [ -n "$engine" ] || { [ -n "${FSA_IMPLEMENTER:-}" ] && engine_source=env || engine_source=default; }
engine=${engine:-${FSA_IMPLEMENTER:-claude}}
# Grok reasoning effort: the brief's EFFORT: line, then FSA_GROK_VARIANT; empty keeps the model default.
variant=$(sed -nE 's/^EFFORT:[[:space:]]*([a-z]+).*/\1/p' "$brief" | head -1)
variant=${variant:-${FSA_GROK_VARIANT:-}}
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
  claude) cc_cmd=$(python3 -I "$(dirname "${BASH_SOURCE[0]}")/lib/claude_cli.py") || exit 2 ;;
  grok)  opencode_bin=${FSA_OPENCODE_BIN:-$(command -v opencode || echo "$HOME/.opencode/bin/opencode")}
         [ -x "$opencode_bin" ] || { echo "opencode CLI not found (the Grok engine runs through opencode)" >&2; exit 2; }
         oc_auth=${XDG_DATA_HOME:-$HOME/.local/share}/opencode/auth.json
         [ -n "${XAI_API_KEY:-}" ] || jq -e 'has("xai")' "$oc_auth" > /dev/null 2>&1 ||
           { echo "no xAI credential: run 'opencode auth login' (xAI) or export XAI_API_KEY" >&2; exit 2; } ;;
esac

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root=${FSA_CODEX_ROOT:-$(git rev-parse --show-toplevel)}
. "$here/lib/runs-dir.sh"
runs=$(fsa_runs_dir "$root"); mkdir -p "$runs"
schema="$root/.claude/codex-result.schema.json"; [ -f "$schema" ] || schema="$here/codex-result.schema.json"

# Optional policy profile (conf key `policy_profile`): its "## Every agent" section is appended to the
# implementer contract for every engine; an unknown name refuses the dispatch before any engine starts.
policy_profile=$(python3 -I "$here/lib/team_conf.py" get "$root" policy_profile) ||
  { echo "invalid fsa-team.conf: policy_profile" >&2; exit 2; }
policy_file=""; policy_section=""
if [ -n "$policy_profile" ]; then
  policy_file="$plugin_src/policies/$policy_profile.md"
  [ -f "$policy_file" ] || { echo "unknown policy_profile: $policy_profile (no $policy_file)" >&2; exit 2; }
  policy_section=$(awk '/^## Every agent/{flag=1; print; next} /^## /{if (flag) exit} flag' "$policy_file")
fi
id="$mode-${dispatch_stamp:-$(date +%Y%m%d-%H%M%S)}-$$"
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
. "$here/lib/task-row.sh"
fsa_build_warn "$brief"
fsa_task_row_init "$brief" "$root"
task_rel=$(fsa_task_row_relpath "$root")

# The implementer never loads Claude plugin skills, so an implement brief carries only the lane skills its paths need.
skill_files() {
  [ "$mode" = "implement" ] || return 0
  local dir="$plugin_src/skills" names=() explicit
  explicit=$(sed -nE 's/^SKILLS:[[:space:]]*//p' "$brief" | head -1)
  [ -n "$explicit" ] && read -ra names <<<"${explicit//,/ }"
  # The path map is the floor; a SKILLS: line only adds to it (scripts/fsa-skill-map is shared with skill-gate).
  local mapped; mapped=$(printf '%s\n' "$allow" | python3 "$here/fsa-skill-map" --root "$root" 2>/dev/null || true)
  [ -n "$mapped" ] && while IFS= read -r n; do names+=("$n"); done <<<"$mapped"
  local n seen=" "; for n in "${names[@]}"; do
    n="${n#fullstack-agents:}"; [[ "$seen" == *" $n "* ]] && continue; seen+="$n "
    [ -f "$dir/$n/SKILL.md" ] && printf '%s/SKILL.md\n' "$(cd "$dir/$n" && pwd)"
  done
  return 0
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

# Generated output (conf `generated_globs`, e.g. `.agent-cargo-cache/*`) is reporting noise, never source: only
# UNTRACKED paths matching a glob are left out of the snapshot; tracked files are always hashed and scope-checked.
generated_globs=$(python3 -I "$here/lib/team_conf.py" get "$root" generated_globs) ||
  { echo "invalid fsa-team.conf: generated_globs" >&2; exit 2; }
is_generated() {
  local g
  while IFS= read -r g; do [ -n "$g" ] || continue; case "$1" in $g) return 0 ;; esac; done <<<"$generated_globs"
  return 1
}
# Narrow by construction: a glob that matches any tracked file covers source, not build output, so the dispatch is
# refused rather than letting that glob hide new files beside the source.
if [ -n "$generated_globs" ]; then
  covered=$(git -C "$root" ls-files | while IFS= read -r f; do if is_generated "$f"; then printf '%s\n' "$f"; break; fi; done)
  [ -z "$covered" ] || { echo "invalid fsa-team.conf: generated_globs matches tracked file '$covered'; list only untracked build output (e.g. .agent-cargo-cache/*)" >&2; exit 2; }
fi
untracked_source() {
  git -C "$root" ls-files -o --exclude-standard | while IFS= read -r f; do if ! is_generated "$f"; then printf '%s\n' "$f"; fi; done
}
generated_count() {
  [ -n "$generated_globs" ] || { echo 0; return; }
  git -C "$root" ls-files -o --exclude-standard | while IFS= read -r f; do if is_generated "$f"; then echo x; fi; done | wc -l
}

# Content hashes, not status lines: a file already dirty before the run must still register; the dispatcher's own ledger never does.
snapshot() {
  { git -C "$root" diff HEAD --name-only
    if [ -n "$generated_globs" ]; then untracked_source; else git -C "$root" ls-files -o --exclude-standard; fi; } | sort -u |
  { if [ -n "$task_rel" ]; then grep -vxF -- "$task_rel" || true; else cat; fi; } |
  while IFS= read -r f; do printf '%s %s\n' "$(git -C "$root" hash-object -- "$root/$f" 2>/dev/null || echo absent)" "$f"; done | sort
}

base=$(git -C "$root" rev-parse HEAD)
snapshot > "$runs/$id.pre.txt"
generated_pre=$(generated_count)

. "$here/lib/herdr-grid.sh"
. "$here/lib/run-scope.sh"

allow_tests=${FSA_IMPLEMENTER_ALLOW_TESTS:-${FSA_GROK_ALLOW_TESTS:-0}}

# The implementer contract (lib/roles/implementer.md) goes to every engine; only enforcement wording differs per engine.
conventions_preamble() {
  cat "$here/lib/roles/implementer.md"
  [ -n "$policy_section" ] && printf '\n%s\n' "$policy_section"
  if [ "$mode" = "implement" ]; then
    if [ "$engine" = "codex" ]; then
      printf 'SCOPE: edit only the brief'"'"'s ALLOWED_PATHS; any other changed path is reported as a scope violation after the run. Never change a file from bash. If the change needs another path, stop and name it in "open_risks".\n\n'
    else
      printf 'SCOPE: the edit and write tools accept only the brief'"'"'s ALLOWED_PATHS; never change a file from bash. If the change needs another path, stop and name it in "open_risks".\n\n'
    fi
  fi
  [ "$mode" = "implement" ] && [ "$allow_tests" != 1 ] &&
    printf 'CHECKS: do not run test suites; Claude runs the tests when it reviews your diff. At the end run only the brief'"'"'s BUILD command once (a compile or type check), filter its output to errors, fix what it reports, and list it in "tests".\n\n'
  return 0
}

# opencode has no output schema, so the Grok engine is told to end with the schema's JSON and it is extracted after the run.
result_contract() {
  [ "$engine" = "grok" ] || return 0
  printf '\n\nFINAL ANSWER CONTRACT: end your final message with exactly one fenced ```json block holding one object that validates against this JSON Schema, and write no fenced block after it:\n'
  cat "$schema"
}

. "$here/lib/registry.sh"
engine_sid=""; [ "$engine" = "claude" ] && engine_sid=$(python3 -c 'import uuid; print(uuid.uuid4())')
instructions_start=$(fsa_instruction_hashes "$root")
# Project rules every engine must receive: AGENTS.md (read natively), else CLAUDE.md as the fallback.
project_docs=""
if [ -f "$root/AGENTS.md" ]; then project_docs=AGENTS.md; elif [ -f "$root/CLAUDE.md" ]; then project_docs=CLAUDE.md; fi
[ -n "$project_docs" ] && [ "$(wc -c < "$root/$project_docs")" -gt 32768 ] &&
  echo "fullstack-agents: $project_docs exceeds Codex's 32768-byte project_doc_max_bytes; Codex truncates it" >&2
jq -n --arg id "$id" --arg mode "$mode" --arg engine "$engine" --arg model "$model" --arg brief "$(realpath "$brief")" \
  --arg root "$root" --arg session "${CLAUDE_CODE_SESSION_ID:-${CLAUDE_SESSION_ID:-}}" --arg started "$(date -u +%FT%TZ)" \
  '{id:$id,mode:$mode,engine:$engine,model:$model,brief:$brief,root:$root,session:$session,started:$started}' > "$runs/$id.meta.json" || true
prompt="$runs/$id.prompt.md"; runner="$runs/$id.runner.sh"
{ conventions_preamble; skills_preamble; cat "$brief"; result_contract; } > "$prompt"
unit=$(basename "$brief" .md); unit=${unit%-r[0-9]*}
fsa_meta_merge "$runs" "$id" "$(jq -n --argjson plugin "${plugin_pin:-$(fsa_plugin_identity "$plugin_src/scripts")}" \
  --arg es "$engine_source" --arg model "$model" --arg variant "$variant" --arg tests "$allow_tests" --arg sandbox "$sandbox" \
  --arg brief_sha "$(fsa_sha256 "$brief")" --arg prompt_sha "$(fsa_sha256 "$prompt")" --arg unit "$unit" \
  --arg sid "$engine_sid" --argjson instructions "$instructions_start" --arg cwd "$root" \
  --arg role_sha "$(fsa_sha256 "$here/lib/roles/implementer.md")" --arg docs "$project_docs" \
  --arg pname "$policy_profile" --arg psha "$(fsa_sha256 "$policy_file")" \
  '{schema: 2, plugin: $plugin, cwd: $cwd, unit: $unit, parent_run: null,
    requested: {engine_source: $es, model: $model, variant: (if $variant == "" then null else $variant end),
                allow_tests: ($tests == "1"), sandbox: $sandbox},
    brief_sha256: $brief_sha, prompt_sha256: $prompt_sha, instructions_at_dispatch: $instructions,
    role_contract: {name: "implementer", sha256: $role_sha}, project_docs: (if $docs == "" then null else $docs end),
    policy_profile: (if $pname == "" then null else {name: $pname, sha256: $psha} end),
    engine_session_id: (if $sid == "" then null else $sid end)}')"
fsa_event "$runs" "$id" created
trap - EXIT

if [ "$engine" = "grok" ]; then
  cfg="$runs/$id.opencode.json"
  # The edit and write tools may touch only the brief's ALLOWED_PATHS; opencode refuses every other path.
  edit_rules='"deny"'
  [ -f "$runs/$id.allow" ] && edit_rules=$(jq -cRn '[inputs | select(length > 0)] | reduce .[] as $p ({"*": "deny"}; . + {($p): "allow"})' < "$runs/$id.allow")
  if [ "$sandbox" = "read-only" ]; then
    perms='{"edit":"deny","bash":"deny","webfetch":"deny","external_directory":"deny","doom_loop":"deny","task":"deny"}'
  elif [ "$allow_tests" = 1 ]; then
    perms='{"edit":'"$edit_rules"',"bash":{"*":"allow","*git stash*":"deny","*git -C * stash*":"deny","*git -c * stash*":"deny"},"webfetch":"deny","external_directory":"deny","doom_loop":"deny","task":"deny"}'
  else
    perms='{"edit":'"$edit_rules"',"bash":{"*":"allow","*git stash*":"deny","*git -C * stash*":"deny","*git -c * stash*":"deny","*cargo test*":"deny","*cargo nextest*":"deny","*test-backend.sh*":"deny","*vitest*":"deny","*jest*":"deny","*playwright*":"deny","*pytest*":"deny","*npm test*":"deny","*pnpm test*":"deny","*yarn test*":"deny","*bun test*":"deny"},"webfetch":"deny","external_directory":"deny","doom_loop":"deny","task":"deny"}'
  fi
  instructions='[]'; [ -n "$project_docs" ] && instructions="[\"$project_docs\"]"
  printf '{"$schema":"https://opencode.ai/config.json","instructions":%s,"permission":%s}\n' "$instructions" "$perms" > "$cfg"
  attach=""; while IFS= read -r f; do [ -n "$f" ] && attach+=" -f '$f'"; done <<<"$(skill_files)"
  cat > "$runner" <<EOF
set -o pipefail
cd '$root' && OPENCODE_CONFIG='$cfg' '$opencode_bin' run -m '$model'${variant:+ --variant '$variant'} --title '$id'$attach -- "\$(cat '$prompt')" < /dev/null 2>&1 | tee '$log'
rc=\${PIPESTATUS[0]}; echo \$rc > '$runs/$id.engine_exit'
python3 '$here/lib/extract-result.py' '$log' '$last' || rc=1
exit \$rc
EOF
elif [ "$engine" = "claude" ]; then
  # Project settings only, so the user-scope plugin lead never loads. The `cc` alias bypasses permission prompts,
  # so the PreToolUse fence (not the Edit/Write allow rules) is what keeps file tools inside ALLOWED_PATHS.
  fence=$(jq -cn --arg c "python3 -I $(printf %q "$here/lib/allowed-paths-fence")" \
    '{hooks:{PreToolUse:[{matcher:"Edit|Write|MultiEdit|NotebookEdit|Bash",hooks:[{type:"command",command:$c}]}]}}')
  args=(-p --model "$model" --session-id "$engine_sid" --setting-sources project,local --settings "$fence" --strict-mcp-config --permission-mode dontAsk
        --output-format stream-json --verbose --json-schema "$(cat "$schema")"
        --tools Read Grep Glob Edit Write Bash --allowedTools Read Grep Glob Bash)
  # Permission paths are gitignore globs, so Next.js segments like [id] must be escaped to match literally.
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    lit=$(sed -E 's/([][*?\\])/\\\1/g' <<<"/$root/$p")
    args+=("Edit($lit)" "Write($lit)")
  done < "$runs/$id.allow"
  args+=(--disallowedTools Agent Task WebFetch WebSearch NotebookEdit "Bash(*codex-task.sh*)")
  # Claude reads CLAUDE.md, not AGENTS.md: shared project rules are appended unless CLAUDE.md already imports them.
  if [ "$project_docs" = AGENTS.md ] && ! grep -qx '@AGENTS.md' "$root/CLAUDE.md" 2>/dev/null; then
    args+=(--append-system-prompt "$(cat "$root/AGENTS.md")")
  fi
  [ "$allow_tests" = 1 ] || args+=("Bash(*cargo test*)" "Bash(*cargo nextest*)" "Bash(*test-backend.sh*)" "Bash(*vitest*)"
    "Bash(*jest*)" "Bash(*playwright*)" "Bash(*pytest*)" "Bash(*npm test*)" "Bash(*pnpm test*)" "Bash(*yarn test*)" "Bash(*bun test*)")
  dirs=$(skill_files | xargs -r -n1 dirname | sort -u)
  [ -n "$dirs" ] && { args+=(--add-dir); while IFS= read -r d; do args+=("$d"); done <<<"$dirs"; }
  cat > "$runner" <<EOF
set -o pipefail
export BASH_DEFAULT_TIMEOUT_MS=\${BASH_DEFAULT_TIMEOUT_MS:-600000} BASH_MAX_TIMEOUT_MS=\${BASH_MAX_TIMEOUT_MS:-1800000}
cd $(printf %q "$root") && FSA_IMPLEMENTER_RUN=$(printf %q "$id") FSA_IMPLEMENTER_ROOT=$(printf %q "$root") FSA_ALLOWED_PATHS_FILE=$(printf %q "$runs/$id.allow") $cc_cmd $(printf '%q ' "${args[@]}") < '$prompt' 2>&1 | tee '$log'
rc=\${PIPESTATUS[0]}; echo \$rc > '$runs/$id.engine_exit'
jq -nRe '[inputs | fromjson? | select(.type == "result")] | last | select(.is_error | not) | .structured_output // empty' '$log' > '$last' || { : > '$last'; rc=1; }
exit \$rc
EOF
else
  # Build caches and journals outside the root stay read-only in workspace-write unless the project names them.
  add_dirs=""
  # Implementer runs drop Codex plugins (the Codex-led edition's lead doctrine); project rules still load.
  codex_docs=""; [ "$project_docs" = CLAUDE.md ] && codex_docs=" -c 'project_doc_fallback_filenames=[\"CLAUDE.md\"]'"
  if [ "$sandbox" = "workspace-write" ]; then
    extra=()
    if [ -n "${FSA_CODEX_ADD_DIRS+x}" ]; then
      IFS=: read -ra extra <<<"${FSA_CODEX_ADD_DIRS}"
    else
      while IFS= read -r d; do [ -n "$d" ] && extra+=("$d"); done \
        < <(python3 -I "$here/lib/team_conf.py" get "$root" codex_add_dirs 2>/dev/null || true)
    fi
    for d in "${extra[@]}"; do [ -n "$d" ] && mkdir -p "$d" && add_dirs+=" --add-dir $(printf %q "$d")"; done
  fi
  cat > "$runner" <<EOF
set -o pipefail
codex exec --cd '$root' -m '$model' -s '$sandbox'$add_dirs --disable plugins$codex_docs --output-schema '$schema' -o '$last' - < '$prompt' 2>&1 | tee '$log'
rc=\${PIPESTATUS[0]}; echo \$rc > '$runs/$id.engine_exit'
exit \$rc
EOF
fi

herdr_pane=""
run_in_herdr_pane() {
  local status="$runs/$id.exit"
  herdr_pane=$(herdr_worker_pane "$root") || return 2
  herdr pane rename "$herdr_pane" "$engine $(basename "$brief" .md)" > /dev/null
  herdr pane run "$herdr_pane" "bash '$runner'; echo \$? > '$status'" > /dev/null || return 2
  until [ -f "$status" ]; do sleep 5; fsa_task_row_renew "$engine" "$task_stem"; done
  return "$(cat "$status")"
}

task_stem=$(basename "$brief" .md)
fsa_task_row_dispatch "$engine" "$task_stem" "$id" || true
fsa_event "$runs" "$id" running
# Every engine process and its children inherit the run marker; the runner leads its own process group.
export FSA_RUN_ID="$id" FSA_ROLE=implementer
# Cancellation stops the runner's group and every marked process, then still records what the run changed.
cancelled=0; runner_pid=""
liveness() { python3 -I "$here/lib/liveness.py" "$1" "$runs" "$id" "${@:2}" 2>/dev/null; }
on_cancel() {
  cancelled=1
  [ -n "$runner_pid" ] && kill -TERM -- "-$runner_pid" 2>/dev/null
  liveness signal TERM > /dev/null
  local waited=0
  while [ -n "$(liveness pids)" ] && [ "$waited" -lt "${FSA_CANCEL_WAIT_S:-10}" ]; do sleep 1; waited=$((waited + 1)); done
  liveness signal KILL > /dev/null
  [ -n "$runner_pid" ] && kill -KILL -- "-$runner_pid" 2>/dev/null
  return 0
}
trap on_cancel INT TERM
set +e
if [ "$herdr_mode" = 1 ]; then
  run_in_herdr_pane
else
  setsid bash "$runner" > /dev/null &
  runner_pid=$!
  fsa_meta_merge "$runs" "$id" "{\"runner_pid\": $runner_pid, \"runner_pgid\": $runner_pid}"
  wait "$runner_pid"
fi
codex_exit=$?
[ "$cancelled" = 1 ] && [ -n "$runner_pid" ] && { wait "$runner_pid" 2>/dev/null; codex_exit=130; }
trap - INT TERM
set -e

fsa_event "$runs" "$id" engine_exited "exit $codex_exit"
snapshot > "$runs/$id.post.txt"
touched=$(run_touched "$runs" "$id")
[ "$engine" = "claude" ] || engine_sid=$(fsa_engine_session_id "$engine" "$log" "$id" "$root" "${opencode_bin:-opencode}")
instructions_end=$(fsa_instruction_hashes "$root")
instructions_changed=false; [ "$instructions_start" = "$instructions_end" ] || instructions_changed=true
fsa_meta_merge "$runs" "$id" "$(jq -n --arg sid "$engine_sid" --argjson end "$instructions_end" --argjson changed "$instructions_changed" \
  '{engine_session_id: (if $sid == "" then null else $sid end), instructions_at_completion: $end, instructions_changed: $changed}')"
fsa_event "$runs" "$id" collected

printf 'run=%s\nengine=%s\nmodel=%s\ncodex_exit=%s\nbase=%s\nlast_message=%s\nlog=%s\ntouched_by_this_run:\n%s\n' \
  "$id" "$engine" "$model${variant:+ (variant $variant)}" "$codex_exit" "$base" "$last" "$log" "${touched:-(none)}"
[ "$mode" = "implement" ] && printf 'allowed_paths=%s\n' "$runs/$id.allow"
[ -n "$herdr_pane" ] && printf 'herdr_pane=%s (close it after the audit: herdr pane close %s)\n' "$herdr_pane" "$herdr_pane"
stash_used=0
if grep -Fq 'Saved working directory and index state' "$log"; then
  stash_used=1
  printf 'STATUS=SHARED_CHECKOUT_VIOLATION (git stash ran during the run; compare %s and .post.txt)\n' "$runs/$id.pre.txt"
fi

# A truncated or empty result is a red result: re-brief once, then hand the user the failure.
summary_len=$(jq -r '(.summary // "") | length' 2>/dev/null < "$last" || echo 0)
[ "$codex_exit" -eq 0 ] && [ -s "$last" ] || echo "STATUS=FAILED (read the log tail before auditing)"
[ "${summary_len:-0}" -ge 11500 ] && echo "STATUS=TRUNCATED (summary hit the schema cap; re-brief asking for a narrower scope)"
# Paths a concurrent run in this root or the lead's briefs account for are not this run's; the rest still needs its author confirmed.
if [ "$mode" = "implement" ]; then
  outside=$(run_outside "$runs" "$id" "$root" "$brief")
  printf '%s' "${outside:+$outside$'\n'}" > "$runs/$id.outside"
  [ -n "$outside" ] && printf 'STATUS=OUT_OF_SCOPE (changed outside ALLOWED_PATHS during the run; confirm the author before auditing):\n%s\n' "$outside"
  generated_post=$(generated_count)
  [ "$generated_post" != "$generated_pre" ] &&
    printf 'GENERATED: %s -> %s untracked paths under generated_globs (informational, excluded from scope checks)\n' "$generated_pre" "$generated_post"
fi
noop=0; [ "$mode" = "implement" ] && [ -z "$touched" ] && { noop=1; echo "STATUS=NO_CHANGES (the run changed no file; read the summary before re-briefing)"; }
[ "$instructions_changed" = true ] && echo "STATUS=INSTRUCTIONS_CHANGED (project instructions changed during the run; review the result against the current rules)"
[ "$codex_exit" -eq 0 ] && [ -s "$last" ] && [ "${summary_len:-0}" -lt 11500 ] && [ -z "${outside:-}" ] && [ "$noop" = 0 ] \
  && [ "$instructions_changed" = false ] && [ "$stash_used" = 0 ] && echo "STATUS=OK (audit the diff before trusting it)"

# Terminal state: the first that applies; `succeeded` means a valid in-scope result, never an accepted change.
engine_exit=$(cat "$runs/$id.engine_exit" 2>/dev/null || echo "$codex_exit")
details=()
[ "$cancelled" = 1 ] && details+=(cancelled)
[ "$engine_exit" -ne 0 ] && details+=(engine_failed)
{ [ ! -s "$last" ] || [ "${summary_len:-0}" -ge 11500 ]; } && details+=(invalid_output)
[ -n "${outside:-}" ] && details+=(scope_violation)
[ "$noop" = 1 ] && details+=(no_changes)
[ "$stash_used" = 1 ] && details+=(stash_used)
state=${details[0]:-succeeded}
after=$(liveness state || echo '{"state":"uncertain"}')
held=$(jq -r 'if .state == "running" or ((.processes // []) | length > 0) then "held" else "free" end' <<<"$after")
[ "$held" = held ] && echo "STATUS=OWNERSHIP_HELD (run processes are still alive; paths stay owned until \`codex-task.sh release $id\`)"
jq -n --arg state "$state" --argjson engine_exit "$engine_exit" --arg details "${details[*]}" --arg touched "$touched" \
  --arg outside "${outside:-}" --argjson changed "$instructions_changed" --argjson after "$after" --arg held "$held" \
  --arg started "$(jq -r .started "$runs/$id.meta.json")" --arg ended "$(date -u +%FT%TZ)" \
  '{state: $state, engine_exit: $engine_exit, details: ($details | split(" ") | map(select(. != ""))),
    touched: ($touched | split("\n") | map(select(. != ""))), outside: ($outside | split("\n") | map(select(. != ""))),
    review: (if $changed then ["instructions_changed"] else [] end), liveness_after: $after, ownership: $held,
    started: $started, ended: $ended}' > "$runs/$id.result.json"
fsa_task_row_finish "$state" "$id" || true
fsa_event "$runs" "$id" "$state"

# Exit codes: legacy (default) keeps 0 for every completed run; strict maps the terminal state (D4).
[ "$cancelled" = 1 ] && exit 130
[ "${FSA_DISPATCH_EXIT:-legacy}" = strict ] || exit 0
case "$state" in
  engine_failed) exit 10 ;;
  invalid_output) exit 11 ;;
  scope_violation) exit 12 ;;
  no_changes) exit 13 ;;
esac
[ "$instructions_changed" = true ] && exit 14
exit 0
