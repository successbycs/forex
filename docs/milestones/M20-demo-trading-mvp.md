# M20 — bounded automated Demo trading MVP

## Purpose

M20 replaces the deferred Ollama evaluation closeout with the MVP operational
loop: fresh `GOMarketsMU-Demo` EUR/USD data, an adaptive M1-only live-listener assessment, a
continuous cap-constrained Demo order, and durable reconciliation data for later
backtesting. It never permits `GOMarketsMU-Live`.

The consolidated regime-classification, selected-strategy, and strategy-owner
procedure is [M20-market-regime-strategy-operating-procedure.md](M20-market-regime-strategy-operating-procedure.md).

## Bounded session contract

The governed configuration permits only a session that is all of the
following:

- exactly `GOMarketsMU-Demo` and `EURUSD`;
- continuous Demo-only authority (`maximum_duration_minutes: 0`) with a new
  immutable session record for each activation and no development-phase total
  trade-count ceiling;
- one open position at a time;
- no more than USD 10,000 notional per trade and USD 100,000 cumulative notional;
- a calculated protective stop whose theoretical loss is no more than AUD 100;
- the persistent Option B risk guard: lesser of AUD 100 and 0.10% of equity per proposed loss, 0.50% daily loss pause, 1.00% weekly loss pause, 2.00% peak adjusted-equity drawdown pause, and fail-closed cash-flow reconciliation;
- a persisted, unexpired proposal and unique idempotency key before execution.

The broker credential is never tracked or retained in evidence. The only
tracked reference is the name of the required machine-local environment
variable.

## Data and decision record

The listener keeps its incoming MT5 tick observations only in memory and runs
an assessment every five seconds using a fresh tick and closed M1 candles.
Every resulting proposal stores one hash-addressed decision snapshot of the
current bid, ask, spread, and closed M1 candles; it deliberately retains no
listener stream or M5 candles. The deterministic MVP assessment evaluates all
five fixed M1 strategies. Regime precedence selects at most one strategy as
the trade owner; its own entry, protective stop, 1.5R target and monitoring
contract govern the order. The first goal is an inspectable operational loop,
not a profitability claim.

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
fixed Demo adapter to prove fresh server identity and data, persisted audit
rows, one accepted Demo order with a broker-matched `OPENED` to `CLOSED`
lifecycle and broker-derived AUD P&L, an independent verifier, and the current
Triad-plus-domain recommendation required by `AGENTS.md`. `NO_TRADE` is a
truthful assessment outcome, but cannot alone close M20.

The proof verifier requires the closed trade's own proposal revision and
configuration to match the manifest; sharing an old continuous lease is not
sufficient. The fixed monitor retains the exact position-specific broker deal
rows used for cost calculation in its immutable CLOSED event. The offline
verifier recomputes matched volume, entry/exit prices, commission, fee, swap,
and net AUD P&L from those rows. It also checks fresh listener status and
deployment diagnostics against the current four payload hashes and lease caps.
Older outcomes without retained broker rows remain historical ledger records,
not substitute proof for a new release. Capture refuses an existing bundle
directory, including an incomplete or failed prior capture.

## Operator dashboard

On the T16 machine running VS Code, use the read-only live terminal view:

```bash
python3 scripts/m20_listener_dashboard.py
```

It refreshes the T480 listener heartbeat, latest assessment, order outcome,
and compact candle-check metrics. Listener heartbeat and next-assessment times
are displayed in both UTC and New Zealand time (`DD/MM/YY HH:MM:SS NZST`).
Press `Ctrl+C` to exit.

Each assessment lists all five documented M1 strategies. Each can produce a
tradable fixed plan, but deterministic regime precedence grants order
authority to exactly one and the one-position limit prevents duplicate EURUSD
exposure. The selected strategy owns its SL, TP and exit decision.

If the T480 status request stalls, the dashboard times it out after eight
seconds and continues refreshing with an `UNAVAILABLE` state rather than
freezing the terminal view.

For trade-focused monitoring, use the separate read-only ledger dashboard:

```bash
python3 scripts/m20_trade_ledger_dashboard.py
```

It lists opened Demo trades for the current Auckland calendar day, newest
first, with proposed and broker-filled entry, SL, TP, monitoring/reconciliation
state, sold time and dedicated exit price when available, and realised AUD P&L
only when MT5 has been reconciled. Rejected attempts are counted separately;
use `--show-rejections` to inspect them without confusing them with trades.
`Pending` means the system does not yet have a verifiable P&L outcome.

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
- **M20.10 — Trade lifecycle and P&L dashboard:** provides a separate
  read-only terminal view of the immutable PostgreSQL trade ledger, clearly
  distinguishing monitoring, sold/verified, rejected, and unreconciled states.
- **M20.11 — Controlled five-strategy Demo execution trial:** reuses the
  existing fixed listener, release path, PostgreSQL audit, and read-only
  dashboards so deterministic regime precedence may grant exactly one of the
  five M1 strategies execution authority. It retains one EURUSD position,
  Demo-only caps and protective controls while collecting strategy-owned
  broker-reconciled results during an operator-owned, initially three-to-four-day
  observation window. Its MVP scope and exclusions are
  recorded in [M20.11-five-strategy-demo-trial.md](M20.11-five-strategy-demo-trial.md).
- **M20.12 — Multi-timeframe context trial for M1 Demo execution:** is
  implemented locally and staged, but is not deployed to T480. M1 remains the
  sole execution and ownership timeframe; M5/H1 records are read-only and
  cannot alter entry, exit, or holding time in v1. H4/D1/W1 are deferred from
  the fast path. Its research basis, independent trader-domain review, Demo to
  Live roadmap, and operator feedback questions are in
  [M20.12-multi-timeframe-context-trial.md](M20.12-multi-timeframe-context-trial.md).

All M20 packages remain Demo-only. They do not claim M20 completion or
authorize Live trading.

### Post-sale Discord notification adapter (staged)

The staged `t480/m20_discord_trade_notification.py` adapter sends a single
human-readable Discord webhook message only after the fixed M20 runner has
recorded a broker-matched `CLOSED` outcome and its PostgreSQL reconciliation
returns `MATCHED`. It includes side, lots, entry and exit prices, strategy,
close reason, realised AUD P&L, commission, swap, estimated costs, and the
post-close account liquidity snapshot (balance, equity, free/used margin, and
floating P&L). It is deliberately best-effort: a Discord failure cannot block
execution, monitoring, ledger persistence, or reconciliation.

The webhook URL is an ignored T480-local secret in
`m20_demo_listener_service.local.json` and must be an approved
`https://discord.com/api/webhooks/...` URL. Set
`FOREX_M20_DISCORD_NOTIFICATIONS_ENABLED` to `true` and provide
`FOREX_M20_DISCORD_WEBHOOK_URL` only in that T480-local file. Notifications
are disabled by default; enabling and deploying the adapter are separate
operator actions.
No Discord message is evidence of trade completion—the immutable PostgreSQL
outcome and broker reconciliation remain authoritative.
