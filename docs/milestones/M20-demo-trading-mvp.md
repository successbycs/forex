# M20 — capped automated Demo trading MVP

## Purpose

M20 replaces the deferred Ollama evaluation closeout with the MVP operational
loop: fresh `GOMarketsMU-Demo` EUR/USD data, an adaptive M1-only live-listener assessment, a
continuous cap-constrained Demo order, and durable reconciliation data for later
backtesting. It never permits `GOMarketsMU-Live`.

## Bounded session contract

The governed configuration permits only a session that is all of the
following:

- exactly `GOMarketsMU-Demo` and `EURUSD`;
- continuous Demo-only authority (`maximum_duration_minutes: 0`) with a new
  immutable session record for each activation; caps remain per recorded session;
- one open position at a time;
- no more than USD 10,000 notional per trade and USD 100,000 cumulative notional;
- a calculated protective stop whose theoretical loss is no more than AUD 100;
- a persisted, unexpired proposal and unique idempotency key before execution.

The broker credential is never tracked or retained in evidence. The only
tracked reference is the name of the required machine-local environment
variable.

## Data and decision record

The listener keeps its incoming MT5 tick observations only in memory and runs
an assessment every five seconds using a fresh tick and closed M1 candles.
Every resulting proposal stores one hash-addressed decision snapshot of the
current bid, ask, spread, and closed M1 candles; it deliberately retains no
listener stream or M5 candles. The deterministic MVP assessment returns
`BUY`, `SELL`, or `NO_TRADE` from closed M1 momentum. It also evaluates four
shadow strategies—compression breakout, trend pullback, range reversion, and
session breakout—without granting them order authority. The first goal is an
inspectable operational loop, not a profitability claim.

## PostgreSQL audit boundary

Migration `006_m20_demo_trading_audit.sql` introduces separate append-only
Demo-session, proposal, decision-snapshot, execution-attempt, position-event,
and outcome tables. It does not relax M19's historical, research-only lineage
tables. The fixed runner persists a proposal before invoking the broker. An
accepted Demo order remains open with broker-side SL/TP and durable position
state. The fixed monitor may move its stop to breakeven at +1R, close after two
opposite completed M1 candles or ten minutes, and reconcile a broker-side
SL/TP exit from deal history. Only then is a `CLOSED` lifecycle event plus
immutable P&L/cost outcome written. A rejected order is retained as its
terminal broker result.

## Completion evidence

M20 is not complete from this document or unit tests. Completion requires the
fixed Demo adapter to prove fresh server identity and data, bounded execution
or `NO_TRADE`, persisted audit rows, reconciliation, an independent verifier,
and the current Triad-plus-domain recommendation required by `AGENTS.md`.

## Operator dashboard

On the T16 machine running VS Code, use the read-only live terminal view:

```bash
python3 scripts/m20_listener_dashboard.py
```

It refreshes the T480 listener heartbeat, latest assessment, order outcome,
and compact candle-check metrics. Listener heartbeat and next-assessment times
are displayed in both UTC and New Zealand time (`DD/MM/YY HH:MM:SS NZST`).
Press `Ctrl+C` to exit.

Each assessment also lists all five documented M1 strategies. Momentum
breakout remains the sole active, order-eligible strategy. Compression
breakout, trend pullback, range reversion, and session breakout are read-only
shadow comparisons: they can report `BUY`, `SELL`, or `NO_TRADE` but cannot
submit an order.

If the T480 status request stalls, the dashboard times it out after eight
seconds and continues refreshing with an `UNAVAILABLE` state rather than
freezing the terminal view.

## Current M20 work packages

- **M20.7 — Permanent M1 listener and operator observability:** documents and
  verifies the T480 Scheduled Task, its five-second redacted status, and the
  read-only T16 dashboard. It does not add a trading control surface.
- **M20.8 — MT5 rejection diagnostics and execution-path remediation:** records
  broker return codes against immutable execution attempts, reconciles every
  attempt, and corrects any confirmed Demo execution-path fault before fresh
  evidence is captured.
- **M20.9 — Atomic T480 listener deployment:** stages a fixed hash-checked
  ProgramData release, prepares non-secret local state, atomically switches the
  Scheduled Task with rollback, and keeps lease, status, recovery, runner, and
  dashboard paths aligned.

All M20 packages remain Demo-only. They do not claim M20 completion or
authorize Live trading.
