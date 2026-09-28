# Demo strategy and edge-case evaluation — sub-ExecPlan

This is a child of `demo-mvp-console-execplan.md`. It is a future read-only
evaluation plan. It does not authorise strategy changes, optimisation, risk
changes, Demo-entry changes, or Live trading.

## Purpose

After the Demo console can prove exactly what the system did and what it made
or lost after actual broker costs, evaluate the fixed strategies and adverse
conditions using clean, versioned Demo evidence. The outcome is a recommendation
about further Demo research, not a claim of edge and not a Live promotion.

## Preconditions

The console's natural lifecycle proof has passed; the evaluation window,
strategy versions and data-exclusion rules are frozen before analysis; all
included records are system-owned and broker-matched; and no concurrent
strategy tuning changes the sample. A missing or changed prerequisite invalidates
the evaluation rather than being filled with estimates.

## Evaluation dataset and questions

For each strategy/version, retain selected signals, unselected signals, rejected
attempts, opened trades, matched closes, actual costs, net P&L, holding time,
slippage where broker facts support it, and no-trade/gate reasons. Segment only
by predeclared market conditions and sample dates. Report sample sizes,
drawdown, concentration, rejected/missing records and uncertainty; do not set a
profit threshold after seeing results.

Exercise and document the relevant safety/edge evidence: stale or missing price,
wide spread, invalid candle, conflicting strategy signals, existing position,
risk pause, broker rejection, partial/unresolved execution, restart/disconnect,
duplicate-candle prevention, protection/stop-target outcome, weekend/gap and
reconciliation delay. Tests and observed incidents must be labelled separately.

## Decision gates

At the end, an independent review can recommend one of: retain current Demo
collection; investigate a specific failure; design a new controlled Demo
experiment; or conclude evidence is insufficient. A later Live-readiness plan
would separately require explicit human authority, independent risk review,
out-of-sample evidence, actual-cost and adverse-condition analysis, release
readiness, and a new account/control design. It is never unlocked by dashboard
completion or aggregate profit.

## Demo trading continuity

`CONTINUE`: this package is observation and analysis only. It does not interrupt
or retune the healthy Demo listener. A data-quality issue stops only the
evaluation until resolved.

## Design progress and decisions

- [x] Separated Demo MVP measurement from strategy-edge and Live-readiness
  decisions.
- [x] Defined sample integrity, adverse-condition and review requirements.
- [ ] Start only after the MVP console's natural lifecycle proof.
