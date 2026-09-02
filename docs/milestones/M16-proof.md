# M16 — historical and ML walk-forward evaluation

M16 evaluates the existing `eurusd-linear-baseline.v1` only on closed,
retained EUR/USD H1 Demo-only bars. It uses three fixed chronological holdout
windows. For every window the M15 centroid model is trained once on bars before
the first test session, then frozen while testing complete UTC sessions from
08:00 to the mandatory 20:00 exit. The comparisons are the M15 baseline, a
deterministic two-bar-return direction baseline, and `NO_CHANGE` (no action).
Rows are never shuffled; a test window cannot fit on itself or later data.

The reported cost-sensitive number subtracts a fixed 2 basis-points-per-side
sensitivity from each non-`NO_TRADE` result. It is not a captured broker spread,
profitability claim, forecast, sizing rule, order signal, or trading edge.
Observed M1 spread/cost capture is intentionally deferred to a later,
separately-proven capability.

## Context coverage is not fabricated

The probe accounts separately for macro, calendar and GDELT sentiment rows
available at each historical cutoff. They are not model features in M16. If a
source has no aligned retained historical rows, its result is
`EVALUATED_AS_UNAVAILABLE`; if it has rows, its result is
`EXPERIMENTAL_CONTEXT_COVERAGE_ONLY`. This is a coverage result, not evidence
that the context predicts EUR/USD. It avoids treating sparse or later context
as if it had influenced the historical price decision.

The fixed T480 probe reads PostgreSQL through the Forex adapter, emits a JSON
result containing the model/source versions, window boundaries, coverage,
feature-separation descriptions and all baseline metrics, then retains it in
the M16 evidence bundle. It cannot access MT5, place orders, access a live
server, or alter database records.

## Current proof limitation — 2026-09-02

The retained M2 snapshot is a single historical MT5 observation captured on
2026-08-29. Its 720 individual bars contain their UTC opening time and OHLCV,
but not a per-bar source-availability timestamp. The current data contract
therefore assigns each bar the availability of the retained M1 observation.

M16 now enforces this rule at every decision and exit timestamp. On the real
T480 snapshot it correctly finds zero point-in-time-valid 08:00-to-20:00 UTC
sessions; it must not treat the earlier retrospective result as a valid
no-lookahead walk-forward evaluation.

M16 can resume only with one of these explicit, reviewable inputs:

1. a new price dataset that records each bar's source availability at or before
   its decision time; or
2. an operator-approved retrospective policy that defines H1 bar availability
   at bar close, labels the evidence as an assumption rather than observation,
   and is reflected in the milestone contract and evidence limitations.

Neither option authorises live trading, an order surface, or use of
`GOMarketsMU-Live`.
