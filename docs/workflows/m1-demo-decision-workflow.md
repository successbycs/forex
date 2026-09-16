# M1 Demo decision workflow

This document is the operational reference for the EUR/USD M1 Demo decision
loop. It describes what the deployed listener is intended to do, what it
records, and which parts are active today. It is not a strategy specification,
milestone contract, or trading-performance claim.

The only execution target is `GOMarketsMU-Demo` for `EURUSD`. A `NO_TRADE`
decision is a normal successful outcome. Nothing in this workflow authorizes
Live trading.

## Current operational sequence

The listener runs every five seconds but acts only on a fresh, completed M1
candle. The fixed M20 runner is the executable definition in
`t480/m20_demo_trading_session.py`; `t480/m20_demo_listener_service.py`
starts it and retains the user-visible status.

```text
New completed M1 candle available
  -> validate EURUSD quote, completed bars, freshness, and Demo account identity
  -> confirm lease, position, duplicate, loss, exposure, and broker safety gates
  -> evaluate the five fixed M1 strategies on the same immutable snapshot
  -> select at most one executable M1 owner by deterministic regime precedence
  -> calculate broker-valid entry, stop, target, capped size, and cost coverage
  -> apply the final risk, financing, and execution gates
  -> persist exactly one BUY, SELL, or NO_TRADE proposal and its audit record
  -> submit only an actionable persisted proposal through the fixed Demo path
  -> monitor any accepted position through close and reconcile broker history
  -> journal the decision, execution attempt or refusal, and outcome
```

The resulting records contain the snapshot, strategy comparison, selected
owner, proposal, risk results, broker attempt, lifecycle, and reconciliation.
They are available through the read-only dashboard and retained audit/evidence
paths.

The proposed target ordering is visualised in the
[M1 hybrid decision flow](m1-hybrid-decision-flow.md). Its intended end state,
current gaps, and evidence-led promotion rules are in the
[M1 decision-workflow end-state review](../reviews/m1-decision-workflow-end-state.md).

## Current limits and explicit non-gates

Economic-event context has a defined interface, but the shipped M1 policy is
currently annotation-only. It does not yet block a new entry. An enabled event
window must be introduced through a governed policy and deployed context
package; missing or invalid enabled context must fail closed.

M5/H1 context is currently recorded after the M1 decision as shadow context.
It is informative and cannot create, reject, or take ownership of an M1
trade. It must not be described as an active higher-timeframe entry gate until
the runtime contract, tests, and configuration explicitly make it one.

The listener's configured financing window, quote freshness, account state,
broker identity, cost coverage, position limits, and risk limits are active
entry gates. If any required fact is stale, missing, invalid, or unsafe, the
outcome is `NO_TRADE` or a fail-closed refusal.

## Timeframe expansion

M1 is the only operational decision timeframe today. M15 and other timeframes
will be added as separate, versioned workflow sections rather than silently
changing M1 behavior. Each new timeframe must state:

- its completed-candle trigger and data-freshness rules;
- whether it is an execution owner, a veto, or context only;
- its strategy, stop/target, sizing, and risk rules;
- its interaction with existing M1 positions and exposure limits; and
- its distinct journal and reconciliation evidence.

A future M15 workflow may consume M1 or higher-timeframe data only after those
bars are complete and available at the M15 decision time. It cannot gain order
authority merely by being added to this document. Its runtime implementation,
governed configuration, tests, and milestone scope must make that authority
explicit.

## Source of truth

This document describes the operational flow. The sources of truth for its
current enforcement are:

- `t480/m20_demo_trading_session.py` for M1 assessment, risk, execution,
  monitoring, and reconciliation;
- `t480/m20_demo_listener_service.py` for the scheduled listener and status;
- `config/risk.yaml`, `config/execution.yaml`, and `config/agent.yaml` for
  governed configuration; and
- `milestone_registry.json` for the active milestone's proof requirements.

If the document and executable runtime disagree, treat the runtime and its
governed configuration as current behaviour, repair this document, and record
the discrepancy in the relevant ExecPlan.
