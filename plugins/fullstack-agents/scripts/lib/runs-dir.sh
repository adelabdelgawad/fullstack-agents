# Sourced: one run registry for dispatchers, gates and readers (FSA_CODEX_RUNS_DIR, then the project binding, then the default).

# fsa_binding <root> <key>: value of <root>/.claude/fsa-team.conf's `key`, or nothing; list keys print one item per line.
fsa_binding() {
  python3 -I "$(dirname "${BASH_SOURCE[0]}")/team_conf.py" get "$1" "$2"
}

fsa_expand_home() {
  case "$1" in
    "~") printf '%s' "$HOME" ;;
    "~/"*) printf '%s/%s' "$HOME" "${1#\~/}" ;;
    *) printf '%s' "$1" ;;
  esac
}

# fsa_runs_dir <root>: the primary registry directory new runs are written to.
fsa_runs_dir() {
  local bound
  if [ -n "${FSA_CODEX_RUNS_DIR:-}" ]; then
    printf '%s\n' "$FSA_CODEX_RUNS_DIR"
    return 0
  fi
  bound=$(fsa_binding "$1" runs_dir)
  if [ -n "$bound" ]; then
    printf '%s\n' "$(fsa_expand_home "$bound")"
  else
    printf '%s\n' "$HOME/.codex/fsa-runs"
  fi
}

# fsa_runs_read_dirs <root> [extra-dir]: every directory readers must scan, primary first, existing legacy dirs after.
fsa_runs_read_dirs() {
  local d seen=" " dirs=()
  while IFS= read -r d; do
    [ -n "$d" ] && dirs+=("$d")
  done < <(fsa_binding "$1" legacy_runs_dirs)
  for d in "$(fsa_runs_dir "$1")" ${2:+"$2"} "${dirs[@]}"; do
    [ -n "$d" ] || continue
    d=$(fsa_expand_home "$d")
    case "$seen" in *" $d "*) continue ;; esac
    seen+="$d "
    [ -d "$d" ] && printf '%s\n' "$d"
  done
  return 0
}
