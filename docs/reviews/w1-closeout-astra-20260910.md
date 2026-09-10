# Astra Wave 1 closeout review — 10 September 2026

Recorded from the separate read-only Astra reviewer response. This is an affected-area review, not a bound Triad recommendation or milestone closure.

## Accepted observations

Retained `runs/evidence/M20/w1-automated-restart-20260910/raw/` shows protected ticket 42234057 / attempt 6170b7e5-bf55-5363-ab5f-160f6201fdf1 recovered after listener replacement. Entry 1.16389, SL 1.16355 and TP 1.16445 remain consistent with broker history.

`runs/evidence/M20/w1-closeout-20260910T084421Z/raw/` records opening deal 34871557 and closing deal 34872579: 0.01 EURUSD BUY 1.16389, broker stop-loss close 1.16355, AUD -0.47 net, zero commission/fee/swap. Original lease and proposal/attempt persisted; OPENED → CLOSED / MATCHED. Broker close 08:43:50 UTC and database observation 08:43:51 UTC are distinct.

Six closed outcomes total AUD -1.98, exactly bridging 100994.79 to 100992.81 in broker and expected balances. Baseline/peak/weekly anchors remain 100995.51; daily 100994.79. Separate offline verifier: `runs/verification/M20/w1-closeout-20260910/verify_retained.py` and `result.json`.

The account is not flat at this capture: subsequent ordinary SELL 42235606 has an OPENED record. Maintenance hold was subsequently enabled. Protected listener recovery does not itself prove automatic-trigger execution or a failed broker-read drill.

## Findings requiring correction

1. Restart-drill marker parse/write failure can terminate protective monitoring and exhaust task retries. Drill bookkeeping faults must prevent entry/drill continuation while preserving monitoring and owner exits, retaining an incident.
2. Recovery matches ticket only and can accept a different attempt. Require exact attempt and ticket, with negative behavioural tests.
3. The older deployed AUD 0.01 refusal verifier passes and establishes genuine metadata, calculation refusal and exact original-lease restoration. However, its `_risk_levels` helper is called only by that drill; ordinary trading uses `_strategy_trade_plan` / `_planned_stop_loss` / reservation controls. It cannot prove the actual production risk path. Correct the shared calculation without forced signals/orders and retain fresh deployed proof.

## Remaining scope

Partial-fill proof is conditional on observation; nonzero charges are included where available. Overnight/triple/holiday qualification remains unobserved and outside the temporary approved intraday mandate, which expires 17 September. None requires manufactured trades or costs.

W1.R still records detached-T16/no-logon and incident-delivery proof as unproven. These need an explicit applicability/dependency disposition; listener restart is not host-reboot proof. Proposed shared-platform scope alone does not authorise a reboot.

Final acceptance remains pending corrected implementation review, actual applicable refusal proof, final release/configuration/effective-limit binding, applicable W1.R proof/disposition and required independent recommendation. Wave 1 alone cannot close M20.

## Runtime restart failure found during this review

At 08:51:09 UTC, `raw/held-diagnostics-baseline.json` in the closeout bundle observed task `Ready`, result 1 and no listener processes despite three configured one-minute restart retries. The last acceptance was SELL 42235606 at 08:44:07. This disproves automatic restart availability for the captured incident; the trigger cause is supported by sequence but the old marker was not exposed by that diagnostic.

The authorised fixed listener recovery was requested at 08:51:26–28. Fresh 08:52:43 heartbeat then showed `MAINTENANCE_HOLD` / monitor `IDLE`; broker account was AVAILABLE/flat at AUD 100992.55. Separate post-recovery unresolved query is empty. The hold and Option B were not cleared.

Astra recommends a synchronous fixed replacement worker after the original trading loop unwinds, with the original task process waiting as an inert supervisor. Persist the request and process identities; require exact ticket/attempt recovery. Launch/child failure must latch a drill fault and return to monitoring with entries blocked. Do not rely on Windows task retries or a detached replacement. This is worker restart with parent supervision retained, not a host-reboot proof.

## Refusal repair review

The separate Astra reviewer accepted the corrected shared `_planned_stop_loss` / technical-stop normalization probe, finite input validation, canonical broker-offset UTC conversion, post-read freshness bound and retained quote/capture timestamps. It also accepted forwarding only the tick offset from the existing revision/hash-bound T480 configuration. Focused actual-behaviour tests passed, including stale/future/nonfinite inputs and no-order assertions. This accepts source/tests for deployment; fresh broker-input refusal and exact original-lease restoration remain separate proof. The result is a lower-bound risk refusal, not a reservation, strategy-selection or overnight-cost demonstration.

## Final affected-area source disposition

**READY_FOR_HELD_DEPLOYMENT** from the separate read-only Astra review. All 26 listener tests and targeted status check pass. Reviewed behavior: each fault-blocked loop still runs bounded monitoring; exact attempt/ticket matching; one fixed replacement worker after the old loop unwinds; inert waiting parent; spawn/nonzero failure returns to monitoring-only; wait errors cannot start a competing worker. Legacy requests remain explicitly unverified and cannot rearm. The existing stop operation terminates matching payload processes. No further source blocker identified. Fresh deployed hashes/configuration/limits, held recovery and actual refusal/restoration remain required. Actual automatic child handoff on Windows is still unobserved and is not claimed by these tests.
