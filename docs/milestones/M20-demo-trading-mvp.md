# M20 — capped automated Demo trading MVP

## Purpose

M20 replaces the deferred Ollama evaluation closeout with the MVP operational
loop: fresh `GOMarketsMU-Demo` EUR/USD data, a recorded M1/M5 assessment, a
bounded Demo-session order, and durable reconciliation data for later
backtesting. It never permits `GOMarketsMU-Live`.

## Bounded session contract

The governed configuration permits only a session that is all of the
following:

- exactly `GOMarketsMU-Demo` and `EURUSD`;
- no more than ten trades in a maximum sixty-minute window;
- one open position at a time;
- no more than USD 100 notional per trade and USD 1,000 cumulative notional;
- a persisted, unexpired proposal and unique idempotency key before execution.

The broker credential is never tracked or retained in evidence. The only
tracked reference is the name of the required machine-local environment
variable.

## Data and decision record

Every proposal stores a hash-addressed snapshot of the current bid, ask,
spread, and closed M1/M5 candles. The deterministic MVP assessment returns
`BUY`, `SELL`, or `NO_TRADE`: agreement between closed M1 and M5 momentum is
actionable; a conflict is a recorded abstention. The first goal is an
inspectable operational loop, not a profitability claim.

## PostgreSQL audit boundary

Migration `006_m20_demo_trading_audit.sql` introduces separate append-only
Demo-session, proposal, decision-snapshot, execution-attempt, position-event,
and outcome tables. It does not relax M19's historical, research-only lineage
tables. The fixed runner now writes and reads back a `NO_TRADE` proposal
before emitting its success marker. A future fixed MT5 executor must write the
proposal before invoking the broker and reconcile each broker response into
these audit records; it is intentionally not implied by the `NO_TRADE` path.

## Completion evidence

M20 is not complete from this document or unit tests. Completion requires the
fixed Demo adapter to prove fresh server identity and data, bounded execution
or `NO_TRADE`, persisted audit rows, reconciliation, an independent verifier,
and the current Triad-plus-domain recommendation required by `AGENTS.md`.
