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

## 2026-09-07 retained broker-history attribution

The fixed `m20_unresolved_history_probe` read the Demo EURUSD deal history
for the four unresolved timestamps. It applies the governed +10,800-second
broker timestamp offset before comparison. Each mapping is unique by adjusted
open time, action, and 0.01-lot volume:

| Attempt | Broker position | Open UTC | Close UTC | Net AUD | Broker charges |
| --- | ---: | --- | --- | ---: | --- |
| `feffc714-c88f-5d34-bdca-705040a28565` | 41488649 | 09:18:05 | 09:28:07 | 0.18 | commission 0, fee 0, swap 0 |
| `e0dac54c-6b56-5a84-9022-126c3c21e00b` | 41495536 | 11:18:08 | 11:21:00 | 0.01 | commission 0, fee 0, swap 0 |
| `15dffa0b-0446-500c-af09-ddce686e11f9` | 41499398 | 12:04:03 | 12:13:02 | -0.56 | commission 0, fee 0, swap 0 |
| `c66d1af4-3d00-56a8-83e2-881f1eec416b` | 41499981 | 12:13:07 | 12:15:01 | -0.21 | commission 0, fee 0, swap 0 |

This closes the retained-broker-history gap, but does not alter the immutable
audit. The current bridge correctly refuses `record-closed-outcome` without a
durable open-position state row, which these legacy attempts predate. The
remaining W1.2/W1.3 implementation is a fixed append-only historical
reconciliation action that validates these deal sets, appends provenance and a
reconciliation revision, and never modifies the existing `OPENED` or `FAILED`
events. Until it is independently verified, the global one-position gate must
remain closed.

## 2026-09-07 fixed retained-history reconciliation prepared

A local, hash-bound reconciliation path is prepared for the four attributed
legacy attempts. It has no caller-supplied account, symbol, position, deal, or
SQL input. It re-reads each exact Demo broker position identifier, requires two
EURUSD market deals with the recorded UTC timestamps, directions, 0.01-lot
volumes, and AUD net P&L, then asks the audit bridge to append the following
new records:

- one immutable `CLOSED` event carrying the complete broker deal set and its
  SHA-256 digest;
- one fee-complete `MATCHED` AUD outcome, with unavailable historical
  spread/slippage estimates kept `NULL`; and
- one immutable `REPAIRED` reconciliation revision whose source records the
  absence of a legacy outcome.

The existing `OPENED` and `FAILED` events are not modified. The action cannot
submit or modify an order, and it does not change the persistent risk-policy
state: the policy baseline was initialized after these historical closes, so
adding their P&L to `expected_balance` would create a false cash-flow signal.

The reconciliation is not yet deployed or executed. It changes the governed
T480 command catalog, so it needs a new revision, configuration-fingerprint
refresh, hash-checked release deployment, and an explicit operator decision
before the append-only remote database write. Local validation covers all four
broker deal mappings and the broader Wave 1 focused test suite; the current
milestone validator correctly reports configuration-fingerprint drift until
that governed configuration is formally adopted.

## 2026-09-07 retained-history reconciliation executed and verified

Release `073853dd0cce8d57` was hash-verified, prepared, configured, and
installed on the fixed `GOMarketsMU-Demo` EURUSD listener surface. The first
reconciliation execution failed closed before writing because the bridge lacked
a UUID function import. The defect and deployment guard were corrected in
commits `5b1a0d8` and `4c3a845`; installation now refuses a release that lacks
a successful hash-bound preparation.

The corrected fixed reconciliation then completed with
`FOREX_M20_HISTORICAL_RECONCILIATION_OPERATION_OK`. It appended all four
broker-attributed legacy lifecycles. The independent read-only unresolved
summary is now `[]`. The lifecycle ledger records, for every recovered attempt,
`OPENED`, `FAILED`, and appended `CLOSED` events, a `REPAIRED` outcome, actual
commission, fee, and swap of AUD 0.00, and the retained broker-history reason.
The recovered net total is AUD -0.58.

The persistent conservative-risk policy remains unpaused, with the original
AUD 100,995.51 baseline, expected balance, peak, daily anchor, and weekly
anchor. The reconciliation did not treat historic P&L as a current cash flow.
The independent audit verifier returned
`FOREX_M20_DEMO_AUDIT_VERIFY_OK`, including Demo-only, cap, idempotency,
immutable-trigger, and fee-completeness checks. The listener then produced a
fresh `RUNNING` heartbeat and a normal `NO_TRADE` assessment without a
protected broker position.

This clears the four legacy unresolved-attempt blockers for W1.2/W1.3. Wave 1
is still not complete: it needs a clean, post-release accepted Demo
`OPENED`-to-`CLOSED` lifecycle with broker fees, the W1.4 restrictive-risk and
recovery drills, retained raw proof, independent verification, and the
contract-required review recommendation.

## 2026-09-07 Wave 1 resumed: current lifecycle, liveness, and safe checkpoint

At 02:40 UTC, the fixed read-only listener status was stale on deployed release
`073853dd0cce8d57`. Its last durable monitor record named the unresolved Demo
SELL attempt `a78aec5c-6dd3-5f91-aaa4-464571e2cc93`, broker position
`41751387`, with its recorded SL and TP. The weaker account-liquidity helper
reported zero positions, but it intentionally treats an unavailable MT5
position result as an empty collection and therefore could not close that
attempt.

The fixed `m20_listener_recover` operation restarted only the existing
`Forex-M20-Demo-Listener` Scheduled Task. It did not expose an arbitrary order
operation. The restarted monitor reconciled that durable attempt to a
broker-side close at 14:40:43 NZST. The independent lifecycle summary reports
an exact `OPENED` then `CLOSED` lifecycle, entry 1.16085, exit 1.16106, AUD
realised P&L -0.29, and broker commission, fee, and swap each AUD 0.00. Its
reconciliation status is `MATCHED`; the unresolved-attempt summary is `[]` and
the independent audit verifier returned `FOREX_M20_DEMO_AUDIT_VERIFY_OK`.

At 02:44 UTC the existing deployed listener was again `RUNNING` with a fresh
heartbeat, an IDLE successful monitor result, and no current protected
position. This is a current operational observation, not a final evidence
bundle or a claim of continuous uptime. The zero broker charges make this a
fee-complete zero-charge lifecycle; it does not demonstrate nonzero-fee
handling, which remains pending actual observation.

The risk state is fail-closed with `EXTERNAL_CASH_FLOW`, even though its
expected balance and observed account balance both now equal AUD 100,995.22.
The likely sequence is that the restarted runner assessed balance before the
supervisor reconciled the already broker-closed tracked position; it briefly
saw the -0.29 realised trade movement as unexplained cash flow. This is an
inference from the persisted timestamps and state, not a claimed direct remote
exception trace. No resume action was issued. The pause prevents new entries
until a recorded review, so it is safe but not correct evidence of an actual
deposit or withdrawal.

Local changes now make startup reconcile durable open-position state before
the first assessment/risk gate, and fail closed with
`MONITORING_UNAVAILABLE` if that reconciliation cannot run. They also prevent
a bounded monitor pass from causing a negative `sleep()` interval and a stale
supervisor. Focused listener, M20 trading, T480 adapter, and runtime-config
tests pass, as do milestone governance validation and `git diff --check`.
These changes are **not deployed**: the T480 release protocol binds
`application_revision` to `git HEAD`, and this goal does not authorise a
commit. Do not stage, prepare, configure, or install this uncommitted source as
proof for the existing revision.

### Exact resumption conditions

1. Obtain explicit commit authority for the reviewed listener and test changes.
   Commit the exact source, then refresh any affected fingerprint and stage,
   prepare, configure, and install its hash-bound release. Capture a fresh
   listener status and strict lifecycle/risk summaries after deployment.
2. Verify the false `EXTERNAL_CASH_FLOW` pause was not caused by a real account
   cash flow. If it was not, use the fixed resume action only after that
   operator review, then verify the next account check remains unpaused and
   matches expected balance. If it was real, record the approved cash-flow
   adjustment instead; do not resume on inference alone.
3. Obtain an explicit temporary restrictive-limit value and restoration
   procedure for the W1.4 refusal drill. Run it only against the deployed
   hash-bound release, with no intentional loss, and retain before/after risk
   state plus restart/protected-position proof.
4. Capture a clean-worktree, post-deployment M20 evidence bundle and run the
   independent verifier. Current documentation and uncommitted source make the
   fixed capture command correctly refuse a bundle today. A fresh zero-charge
   lifecycle exists, but a nonzero broker charge remains an explicit pending
   W1.3 condition when the broker supplies one.

Wave 1 remains **IN PROGRESS**. No M20 closeout, production access, strategy
expansion, new lease, risk-policy resume, commit, or deployment was performed
by this checkpoint.
