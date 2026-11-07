# Herdr touch scrolling

Cause: both xterm clients use zero local scrollback. xterm 5.5's touch
handler only scrolls its local viewport (and ignores mouse-reporting apps).
Wheel events already reach the remote application.

Implement a shared disposable touch-to-wheel adapter, preserving touch position
for Herdr pane routing, taps, multi-touch, and listener cleanup. Wire it to both
the full Herdr console and the individual live terminal.

Files: dashboard/src/terminal/{touchScroll.ts,touchScroll.test.ts,
herdrClient.ts,liveTerminal.ts}; rebuild dashboard assets after validation.
Preserve existing unrelated changes, including herdrClient.ts and built assets.

Acceptance: vertical one-finger swipes emit correctly directed wheel events;
small movements accumulate; taps and multi-touch emit no scroll; cancellation
and disposal discard gesture state. Existing wheel handling stays intact.

Checks: focused regression tests (red then green), dashboard tests, TypeScript
and Vite build, bounded Claude audit. Physical iPad Safari is unavailable here.
Style: React/Vite, strict TypeScript, relative imports, two-space indentation,
Vitest/jsdom; terminal event resources have explicit disposal.

Validation evidence: /tmp/herdr-touch-tests.log (119 tests pass),
/tmp/herdr-touch-build.log (TypeScript/Vite pass; existing runtime font warnings),
/tmp/herdr-touch-browser.log (real Chromium/xterm: zero mouse reports before
adapter, two up and one down SGR reports after; coordinates preserved).
Browser harness: /tmp/herdr-touch-browser.mjs.
The pre-existing sidebar toggle diff in herdrClient.ts is outside this task;
review only touchScroll import/state/disposal/installation in that file.

Repair review: the first Claude output identified a replaced DOM text target
breaking subsequent scrolling. Confirmed in DomRenderer.ts replaceChildren and
a failing regression test. Wheel events now dispatch on the stable xterm screen;
gesture listeners stay directly on the initial touch target until end/cancel,
even if detached. The browser harness now redraws real DOM-rendered xterm output
mid-swipe and checks continued SGR reports. Test and build logs above are refreshed.
First audit artifacts: /tmp/herdr-touch-audit/fsa-claude-audit-_ms1e7b8/claude.json.
Its response failed schema validation because repair_scope entries included prose.
For this audit, repair_scope entries must be exact repository-relative file paths,
with descriptions only in issue/evidence. Do not include prose in path strings.
