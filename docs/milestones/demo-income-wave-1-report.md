# Wave 1 progress and proposed risk policy

## 2026-09-10 continuation checkpoint — inspection only, budget stop

**Wave 1 remains incomplete. No implementation, deployment, restart, risk
resume, hold release or trade was performed in this continuation.**

Read the supplied goal objective and the required wave guide, W1 specification,
W1.R package, resume prompt and this full report. Inspected Git status,
AGENTS.md, current project state, the complete active M20 contract, evidence
rules and current risk implementation. Preserved the existing wave/research
documentation edits, run-history changes and other local work.

The fixed read-only `m20_listener_status` observation at
`2026-09-09T23:28:12Z` (10 September 11:28 NZST) reports:

- release `c523b1c904b8aa51`, `state=STALE`, `running=false` as derived by the
  status helper from heartbeat freshness;
- last heartbeat `2026-09-09T22:46:03.472998Z`, age 2,528 seconds;
- last recorded detail is the maintenance hold, with an IDLE/empty recovery
  result at that old heartbeat;
- historical ticket `41760154` remains `LAST_KNOWN_UNVERIFIED`.

The adapter retained its raw operation response in its configured append-only
execution log. This is a new status observation, not current broker exposure,
proof of process termination or a verified live job handle. The actual task,
process and broker state require diagnostics before any restart. Do not infer
flat exposure from the stale empty recovery result. No current backup or
no-logon recovery proof was checked in this continuation.

Current `enforce_risk_policy` still stores a single `pause_reason` and only
evaluates weekly/drawdown breaches when it is empty. Day rollover clears a
daily reason. This confirms that the reviewed latch defect remains in source;
no new behavioural reproduction or fix was performed during this checkpoint.
The active M20 state remains `NEEDS_FIX`.

### Concrete remaining plan

1. Inspect actual scheduled-task/process diagnostics and current shared-runtime
   state without restarting a healthy service. Confirm maintenance hold and
   broker/audit exposure through the permitted serialized surface.
2. Reproduce overlapping daily/weekly/drawdown breaches with the actual risk
   function, then implement independent persistent reasons and resume handling.
   Test recovery, rollover, restart, cash-flow overlap and remaining headroom
   against isolated persistence. Preserve Option B thresholds and anchors.
3. Verify technical-stop sizing and cost/reservation headroom; prepare any
   exact required execution-rule amendment before dependent deployment.
4. Review and commit the narrowly scoped authorised fixes; prepare a hash-bound
   release and rollback. Preserve unrelated documentation/local work. Confirm
   shared backup/restore prerequisites before disruptive host/database drills.
5. Complete W1.R recovery and W1.1 effective-limit proof, W1.2 genuine lifecycle
   and interruption proof, W1.3 broker accounting/charge observations, W1.4
   protected-position restart and actual restrictive-limit refusal. Restore
   Option B immediately after the approved AUD 0.01 drill. Keep unobserved
   partial fills/nonzero charges explicitly pending where required.
6. Independently verify retained raw evidence and obtain required bound review;
   do not claim Wave 1 or M20 complete from local tests or this handover.

### Budget and resumption condition

The objective explicitly limits execution to 25,000 tokens. The active goal
mechanism has no recorded cap and provides no tool to change an active budget.
The first usage recheck reported **30,948 tokens**, exceeding the requested
limit during required document/current-state loading. Execution stopped at
this inspection checkpoint; the excess is disclosed rather than represented
as compliance. No budget increase or replacement goal was created.

Resume implementation only with renewed operator budget authority. Use this
checkpoint and the inspected current specifications to avoid another full
historical-report reload unless the objective requires it; inspect changes and
fresh external state. The goal remains unfinished, not complete or formally
blocked merely because its budget was exceeded.

## Earlier checkpoints — historical observations follow

Status: **IN PROGRESS — Option B and the corrected listener are deployed on Demo. The Windows/Ubuntu risk-resume defect is resolved and independently checked. Fresh lifecycle/recovery evidence and final bound verification remain. See the latest checkpoint below.**

## 2026-09-07 W1.R execution checkpoint — maintenance hold and T480 continuity

W1.R is in progress. The listener remains in the fixed
`W1R_COORDINATED_MAINTENANCE` hold, so it continues bounded broker-side
reconciliation but cannot assess a quote or submit a Demo entry. Do not remove
that hold while the recovery drill remains incomplete.

The following corrections are deployed on the fixed `GOMarketsMU-Demo`
surface:

- Every per-position recovery failure now makes the supervisor fail closed;
  a successful process exit cannot report `IDLE` over a failed recovery.
- A failed MT5 `positions_get()` result is reported as unavailable, rather
  than as zero positions.
- The listener status separates durable protection from fresh observation.
  The retained historical SELL ticket `41760154` therefore reports
  `LAST_KNOWN_UNVERIFIED`; it is not represented as a current protected
  position. A direct successful broker read at the maintenance boundary
  reported `GOMarketsMU-Demo`, AUD, and zero open positions.
- Release `c523b1c904b8aa51` produced a fresh `MAINTENANCE_HOLD` heartbeat
  and successful empty recovery. Its hashes and configuration were prepared
  before install. The installed listener now uses a Windows boot trigger with
  passwordless S4U for the registered user, rather than a logon trigger.

The shared T480 startup dependency was also tested without extending or
closing its M5 milestone. Its temporary S4U probe completed successfully and
could see the Ubuntu distribution. The original boot action was found to name
an unavailable `health_dashboard` Compose service in the deployed checkout;
this terminated its WSL keepalive even though already-running endpoints still
returned health responses. The shared correction starts only `n8n` (which
starts PostgreSQL through Compose dependency resolution) and relies on the
dashboard's own restart policy. It passed the shared local suite and the
updated boot-triggered S4U task was registered with the former task XML kept
on T480 for rollback. A manually started task returned Ready with n8n and
dashboard health endpoints responding, but that is not no-logon reboot proof.

The host reboot drill was intentionally not run. The shared maintenance
preflight did not provide a usable current backup marker, and the shared M5
contract says to stop in that condition. No claim is made about reboot,
detached-T16, or post-reboot recovery. The exact resumption condition is:

1. produce and independently verify a current recovery-safe backup marker on
   the shared T480 surface;
2. retain a new flat-account and active-hold broker observation immediately
   before the drill; and
3. run the approved reboot, then capture fresh task, WSL/PostgreSQL, MT5 Demo
   identity, listener and risk-state evidence without Windows sign-in.

W1.R has not supplied W1.2/W1.4 protected-position restart proof, a nonzero
broker-charge outcome, incident/notification delivery proof, the full
detached-T16 window, or the contract-required final independent review.
Those remain pending and Wave 1 is not complete.

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

## 2026-09-07 authorised deployment and W1.4 refusal drill

The operator authorised the reviewed changes, confirmed that no external cash
flow occurred around the AUD -0.29 close, and approved an AUD 0.01 temporary
planned-loss limit solely for the refusal drill. Commits `71eb182` and
`83f302f` deployed release `29072a8900d6831b` with configuration fingerprint
`sha256:8a4f7d278e3b536b31f7f6c272ce032719877af7075c62cdd60ab0c1ae3a55e6`.
The release hash gate initially rejected a duplicated staged service segment;
no deployment occurred until a clean restage passed prepare, configure, and
install. The new listener then reported a fresh `RUNNING` heartbeat, an IDLE
empty durable-position recovery, and no protected position.

For the drill, the listener was stopped before the temporary five-minute
Demo-only lease was installed. The fixed no-order calculation used live
GOMarketsMU-Demo EURUSD metadata: minimum volume 0.01 and a minimum-increment
loss of AUD 0.013893. That exceeds the approved AUD 0.01 cap, so it returned
`FOREX_M20_DEMO_RISK_REFUSAL_DRILL_OK` with
`M20 minimum EURUSD price increment exceeds the AUD loss cap` and
`order_submitted=false`. The standard continuous Demo lease was restored
immediately with the approved AUD 100 maximum loss, then the listener was
restarted and verified healthy.

The authorised `resume-risk-policy` request could not be recorded because its
local PostgreSQL connection at `127.0.0.1:5432` closed unexpectedly. The
persistent risk state therefore remains fail-closed; no entry is authorised
until that database path is healthy, the fixed resume request succeeds, and a
subsequent account check verifies the expected balance remains aligned. This
deployment and drill do not close Wave 1: fresh retained evidence, independent
verification, the required protected-position restart/recovery proof, and the
contract-required review recommendation remain outstanding.

A subsequent T480 PostgreSQL health probe reported the container healthy and
accepting local connections, but one immediate retry of the fixed resume
request produced the same connection-closed error. Treat the database path as
unavailable to the listener until its application connection succeeds; do not
retry it in a tight loop.

### Connection-path correction

The follow-up investigation identified an application adapter defect, not a
PostgreSQL outage. The trading runner's `_bridge()` invokes the verified bridge
inside T480 Ubuntu, where PostgreSQL is loopback-bound. The fixed resume action
instead invoked that bridge with Windows Python. The same `127.0.0.1` DSN then
addressed Windows rather than Ubuntu. At 03:01 UTC the listener's recovery and
independent PostgreSQL summaries were successful; the durable entry block was
still `EXTERNAL_CASH_FLOW`, with expected balance AUD 100,995.22 and no resume
record. The earlier statement that the listener's database path was unavailable
was therefore incorrect.

The resume adapter now invokes the same fixed Ubuntu bridge, retaining its
source hash check. It forwards the existing local DSN through `WSLENV` by name
and restores the previous environment afterward. No database endpoint, SQL,
account, or order parameter is exposed. Adapter regression tests and governance
validation pass. The existing operator confirmation of no external cash flow
authorises the recorded resume; its real-world result and subsequent balance
check must still be captured before claiming the blockage resolved.

### Resume verified on Demo; remaining Wave 1 proof

Commit `7d50038` fixes the resume adapter. The unchanged runtime payload release
`29072a8900d6831b` was hash-checked, rebound to that committed application
revision and the unchanged `sha256:8a4f7d278e3b536b31f7f6c272ce032719877af7075c62cdd60ab0c1ae3a55e6`
configuration, and restarted without replacing the current session lease.
The corrected resume succeeded at 03:03:31 UTC and created audit record
`b8694a8c-e227-4857-ae71-41e333d88d1c` for the reviewed `EXTERNAL_CASH_FLOW`
pause.

At 03:04 UTC, the subsequent risk check showed `pause_reason: null` and
`cash_flow_review_approved: false`. Expected balance, broker balance, and broker
equity all equalled AUD 100,995.22. Baseline, peak, daily anchor and weekly
anchor stayed unchanged at AUD 100,995.51. The strict durable-position recovery
succeeded with an empty result; the listener heartbeat was fresh. The
read-only audit verifier passed its Demo-only, exposure, proposal-first,
idempotency, append-only and fee-completeness checks. The temporary AUD 0.01
drill was not repeated and the approved Option B limits remain in effect.

Raw operation responses are retained unchanged under
`runs/evidence/M20/w1-resume-20260907T030324Z/`. Independent offline assertions
compared before/after state, the resume ID and timestamps, observed account
values, unchanged anchors, recovery, and audit output; the result and SHA-256
input hashes are separate at
`runs/verification/M20/w1-resume-20260907T030324Z/resume-verification.json`
(`FOREX_W1_RISK_RESUME_VERIFIED`). These are operational evidence, not a final
M20 bundle. The focused M20, adapter, accounting-dashboard and configuration
test suites passed, as did governance validation and `git diff --check`.

| Item | Current result and remaining condition |
| --- | --- |
| Reported PostgreSQL/resume blockage | **PASS — resolved.** Resume writes and subsequent risk checks work through T480 Ubuntu. |
| W1.1 release/configuration alignment | Rebound to `7d50038`; final effective-limit comparison in the bound Wave 1 bundle remains **PENDING**. |
| W1.2 lifecycle/recovery | The last retained matched lifecycle is the earlier AUD -0.29 close. The current lease `9673811b-0e23-47f9-b8e6-e0a86d1adf06` has no execution yet in the captured summary. Its genuine opened-to-closed lifecycle and controlled interruption/recovery proof remain **PENDING**. |
| W1.3 accounting proof | New sample must retain attributable raw broker deals and independently recompute fills, fees and net totals. Nonzero charges and partial fills remain unobserved; no synthetic observation is counted as broker proof. |
| W1.4 risk recovery | Resume and unchanged anchors across the flat restart/session history are verified. Restart with an actually open, broker-protected position remains **PENDING**. The prior AUD 0.01 calculation-only probe does not by itself demonstrate a listener assessment refusal or open-position recovery. |
| Final verification/review | **PENDING** until the required observations exist. No wave/milestone completion is claimed and no next wave is started. |

A clean detached worktree at `/tmp/forex-wave1-7d50038` is prepared for the
existing capture script; its governance and T480 preflight pass. This preserves
the main checkout's unrelated research/prompt work without weakening the
clean-revision rule. Do not invoke or recapture repeatedly while the required
lifecycle is absent. Resume proof work when the ordinary approved Demo listener
has an eligible protected position for the recovery drill and a current-lease
broker close. Preserve the lease and caps; do not force a trade or renew a lease
to manufacture evidence. No further operator decision is needed for the
resolved connection defect.

### Protected-open Wave 1 alert

The listener now issues one best-effort Discord message after all three real
conditions hold: the broker position is observed with positive entry, stop and
take-profit values; PostgreSQL has accepted the durable `OPENED` record; and
the local monitor job has been written. The message identifies the Demo EURUSD
side, volume, ticket, entry, SL and TP, then asks the operator to resume Wave
1. It cannot submit, modify, close, delay, or invalidate an order or lifecycle.

The listener status returns only `discord_open_alert_configured`, never a
webhook URL. Deployment preserves an already configured T480-local Discord
setting. The status must be `true` before the first eligible open; a synthetic
message is not proof and was not sent. The alert complements the dashboard; it
cannot automatically resume a Codex goal.

### SuccessByCS alert configuration and current availability checkpoint

At 05:39 UTC, the operator authorised use of the locally configured
SuccessByCS bot. The T480-local listener configuration was updated from the
existing local CSP configuration without printing, copying into the repository,
or committing the webhook secret. Release `8237331c7fa79d5a`, bound to source
revision `63b9a30d654186eb129aed6581a02a73d233e1c9` and configuration fingerprint
`sha256:da580b9e9131ff01987835cada4a7ada82465fdd3900fc38b8809d572a219eb5`, was
installed successfully. The status surface reported
`discord_open_alert_configured: true`. It does not expose the webhook URL.

The latest read-only status at 05:44 UTC then reported a fresh supervisor
heartbeat but `MONITORING_UNAVAILABLE`: its bounded durable-position monitor
received the MT5 error `Terminal: Authorization failed`. The listener correctly
failed closed and did not submit an assessment or an order. There was no open
position to protect. The fixed recovery operation at 05:45 UTC could not reach
T480 because SSH to `192.168.0.210:22` timed out during banner exchange; it did
not run and made no change to the scheduled task, broker, lease, or risk state.

Wave 1 remains **IN PROGRESS**. Resume when T480 is reachable, the MT5
GOMarketsMU-Demo terminal authorises again, and a read-only listener status
confirms a successful durable-position monitor before normal eligible Demo
operation continues. The next genuine protected `OPENED` event will send the
configured Discord alert, which is the cue to perform the authorised
open-position restart/recovery evidence drill. Do not force a trade, send a
synthetic Discord message, or treat the alert configuration itself as broker
proof.

### 2026-09-07 W1.R planning handover — not executed

The operator requested packaging of the reviewed fixes without execution.
[W1.R: T480 reliability and recovery](../prompts/demo-income-wave-1-recovery-work-package.md)
now supplies R1–R7, mapped to W1.1–W1.4, with owners, dependencies, acceptance,
real-world tests and rollback boundaries. The wave guide and both Wave 1 goal
entry points reference that package. This update changes planning documentation
only; no repair, deployment, restart, trade, goal resume or milestone transition
was performed, and no acceptance criterion is newly marked PASS.

The preceding review found intermittent SSH recovery and a shared PostgreSQL
shutdown/readiness gap from 15:47:10 to 17:39:15 NZST. Its cause was not proven.
The listener was reachable again at the review's 17:54 NZST snapshot. These
observations supersede the interpretation of a permanently offline T480, not
the need for current checks. They are not a final raw evidence bundle.

The earlier statement that there was no position to protect during failed
observation was too strong. Unknown broker exposure must remain unknown; an
empty durable recovery list or missing protection field is insufficient proof
of flatness. The review also locally reproduced per-position `RECOVERY_FAILED`
being presented as `IDLE`. R2/R3 schedule those corrections; they are not yet
implemented by this planning update.

Next execution, when explicitly instructed, begins with W1.R's diagnosis and
state-handling prerequisites, then coordinated maintenance, proposed platform
continuity proof and original Wave 1 evidence. Reuse prior risk decisions and
completed implementation. Resolve only missing authority/contract scope for
dependent shared-platform drills. Preserve the original proof gaps and do not
automatically start another wave or the lab's own milestone.

## 2026-09-10 continuation — independent risk pauses implemented, deployment pending

**Wave 1 remains incomplete.** The operator supplied an additional 50,000-token
allowance. Implementation commit: `3472885` (`fix(wave1): preserve independent
risk pauses and gate reservations`). No push, branch, next wave, Live access,
new Demo lease or maintenance release occurred. The final goal-tool check
returned no registered goal; no native budget enforcement or completion is
claimed for this continuation.

### Implemented and reviewed locally

- Migration 022 retains each risk pause independently, backfills an existing
  scalar reason, preserves anchors/resume history, and prevents a legacy
  scalar-only writer from silently clearing the new latches.
- Daily rollover clears only the daily latch. Weekly/peak/manual reasons
  survive recovery, week rollover and process restart. An operator resume
  acknowledges one manual reason and requires another account observation.
- The risk state binds to the verified Demo account identity using a hash;
  another account cannot inherit or reset it. Legacy state binds on its first
  accepted observation after migration; this does not prove historical identity.
- Remaining daily, weekly, peak and per-trade cash headroom limits new planned
  risk. Reservations and risk changes share a transaction lock across leases;
  the reservation rejects paused, stale, unbound or insufficient risk state.
  The runner refreshes account state before reservation. Existing global
  unresolved-attempt protection remains in place.
- At minimum volume, the executor retains the intended technical stop and
  refuses an unaffordable trade. The strategy documents now expressly remove
  stop tightening solely to fit the budget. This is the scoped W1.4 correction,
  not a new strategy or a change to Option B amounts.
- Fixed read-only task diagnostics expose task state, process identities,
  power settings and recent Python application events. The supervisor now
  retains bounded, redacted crash frames and retries a transient Windows
  status-file replacement failure at most three times. These changes are
  not deployed and do not establish the cause of the observed crashes.

### Validation and retained evidence

`scripts/verify_project.sh` passed, including **294 tests**, configuration,
registry, Triad-policy, secret and adapter checks. **23 tests use an actual
isolated PostgreSQL 16 instance** on localhost port 55481 and the dedicated
`forex_w1_test` database. Reservation refusal tests isolate proposal parsing;
they do not claim a complete broker execution or a concurrent end-to-end
order-race demonstration.

The original committed risk function reproduced the defect against PostgreSQL:
following a simultaneous breach, recovery and next-day rollover permitted entry.
The corrected function retains weekly and peak pauses. A separate actual restart
of the isolated database preserved its state exactly; a subsequent recovered
next-day observation still refused entry. All equity paths here are synthetic.

Evidence index: `runs/evidence/w1-continuation-20260910/index.json`.
Remote raw observations and local engineering outputs occupy separate
subdirectories. The index binds source hashes and implementation revision.
`runs/verification/w1-continuation-20260910/artifact-check.json` separately checks
artifact hashes, restart equality, retained manual latches, broker flatness and
operating pause preservation. This is a separate verifier process, not a Triad
recommendation, external witness or M20 proof bundle.

### Current T480 observations

- The listener was found stopped, task result **1**, and was recovered once
  under the existing maintenance hold. It subsequently exited again. The
  final status is **STALE**, old release `c523b1c904b8aa51`, last heartbeat
  `2026-09-09T23:44:21.611405Z`. Do not describe it as continuously running.
- Task diagnostics show S4U, no Forex Python process, and both battery-start
  prohibition and stop-on-battery enabled. No matching Python Application
  Error/WER event was returned. These settings are observations, not proof
  that battery state caused either exit. Historical Python exception frames
  were not retained; the new crash recorder addresses that diagnostic gap.
- A fresh read-only broker probe observed `GOMarketsMU-Demo`, AUD balance and
  equity **100,994.79**, and **zero open positions**. This is flatness at that
  capture, not a continuing guarantee or a reinterpretation of the old
  monitor-job ticket.
- The operating database still has `EXTERNAL_CASH_FLOW` paused, baseline
  **100,995.51**, expected balance **100,995.32**, unchanged anchors and its
  existing resume record. The AUD 0.53 difference from the new balance needs
  broker-ledger attribution. The operator's historical AUD -0.29 confirmation
  cannot be extended to this difference. No pause was cleared.
- The shared backup check returned a valid **PostgreSQL-logical** manifest
  captured on **2026-09-07 19:45 NZST**. It is older than the shared 24-hour RPO.
  The available shared handover reports isolated synthetic restore success
  but does not establish a verified retained full-lab T16 bundle. A current
  backup/restore evidence pointer was requested from the operator.

### Remaining criteria and resumption sequence

| Area | Status and exact remaining work |
| --- | --- |
| W1.1 / R4 | Local configuration fingerprint and migration artifacts updated. Obtain current affected-data backup and isolated-restore evidence; retain fresh broker/ledger/risk baseline, then stage migration 022 and the compatible reviewed release under the entry hold. Verify source hashes, task configuration and unchanged anchors before considering release. |
| W1.2 | Prior lifecycle repairs retained. Capture a genuine eligible Demo open-to-close lifecycle on the final release and independently reconcile protection, ownership and terminal/broker results. No manufactured signal or forced loss. |
| W1.3 | Broker charge and reconciliation proof remains incomplete. Qualify actual commission/financing/fee behavior and reconcile the current balance difference; preserve the cash-flow pause until its exact attribution and approved review are satisfied. |
| W1.4 | Independent latches and reservation headroom pass local integration checks. Planned-loss allowance currently includes stop distance and the existing spread-based slippage estimate; it still does **not** establish applicable commission, financing or other charges. Complete this qualification/integration, reservation concurrency proof and review of unknown-account manual-pause persistence before enabling entries. Then prove a real protected listener restart and the approved AUD 0.01 refusal drill, restoring Option B immediately. |
| R1 / R5 | Recurring task exit remains unresolved. Deploy the redacted crash recorder when deployment prerequisites permit, capture the actual failing frames, fix the supported cause, and demonstrate recovery. Do not infer battery causation or change startup principals blindly. Detached-T16 and separate flat/no-logon reboot windows remain unproven. |
| R6 / R7 | Local crash retention is implemented; bounded incident delivery/recovery proof and current independent review gates remain pending. Rebuild affected proof against the final contract, revision, configuration and broker evidence before claiming completion. |

The maintenance hold and independent risk pause must remain. Database migration,
reboot and other disruptive work remain blocked on current recovery evidence.
Do not close Wave 1 or M20 from this code commit or the passing local checks.
