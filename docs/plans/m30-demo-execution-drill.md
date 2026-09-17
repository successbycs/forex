# M30 Demo execution drill

## Purpose

This one-shot diagnostic answers a narrow operational question: can the exact
deployed T480 terminal submit and close a protected minimum-volume EURUSD order
on the bound Demo account? It exists because a natural M1 strategy signal can
be absent for hours, which makes it unsuitable as the only way to diagnose
terminal-to-broker wiring.

## Boundary

The fixed `m30_demo_execution_drill` adapter operation accepts no inputs. It
requires a running monitor task and a short fixed broker-path lock. The
listener remains running and continues its heartbeat and position monitor; it
only declines new listener entries while the drill owns that path. It also
requires the local
`M1_EURUSD_DEMO` account profile, `GOMarketsMU-Demo`, AUD, EURUSD, a fresh
quote, AutoTrading/API/account permission, a flat EURUSD book, and exactly
0.01 broker minimum volume. It opens a BUY with an AUD 1 maximum protective
stop, closes it immediately, and returns the broker-derived deal history.

The drill writes a local submitted/completed marker before the broker call, so
it cannot be repeated after an order request. It cannot access Live, choose a
symbol, choose a side/size, alter a strategy or risk policy, modify an existing
position, or become a natural M30 lifecycle proof. A terminal refusal creates
no marker and is visible as a refusal result.

## Execution and acceptance

From the repository root, run focused tests, governance validation, deploy the
hash-bound runner release and invoke:

    python3 scripts/t480_adapter.py execute --operation m30_demo_execution_drill

Success returns `FOREX_M30_DEMO_EXECUTION_DRILL_OK`, an open order reference,
a close order reference, a closed position ticket, and broker history. A
disabled terminal returns `FOREX_M30_DEMO_EXECUTION_DRILL_REFUSED` without an
order. Either result is diagnostic evidence only. The broker-path lock clears
automatically after a pre-submission refusal or completed terminal outcome.

## Decision log

- 2026-09-17: Chris authorised this narrow diagnostic after the visible MT5
  account showed no current trading. Natural strategy execution remains the
  only M30 proof surface.
