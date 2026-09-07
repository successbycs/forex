# Wave 1 progress and proposed risk policy

Status: **IN PROGRESS — Option B is implemented locally and its PostgreSQL schema is applied on Demo; a hash-bound runtime deployment and independently verified Demo lifecycle proof remain.**

## W1.1 completed locally

The development-phase total trade-count ceiling is removed. The canonical
runtime configuration, M20 contract wording, schema, fixed lease validator,
and audit bridge now require `maximum_trades: null`. This preserves the
independent one-open-position, per-trade notional, cumulative-notional, and
per-trade maximum-loss controls.

The USD 100,000 *cumulative notional* limit still remains. It is not a
trade-count control, but at the maximum USD 10,000 notional it can practically
limit a lease to ten full-size entries. It needs a separate operator decision
if development trading must be unlimited by both count and cumulative
exposure.

## W1.2 and W1.3 progress

The local runner now distinguishes an MT5 API error from an empty position
result, and refuses new execution when either position or deal-history reads
fail. A broker-reported full or partial fill is not called rejected merely
because terminal position observation fails: it is recorded as `UNKNOWN` and
the reserved attempt remains entry-blocking. Migration `017_m20_unresolved_execution_state.sql` is applied on the fixed Demo PostgreSQL surface; the changed runner still must be deployed before it can govern executions.

Closed-outcome reconciliation now queries the broker position identifier,
requires matching opening and closing market deals with equal aggregate volume,
uses the volume-weighted closing price, and retains commission, fee, and swap as
actual broker amounts. Spread/slippage estimates remain separate from actual
net P&L. Missing or incomplete broker history remains unresolved rather than
being archived as a failed close.

## Recommended low-risk Demo drawdown policy

This is a conservative starting policy for an unproven M1 strategy. It makes
continued operation conditional on capital preservation, not on producing a
trade count or income target.

| Control | Recommended value | Action at breach |
| --- | ---: | --- |
| Planned loss per new trade | Lesser of AUD 100 and 0.10% of policy equity | Refuse the proposal if minimum broker volume cannot fit. |
| Daily net-loss budget | 0.50% of policy equity | Pause new entries until the next Auckland trading day. Existing broker SL/TP remains managed. |
| Weekly net-loss budget | 1.00% of policy equity | Pause new entries until an operator reviews and resumes. |
| Peak adjusted-equity drawdown | 2.00% | Hard pause new entries until an operator reviews and resumes. |
| Unknown equity, account currency, cash flow, position, protection, or reconciliation | Zero tolerance | Fail closed: no new entry; preserve and monitor any protected open position. |

### Definitions

- **Policy equity** is the reported AUD account equity after approved external
  cash-flow adjustments. It is never inferred from deposits, withdrawals, or
  balance adjustments.
- **Adjusted equity** = broker equity minus approved deposits plus approved
  withdrawals made after the policy baseline. A balance or cash-flow change
  without a matching, durable operator record blocks new entries.
- **Daily net loss** compares current adjusted equity with the fixed Auckland
  day-start adjusted-equity anchor. It includes unrealised P&L and therefore
  does not wait for a trade to close before stopping further risk.
- **Weekly net loss** uses the same method from the Monday Auckland anchor.
- **Peak adjusted-equity drawdown** is the loss from the highest durable
  adjusted-equity observation since the operator set the baseline. It includes
  unrealised P&L and never resets automatically.
- **Net** means the broker account result after actual fills, commission, fees,
  and swap. Execution estimates remain separate and are not subtracted again.

### Durable pause and reset rules

Persist the baseline, anchors, peak, expected broker balance, approved cash-flow adjustment, and pause reason in the PostgreSQL audit state. A listener restart or a new
Demo lease reads this state before it may reserve an order.

- A daily pause expires only at the next Auckland day boundary after an
  account/equity read succeeds. It does not clear a weekly or drawdown pause.
- Weekly-loss, peak-drawdown, and cash-flow pauses require the fixed
  `m20_listener_resume_risk_policy` operator action. It writes an append-only
  resume request; the next account check re-applies all limits. For an external
  cash flow only, that review shifts balance and equity anchors by the observed
  cash-flow amount so adjusted-equity drawdown remains continuous.
- An operator cannot reset the peak merely by creating a new lease. Resetting
  a baseline needs a separately recorded capital change and a new approved
  policy revision.

## Proof still required

Local tests do not prove W1. The changed release must be staged on the fixed
Demo surface, its effective limits read back, and then independently checked.
W1.2 and W1.3 remain in progress: MT5 API error handling, partial-fill state,
and broker deal-history reconciliation require further implementation and
Demo evidence. Option B values and pause authority are now approved. Migrations 016 through 021 have been staged and applied successfully to the fixed Demo PostgreSQL surface; the read-only audit verifier passes. The remaining decision is whether USD 100,000 cumulative notional should remain during the development phase.

## 2026-09-07 deployment correction

The previously deployed listener release `402ea373eafcc9f2` did not include the
Wave 1 risk guard and its risk-policy state was uninitialised. It was idle with
no protected position, and the fixed listener-stop operation returned `stopped: true`.
The legacy status operation is not a valid independent stop check because it
auto-restarts a stale listener; the pending release removes that side effect.
The pending release makes listener status read-only; recovery remains a separate
fixed operator operation so an inspection cannot restart execution.

The T480 endpoint rejects commands above roughly 2.5 KB. The deployment
protocol now uses fifteen service fragments, sixty-four runner fragments, and
thirty-two audit-bridge fragments. It verifies all four staged payload hashes
in a short fixed operation, records that release, and only then writes the
non-secret configuration containing the governed risk policy. This preserves
the configuration-to-release binding while fitting the endpoint limit.

The deployment source is committed because its configured application revision
is bound to `git HEAD`.

## 2026-09-07 Demo deployment evidence

Release `274556076400bc3c` was staged and installed after the remote SHA-256
checks for the listener, runner, PostgreSQL audit bridge, and Discord adapter.
The task produced a fresh heartbeat on `GOMarketsMU-Demo` for EURUSD and made a
valid `NO_TRADE` decision; it did not place an order.

The new continuous Demo lease is `3a44122e-4575-4e08-b632-8a506afc7293` and
has `maximum_trades: null`, one open position, USD 10,000 maximum notional per
trade, USD 100,000 cumulative notional, and AUD 100 maximum loss per trade.

The remote PostgreSQL policy state was initialized in AUD at policy equity
AUD 100,995.51, with no pause. It recorded the Conservative Option B policy
and its daily 0.50%, weekly 1.00%, and peak drawdown 2.00% controls. The
read-only audit verifier returned `FOREX_M20_DEMO_AUDIT_VERIFY_OK` after
deployment.

This is deployment proof, not milestone closeout. A post-release accepted
broker lifecycle with fee-complete reconciliation, independent verification,
and the contract's review recommendation remain required.

## 2026-09-07 unresolved-exposure gate

The deployed listener was restarted through its fixed recovery action after a
stale heartbeat. It produced a fresh heartbeat, then correctly failed closed
at the database one-position gate. The listener reported no protected current
broker position, but that observation cannot close a historical attempt.

The fixed read-only `forex-m20-unresolved-attempt-summary` identifies four
legacy attempts with `OPENED` then `FAILED` events. Each lacks a broker order
reference, position ticket, and position identifier. They are:

- `feffc714-c88f-5d34-bdca-705040a28565`
- `e0dac54c-6b56-5a84-9022-126c3c21e00b`
- `15dffa0b-0446-500c-af09-ddce686e11f9`
- `c66d1af4-3d00-56a8-83e2-881f1eec416b`

The gate must remain closed: a flat current terminal result cannot establish
how any of these historical broker executions ended. W1.2 and W1.3 are
**PENDING**, not failed, while retained broker history is insufficient to map
each attempt to exact opening and closing deals and their fees. W1.4's
open-position restart drill is also **PENDING** because no safely attributable
protected position is available.

Resumption requires retained broker deal/order history that identifies each
attempt's exact broker position, or a separately approved, hash-bound
reconciliation procedure that can prove the mapping without overwriting the
append-only audit record. Until then the listener may run only as a
fail-closed observer; it cannot submit a new order.
