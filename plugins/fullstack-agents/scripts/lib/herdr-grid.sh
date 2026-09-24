# Workers form one row under the calling pane: the first splits it down, later ones split the rightmost worker.
herdr_worker_pane() {
  local cwd=$1 layout caller_y target dir
  layout=$(herdr pane layout --pane "$HERDR_PANE_ID")
  caller_y=$(jq -r --arg p "$HERDR_PANE_ID" '.result.layout.panes[] | select(.pane_id == $p) | .rect.y' <<<"$layout")
  target=$(jq -r --argjson y "$caller_y" '[.result.layout.panes[] | select(.rect.y > $y)] | max_by(.rect.x) | .pane_id // empty' <<<"$layout")
  if [ -n "$target" ]; then dir=right; else target=$HERDR_PANE_ID; dir=down; fi
  herdr pane split "$target" --direction "$dir" --cwd "$cwd" --no-focus | jq -re '.result.pane.pane_id'
}
