# Dispatcher hooks: a brief's `TASK: <ledger.md>#<ROW-ID>` row follows the run; tracker failures only warn on stderr.
fsa_task_lib="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fsa_task_root=""; fsa_task_file=""; fsa_task_id=""; fsa_task_renewed=0; fsa_task_format=""; fsa_task_status=""

fsa_task_cli() {
  local out
  out=$(python3 -I "$fsa_task_lib/task_tracking.py" "$1" --root "$fsa_task_root" --file "$fsa_task_file" "${@:2}" 2>&1) ||
    { printf 'fullstack-agents: task ledger %s for %s failed (run unaffected): %s\n' "$1" "$fsa_task_id" "$(tail -1 <<<"$out")" >&2; return 1; }
  printf '%s\n' "$out"
}

# fsa_task_row_init <brief> <root>: reads the TASK: line; no line leaves fsa_task_id empty and every hook a no-op.
fsa_task_row_init() {
  local spec path dir
  fsa_task_root=""; fsa_task_file=""; fsa_task_id=""
  spec=$(sed -nE 's/^TASK:[[:space:]]*//p' "$1" | head -1 | sed -E 's/[[:space:]]+$//')
  [ -n "$spec" ] || return 0
  path=${spec%#*}; fsa_task_id=${spec##*#}
  if [ "$path" = "$spec" ] || [ -z "$path" ] || [ -z "$fsa_task_id" ]; then
    echo "fullstack-agents: ignoring malformed 'TASK: $spec' (expected <ledger.md>#<ROW-ID>)" >&2
    fsa_task_id=""; return 0
  fi
  case "$path" in
    /*) case "$path" in
          "$2"/*) fsa_task_root=$2 ;;
          *) dir=$(dirname "$path"); fsa_task_root=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null || echo "$dir") ;;
        esac ;;
    *) fsa_task_root=$2 ;;
  esac
  fsa_task_file=$path
  return 0
}

# fsa_task_row_relpath <root>: the ledger path relative to the run root, empty when it lies outside it.
fsa_task_row_relpath() {
  [ -n "$fsa_task_id" ] || return 0
  local abs rel
  case "$fsa_task_file" in /*) abs=$fsa_task_file ;; *) abs=$fsa_task_root/$fsa_task_file ;; esac
  rel=$(realpath -m --relative-to="$(realpath -m "$1")" "$abs" 2>/dev/null) || return 0
  case "$rel" in ..|../*) return 0 ;; esac
  printf '%s\n' "$rel"
}

# fsa_task_row_dispatch <engine> <brief-stem> <run-id>
fsa_task_row_dispatch() {
  [ -n "$fsa_task_id" ] || return 0
  local summary err
  if ! summary=$(python3 -I "$fsa_task_lib/task_tracking.py" show --root "$fsa_task_root" --file "$fsa_task_file" --json 2>/dev/null); then
    err=$(python3 -I "$fsa_task_lib/task_tracking.py" show --root "$fsa_task_root" --file "$fsa_task_file" --json 2>&1 1>/dev/null) || true
    printf 'fullstack-agents: task ledger unreadable; ledger updates disabled for this run: %s\n' "$(tail -1 <<<"$err")" >&2
    fsa_task_id=""
    return 0
  fi
  fsa_task_format=$(jq -r '.format' <<<"$summary")
  fsa_task_status=$(jq -r --arg id "$fsa_task_id" '.items[] | select(.id == $id) | .status' <<<"$summary")
  if ! jq -e --arg id "$fsa_task_id" 'any(.items[]; .id == $id)' <<<"$summary" > /dev/null 2>&1; then
    if [ "$fsa_task_format" = v2 ]; then
      printf 'fullstack-agents: task row %s is missing; add the row first\n' "$fsa_task_id" >&2
      fsa_task_id=""
      return 0
    fi
    fsa_task_cli add --task "$fsa_task_id|in_progress|$2|dispatched (run $3)" > /dev/null || return 0
  fi
  if [ "$fsa_task_format" = v2 ] && [ "$fsa_task_status" = done ]; then
    printf 'fullstack-agents: task row %s is already done; leaving it untouched\n' "$fsa_task_id" >&2
    fsa_task_id=""
    return 0
  fi
  fsa_task_cli set --id "$fsa_task_id" --status in_progress --owner "$1" --activity "implementing $2" --active-for 300 > /dev/null || return 0
  fsa_task_renewed=$SECONDS
}

# fsa_task_row_renew <engine> <brief-stem>: called from a poll loop; renews at most every 240 s.
fsa_task_row_renew() {
  [ -n "$fsa_task_id" ] && [ $((SECONDS - fsa_task_renewed)) -ge 240 ] || return 0
  fsa_task_renewed=$SECONDS
  fsa_task_cli set --id "$fsa_task_id" --status in_progress --owner "$1" --activity "implementing $2" --active-for 300 > /dev/null || true
}

# fsa_task_row_finish <state> <run-id>
fsa_task_row_finish() {
  [ -n "$fsa_task_id" ] || return 0
  if [ "$1" = succeeded ]; then
    local status=in_progress
    [ "$fsa_task_format" = v2 ] && status=verifying
    fsa_task_cli set --id "$fsa_task_id" --status "$status" --owner lead --activity "" --active-for 0 \
      --note "$1: awaiting lead audit (run $2)" > /dev/null || true
  else
    fsa_task_cli set --id "$fsa_task_id" --status blocked --owner lead --activity "" --active-for 0 --note "$1: see run $2" > /dev/null || true
  fi
  return 0
}

# fsa_build_warn <brief>: the BUILD command runs inside the implementer sandbox, which has no sg or docker.
fsa_build_warn() {
  grep -E '^BUILD:' "$1" 2>/dev/null | grep -qE '(^BUILD:|[[:space:];&|(`])(sg|docker) ' &&
    echo "fullstack-agents: BUILD must run inside the implementer sandbox; drop sg/docker" >&2
  return 0
}
