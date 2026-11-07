# Herdr iPad touch scrolling

<!-- fsa:tasks:start -->
| ID | Status | Task | Note |
| --- | --- | --- | --- |
| T01 | done | Fix and verify live terminal touch scrolling | 119 tests, TypeScript/Vite build and real Chromium DOM-redraw swipe regression pass. Claude re-audit PASS, zero issues: /tmp/herdr-touch-audit/fsa-claude-audit-e86pstlk/handoff.json. Physical iPad untested. |
| T02 | done | Prepare reviewed fix for the live cached dashboard release | User approved and live cache updated atomically with backup. Authenticated :8766/next/app.js returns 200 and exact audited artifact hash f3647ac1...; /next/herdr returns 200; no-store headers; no restart. Evidence: /tmp/herdr-touch-live-verification.json. Physical iPad check remains user-side. |
<!-- fsa:tasks:end -->
