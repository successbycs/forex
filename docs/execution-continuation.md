# Execution continuation

`scripts/check_execution_continuation.py` reads the execution-work record for
an active ExecPlan. It returns `CONTINUE` when an unfinished step has all its
dependencies complete, `BLOCKED` when every remaining path depends on a
recorded blocker, and `COMPLETE` when every recorded step is done. It does not
perform work, grant authority, change task state, or establish formal proof.

The selected record is named by the tracked
`config/execution-continuation.json` selector. It must name exactly one
repository-relative execution-work record; the stop hook refuses malformed or
escaping paths. Changing delivery waves therefore requires an explicit selector
update rather than leaving the hook permanently hard-coded to A1. A capacity
hold blocks only the dependent deployment and later observation; it cannot
conceal a test, review, package or diagnostic step that can still proceed.

`.codex/hooks.json` runs `scripts/codex_stop_hook.py` at the end of a Codex
turn. If the selected record says `CONTINUE`, the hook blocks a progress-only
stop and names the next item. It continues to do so on a second stop: an agent
must either execute the work or record a real terminal blocker. The hook is
advisory: it cannot run a command, approve an action, or override a user pause,
cancellation, review-only request, formal gate or platform constraint.

Codex requires a local hook to be reviewed and trusted before it runs. In the
Codex CLI, open `/hooks`, inspect the repository hook definition and trust it.
Start a new session afterwards so the changed repository guidance and hook are
loaded. This requirement comes from Codex’s hook trust model, documented in
[the official hooks guide](https://learn.chatgpt.com/docs/hooks).

Implementation review on 2026-09-14 accepted the checker and hook after a
deeply nested malformed JSON regression was added. The focused checker and hook
suite passed 16 tests in the independent review. This establishes repository
behavior only; hook trust is a local Codex-client action.
