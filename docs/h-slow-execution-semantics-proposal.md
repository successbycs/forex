# H_SLOW v1 execution-semantics proposal

Status: **DRAFT_NOT_ACTIVE**. This is the smallest complete operating proposal
needed to build the fixed H_SLOW Demo adapter. It does not select an account,
write a local binding, submit/modify/close an order, or change
`execution_authority`.

## Fixed scope and caps already approved

- Demo EUR/USD only; H_SLOW remains separate from M1.
- One H_SLOW position maximum, 0.01 lots maximum.
- AUD 1,000 maximum loss, USD 10,000 maximum notional and USD 100,000 lease
  ceilings. These are ceilings, never targets.
- The trial begins only after activation checks pass and continues until Chris
  revokes it. There is no arbitrary end date.

## Proposed v1 operating rules for approval

| Concern | Proposed deterministic rule |
| --- | --- |
| Decision clock | Evaluate once on the first UTC day of a month, only after the prior month has closed and the 12-month input is point-in-time qualified. |
| Flat account | A qualified `BUY` or `SELL` target may create one fixed-size entry only after fresh preflight, broker protection, cost, margin, lease and durable-intent checks pass. `NO_TRADE` creates no order. |
| Existing same-side position | Hold it. Do not add, resize or duplicate it. |
| Opposite target | Submit a close request for the owned H_SLOW ticket first. Do not open the opposite side in that monthly window. Reconcile the close before a later monthly entry can be considered. |
| Initial protection | Attach a broker-side ATR(20) × 3 stop at entry. Refuse the entry if the stop cannot be validly placed and verified. Never widen or remove the stop. |
| Profit management | No take-profit and no trailing stop in v1. Exit occurs only through the protective stop, a later opposite monthly target, or a fail-safe manual/revocation procedure. |
| Holding | Hold continuously while the owned position remains reconciled and its broker-side stop is verified. An unreconciled/unknown position blocks new entries while preservation and reconciliation continue. |
| Overnight / weekend | Permitted only when fresh broker financing/rollover terms, relevant conversion quote and position protection have been observed; otherwise block new entry, not existing-position protection. Verify and retain a pre/post-rollover and pre/post-weekend reconciliation observation. |
| Costs | Use observed spread, commission, financing, conversion and a labelled adverse-cost allowance. Never treat unknown cost as zero; unknown required terms block new entry. |
| Events | Keep verified economic events as point-in-time annotation in v1. They do not choose direction or manage an existing position. |
| Failure / revocation | Disable new entries; retain/reconcile the owned position and keep its broker-side protection. Only Chris's recorded resume authority may lift the new-entry pause. |

## Why this is the shortest useful rule set

It makes the monthly trend policy executable without adding discretionary
management, same-window reversal, automatic loss recovery or edge-based risk
scaling. The adapter can therefore enforce one narrow lifecycle: qualify,
protect, retain, reconcile, then either hold or close-first on the next
monthly signal.

## Approval required

Chris must explicitly approve or amend the proposed operating rules before
they are bound into an execution-capable adapter. Approval does not bypass the
separate dedicated-terminal binding, fresh broker observations, durable store
deployment or formal evidence requirements.
