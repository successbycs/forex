# Demo MVP console sub-ExecPlan — operator surface and proof

This is a child of `demo-mvp-console-execplan.md`. Its design phase is complete;
implementation is authorised by the registered M33.5 parent scope; deployment
remains subject to the parent release gates.

## Outcome

One loopback-only, read-only console combines the live listener state, the
latest decision trace, active trade/reconciliation state, trade journal,
today/week/month actual P&L and strategy scorecard. The existing terminal
dashboard remains a supported diagnostic fallback.

## Interface

Extend the established local-reporting pattern in `scripts/m33_daily_pnl_web.py`
instead of creating a cloud service, generic remote shell, database console or
control plane. Bind only to `127.0.0.1`. The page has fixed GET views and a
strict date/range selector where required; it has no POST, credentials,
authentication bypass, websocket command path or order buttons. It must render
escaped source text, show source/generated times, and visually distinguish
`RUNNING`, `NO_TRADE`, `UNKNOWN`, `UNRECONCILED`, `PLANNED`, `FILLED`, and
`ASSUMED`.

Panels appear in this order: T480 runtime health; price-to-decision trace;
current trade/execution/reconciliation; per-trade journal; actual P&L
today/week/month; then strategy trial evidence. Status freshness is never
presented as trade permission. An open trade has no realised P&L unless a
separate future mark-to-market contract is approved.

## Proof and deployment design

Before deployment, run unit tests for every renderer and error state, then a
local browser test against fixture sources. Run the release-readiness process
before any T480 deployment. The deployment must use the existing fixed adapter
and hash-bound catalogue, must not introduce generic remote execution, and must
verify that the listener stays fresh before and after the report process is
started. The console must run as a separate read-only local process, not inside
the listener and not as a requirement for entry eligibility.

The user-visible proof is one natural closed Demo trade: operator observes its
trace, then later its broker-matched journal row and exact inclusion in the
correct period. No test or proof may force a trade. Failure proof is equally
important: a stale/unavailable source visibly says so and leaves Demo trading
unaffected.

## Demo trading continuity

`CONTINUE`: development, browser testing and console deployment do not justify
a hold. Only a separately observed listener/account safety incident can enter a
hold through the existing authorised procedure. A console failure is isolated;
stop its local process and continue using the existing terminal dashboard.

## Design progress and decisions

- [x] Selected one local read-only composition rather than a new service.
- [x] Defined panel order, failure labels and no-control boundary.
- [x] 2026-09-28: implemented `scripts/m33_mvp_console_web.py`, a
  `127.0.0.1`-bound fixed-GET console. It renders listener state, verified
  trace tail, fixed broker-matched system journal/P&L, and strategy evidence;
  it accepts no input and has no control route.
- [ ] Stage the fixed system P&L query, verify the deployed read sources, and
  run the local browser proof during the governed release.
