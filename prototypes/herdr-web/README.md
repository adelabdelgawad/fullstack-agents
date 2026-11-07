# Herdr web prototype

A full `herdr` client in the browser: the server runs `herdr` in a pseudo-terminal and bridges it over one
WebSocket (binary frames carry terminal bytes both ways, a JSON text frame carries resizes). Herdr draws its
own sidebar, tabs, splits, selection and scrollback, as it does inside Ghostty on the desktop. The shipped
dashboard (`plugins/fullstack-agents/scripts/fsa-dashboard`) is untouched.

## Run

```bash
prototypes/herdr-web/server.py                 # localhost only; prints the URL with its token
prototypes/herdr-web/server.py --host 0.0.0.0  # reachable from another machine
```

Query parameters: `r=xterm` or `r=ghostty` picks the renderer, `session=<name>` attaches a named herdr
session (created if missing) instead of the default one. Each browser tab is a separate herdr client with its
own size; closing the tab detaches it, and the herdr session keeps running.

- Copy: drag selects inside herdr; herdr sends the text as OSC 52 and the page writes it to the clipboard.
  Over plain `http://` from another machine the Clipboard API is unavailable, so it falls back to
  `execCommand("copy")`; serve it over HTTPS or use localhost for the reliable path.
- **key lock**: fullscreen plus Keyboard Lock (Chromium) so Ctrl+W, Ctrl+T and Ctrl+N reach herdr.

## Findings (2026-11-02, headless Chromium, herdr 0.9.1)

| Check | xterm.js 5.5.0 | ghostty-web 0.4.0 |
|---|---|---|
| herdr UI, splits | renders cleanly | renders, with broken split borders and a wrong wrap |
| Click to focus a split | works (typed text lands in the clicked pane) | focus unchanged in `herdr pane list` |
| Copy over plain `http://<lan-ip>` | `execCommand` fallback copied (no Clipboard API there) | not reached: herdr never sees the drag |
| Drag-select | herdr selection, pane-only text via OSC 52 | browser selection across sidebar and panes |
| Drag past the top edge | herdr scrolls history (copied 143 lines, 3 screens) | no scroll (27 visible lines) |

ghostty-web 0.4.0 tracks the mouse-tracking mode (`hasMouseTracking()`) but its bundle has no encoder that
sends mouse events to the program, so every mouse feature of herdr is missing under it.
