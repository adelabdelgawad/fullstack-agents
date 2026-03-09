---
name: debug
description: Use when encountering any bug, error, or unexpected behavior in a fullstack project — enforces root-cause-first debugging discipline before any fix attempts
---

# Debugging Discipline

## The Iron Law

**NO FIXES WITHOUT UNDERSTANDING THE ROOT CAUSE FIRST.**

Not "try this and see." Not "it might be X." You trace it, you understand it, then you fix it. Violating the letter of this rule is violating the spirit.

## When to Use

- Any error, exception, or stack trace
- Unexpected behavior (wrong output, missing data, UI not updating)
- Performance degradation (slow endpoint, high memory, timeout)
- Flaky behavior (works sometimes, fails sometimes)
- Something that "should work" but doesn't

## The Process

Four phases. Sequential. No skipping.

```
REPRODUCE → INVESTIGATE → FIX → VERIFY
```

### Phase 1: REPRODUCE

Confirm the bug exists. Get a reliable way to trigger it.

- Run the failing code / hit the failing endpoint / reproduce the user's steps
- Capture the exact error output, status code, or wrong behavior
- Note the environment: which service, which endpoint, what input
- If you cannot reproduce it, you cannot fix it — investigate why reproduction fails first

**Gate:** You have a repeatable reproduction before moving to Phase 2.

### Phase 2: INVESTIGATE

Understand what is happening and why. This is where the real work lives.

- Read the full stack trace — not just the error message, the entire call chain
- Trace the data flow from input to failure point
- Find where expectations diverge from reality (expected X, got Y)
- Check recent changes: `git log --oneline -10 -- <file>` on the failing path
- Use the debug agents as operational tools:

| Symptom | Agent |
|---------|-------|
| Stack trace / exception | `/debug error` |
| Slow response / timeout | `/debug performance` |
| 4xx/5xx / CORS / auth issues | `/debug api` |
| Recurring patterns in logs | `/debug logs` |

**Gate:** You can explain the root cause in one sentence before moving to Phase 3.

### Phase 3: FIX

Minimal, targeted change. One fix per root cause.

- Fix the root cause, not the symptom
- Change only what is necessary — no drive-by refactoring
- If the fix requires changing more than 3 files, pause and verify you're fixing the right thing
- If the fix is a try/except or error suppression, you are not fixing — you are hiding

### Phase 4: VERIFY

Confirm the fix works. Confirm nothing else broke.

- Re-run the exact reproduction from Phase 1 — it must pass
- Run related tests: `pytest <test_file>` or the relevant test suite
- If the bug was in an API: hit the endpoint again, check the response
- If the bug was visual: reload the page, verify the UI
- If you cannot verify, the fix is not complete

**Gate:** Fresh evidence that the fix works before claiming completion.

## Red Flags — STOP and Return to Phase 1

If any of these are true, you have left the process:

- Each fix reveals a new problem in a different place
- You are changing code you don't fully understand
- You are adding try/except or error suppression instead of fixing the cause
- The fix works but you cannot explain why
- You have applied 3+ attempted fixes without success
- You are editing files not in the stack trace

**ALL of these mean: STOP. Go back to Phase 2. Re-investigate.**

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Let me just try changing this" | That's guessing, not debugging |
| "It works now, ship it" | If you can't explain why, it's not fixed |
| "I'll investigate properly next time" | This IS next time |
| "The error message is misleading" | Read the stack trace, not just the message |
| "It's probably a library bug" | It's almost never a library bug |
| "This is too complex to trace" | Break it into smaller steps. Trace each one |
| "I'll add logging and try again" | Add logging AND read existing logs first |

## Quick Reference

```
Phase 1: REPRODUCE  → Can you trigger it reliably?
Phase 2: INVESTIGATE → Can you explain the root cause in one sentence?
Phase 3: FIX        → Minimal change, root cause only
Phase 4: VERIFY     → Fresh evidence it works, no regressions
```

## Impact

From debugging sessions following this discipline:

- Systematic approach: 15-30 minutes to resolution
- Guessing approach: 2-3 hours of thrashing
- First-time fix rate with discipline: ~90%
- First-time fix rate without: ~40%
- Regressions introduced: near zero vs. common
