# Routine workflow improvements

<!-- fsa:tasks:start -->
| ID | Status | Task | Note |
| --- | --- | --- | --- |
| D1 | done | Deploy hold hook: a user's no-deploy blocks deploy commands until lifted | deploy_hold.py + hook; 6 tests; past prompts classified |
| D2 | done | Lead prompt: no invented go-ahead gates; plain terms | lead prompt: no invented gates, plain terms; task-flow ending rule |
| D3 | done | Status line shows ledger step | fsa-statusline; user settings statusLine (backup settings.json.bak373); live after install |
| D4 | done | Arabic-layout slash command hint | layout-hint hook; exact command allowlist; 3 tests |
| D5 | done | Plugin release + UCM install | 3.74.0 56446bacf8bb pushed; UCM user scope installed; dashboard 447 OK, codex OK, hooks 13/13 |
| D6 | done | keep-connect: standing authorization rule with user veto; project skills allowed | keep-connect 739a498b1 pushed: standing authorization + veto, skills dir |
| D7 | done | keep-connect: call-triage skill + read-only script | scripts/call-triage + skill; 4 modes run on prod read-only; write refused |
| D8 | done | keep-connect: asr-eval skill pointing to existing runbooks | asr-eval skill; scorer missing from repo noted |
<!-- fsa:tasks:end -->
