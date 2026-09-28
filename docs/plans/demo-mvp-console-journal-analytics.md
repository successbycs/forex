# Demo MVP console sub-ExecPlan — journal and period analytics

This is a child of `demo-mvp-console-execplan.md`. Its design phase is complete;
implementation is blocked pending the parent plan's formal-scope decision.

## Outcome

The operator sees an auditable trade journal and actual realised system P&L for
today, this week and this month. A value is included only when it can be traced
to one system-owned M20 proposal and a broker-matched closed Demo outcome.

## Membership and accounting contract

The base row is a final broker-matched, M20-attributed `CLOSED` lifecycle for
the fixed `GOMarketsMU-Demo` EURUSD path. It joins proposal, execution attempt,
position/reconciliation and broker outcome using their retained identities. It
must have one owner strategy/version and one recognised close time. Repaired or
revised source records use the current canonical revision while prior immutable
evidence remains retained.

The journal displays decision/close time, strategy/version, direction,
planned entry and actual fill where available, exit, volume, gross P&L,
commission, fee, swap and actual net P&L. `actual net P&L` is the broker
outcome amount; no page performs money arithmetic. An unavailable broker-cost
component or failed reconciliation makes the row `UNRECONCILED/UNAVAILABLE` and
excludes it from realised totals.

Today is midnight-to-now in `Pacific/Auckland`. This week begins Monday at
midnight in that timezone. This month begins on its first calendar day at
midnight. Each summary reports included matched-closed count, excluded
unreconciled count, actual net P&L and actual broker commission/fee/swap totals.
It must identify the time window and generated-at time. An `ASSUMED` Live
commission comparison, if retained, is separate from actual totals and never
changes them.

The broad broker-account P&L report remains a separate account view. It must
not be silently substituted for strategy/system performance because it can
include balance movements and non-listener history.

## Design and owned implementation paths

Reuse `scripts/m20_trade_ledger_dashboard.py`,
`scripts/m33_daily_pnl_report.py`, their fixed PostgreSQL read operations and
the existing immutable outcome tables. First write a single named, fixed,
read-only system-outcome summary operation; then make terminal and browser
renderers consume its exact response. It accepts no caller SQL and offers no
write, order, MT5 or risk operation. Whether the existing schema is sufficient
is an implementation discovery: add a migration only if a required canonical
membership fact cannot be obtained without inference, and only under an
explicitly authorised database/release sub-step.

## Acceptance and verification

Fixtures must include: two matched system outcomes spanning a week/month
boundary; an unreconciled lifecycle; a rejected attempt; a manual/balance
broker row; a zero actual commission; and an assumed comparison. Verify each
included trade appears once, every excluded row has a reason, boundaries use
Pacific/Auckland correctly, totals equal the returned included journal rows,
and actual/assumed values cannot be combined. Compare a selected natural
closed lifecycle from the fixed source through the summary and renderer.

## Demo trading continuity

`CONTINUE`: all data reads are fixed and read-only. A failed report or database
read reports unavailable data; it does not alter a listener, MT5, lease, risk
policy or order.

## Design progress and decisions

- [x] Defined strict system-owned, matched-closed membership for strategy P&L.
- [x] Defined Auckland day/week/month boundaries and unavailable/exclusion
  rules.
- [ ] Implement after formal scope approval.
