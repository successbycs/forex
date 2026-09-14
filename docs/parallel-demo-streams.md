# Parallel Forex Demo streams

Delivery direction recorded from Chris's request, 2026-09-12: finish the
existing M1 Demo operation, then add a longer-hold stream alongside it. Longer
holds do not replace M1. Both remain in this repository; neither may use
GOMarketsMU-Live. This document does not declare a completed milestone or
activate a second executor.

## Two independently observable streams

| Concern | M1 stream | Longer-hold stream |
| --- | --- | --- |
| Initial policy | Preserve the existing versioned M1 composite | One explicitly specified slower trend-following policy |
| Holding rules | Existing owner-specific minute-scale exits | Separate entry, exit, overnight and weekend rules; no inherited M1 timeout |
| Economic data | Initially annotate decisions and outcomes | Reuse the same event module, with context covering the intended hold |
| Accounting | Its own decisions, attempts, positions and net results | Separate decisions, attempts, positions and net results, including financing |
| Development dependency | Complete outstanding execution/recovery work | Reuse stable components without making M1 depend on this stream |
| Economic qualification | Observe Demo performance | Observe Demo performance; do not require proof of profitability before a bounded Demo trial |

Use published research and informed judgment to choose a frozen initial rule.
Historical replay is useful for finding implementation errors and checking
available inputs; reproducing academic results is not a prerequisite to a
Demo hypothesis trial. A profitable backtest is not an entry requirement.
Formal research/business conclusions still require appropriate evidence.

## Deployment separation

The present executor is not multi-stream. It uses one executor magic ID, a
single monitor-job path and a lease with maximum_open_positions=1. It checks
for existing positions before a new entry. Launching another copy does not
create independent ownership and could overwrite state or block M1.

Recommended initial deployment: a separate explicitly configured Demo account
and terminal instance for the longer-hold stream, with separate runtime state,
leases, account-scoped audit/idempotency records and ownership. This avoids
changing M1's single-position mandate just to introduce the second strategy.
The second account/terminal has not been provisioned or selected. Do not
silently select another saved login. Shared infrastructure and data may be
reused; account identity and order routing must remain explicit.

If both streams instead share one Demo account, first implement atomic
account-wide reservations, per-stream budgets, unique ownership identifiers
and monitor records. Closing or modifying a position must resolve its exact
owner and ticket. Verify hedging/netting behavior; opposite signals must not
silently offset or close another stream's position. Keep gross exposure,
margin and total risk visible even if net EUR/USD exposure is small.

Either deployment needs an explicit total experiment budget, not an automatic
doubling of allowed exposure. Separate Demo accounts should also have combined
reporting of exposure and outcomes. A shared-account two-position allowance
would change the present cap and requires a recorded mandate change before
activation. No caps are changed by this document.

## Canonical wave ownership

The [shared wave guide](prompts/demo-income-waves.md) and
[Wave 3](prompts/demo-income-wave-3.md), including its identical
[goal alias](prompts/research-trading-wave-goal.md), now incorporate this
direction as of 2026-09-12. Wave 1 finishes M1 reliability, Wave 2 supplies
shared data/cost/event components, and Wave 3 implements and observes H_SLOW
alongside M1. Wave 4 remains the separate funded-readiness decision.

## Delivery sequence

1. Finish M1 execution reliability and reconciliation without changing its
   strategy for the longer-hold work. Complete the active recovery milestone
   and its prerequisites honestly; retain market-dependent proof as pending.
2. Define one complete longer-hold strategy and its Demo mandate. Entry, exit,
   sizing, warm-up, financing, gaps and holding permissions must be executable
   rules, not a strategy label. The Wave 3 shadow-first planning prerequisite
   has been removed. Exact account/holding contract and configuration changes
   still need to be recorded before dependent implementation or activation.
3. Add isolated configuration, state and trade ownership. Reuse broker/data
   components where safe. Test direction, sizing, stops, duplicate prevention,
   restart ownership and reconciliation. These are correctness checks, not
   profitability hurdles.
4. Enable the longer-hold Demo stream once those operational checks pass and
   its account/mandate are configured. M1 continues under its own rules.
5. Observe both, reporting net results, financing, drawdown, exposure, rejects
   and operational incidents separately. Review on a fixed schedule and
   version each change; do not retune automatically after losses.

No second strategy milestone is started by this planning record. The existing
active milestone remains M29; the market-proof pause is not a profitability
pause. Provisioning/routing a second account is a separate deployment step.

## Observed status and first repair

The fixed status operation returned a fresh M1 listener heartbeat at
2026-09-11T22:58:39Z, state WAITING_FOR_FRESH_MT5_QUOTE, on the existing Demo
release. It was not restarted. This is a point-in-time status observation,
not proof of uninterrupted availability, a flat account or milestone completion.
The retained protection record was LAST_KNOWN_UNVERIFIED; it must not be
reported as a currently open or currently protected position.

The read-only M27 tick collector previously selected UTC+2 or UTC+3 by which
made a quote appear freshest. The local repair uses the existing governed
offset from config/mt5.yaml and rejects stale/future or invalid quotes. Tests
include the regression where a 3,602-second-old quote was previously made to
look two seconds old. The configured offset still needs independent broker
confirmation; freshness cannot be used to infer it.

A fixed read-only broker probe at 2026-09-11T23:00:22Z returned the Demo quote
with approximately 7,224 seconds of age under the governed UTC+3 offset and
was rejected. No order or listener mutation was performed. The adapter's
ignored execution log retains the operation response; this document is only
a summary, not a substitute for raw evidence.

M1 runtime strategy code is unchanged. M27/M28 remain NEEDS_REVALIDATION;
M29 remains BLOCKED with recovery-proof gaps unresolved; M20 remains an
unproven HUMAN_REVALIDATION_EXCEPTION. The longer-hold stream is not deployed.
