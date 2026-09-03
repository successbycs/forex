# M20 MVP retrospective — implementation checkpoint

This is a retrospective checkpoint, not evidence, approval, or a claim that
M20 is complete. `project_state.json` and the M20 contract remain authoritative.

## Implemented

- Windows Scheduled Task `Forex-M20-Demo-Listener` keeps the T480 listener
  alive across logons.
- It assesses fresh `GOMarketsMU-Demo` EURUSD pricing and completed M1 candles
  every ten seconds without retaining a raw tick stream.
- Each result is a `BUY`, `SELL`, or `NO_TRADE` proposal using the existing
  PostgreSQL audit/reconciliation route. Reconciled `NO_TRADE` outcomes are
  expected when the breakout rule is not met.
- Listener status shows the five-candle range, last-two-candle direction,
  breakout checks, combined move, and spread comparison.
- The T16 VS Code dashboard is read-only:

  ```bash
  python3 scripts/m20_listener_dashboard.py
  ```

## Lessons

1. Fresh price can be inspected every ten seconds while the signal remains
   based on completed candles.
2. A `NO_TRADE` conclusion needs explicit failure metrics to be useful.
3. A permanent process needs a heartbeat, counter, next-run time, and latest
   redacted result to be operationally observable.
4. The recorded rejected attempts need diagnosis before they can be treated as
   strategy outcomes. The current read-only ledger query found seven explicit
   `REJECTED` events, all for `SELL` at `0.01` volume, with MT5 return code
   `10027` (client-terminal autotrading disabled). The eighth attempt has an
   immutable `OPENED` event and durable open-position projection, so it is an
   `OPEN_MONITORING` position rather than an unexplained rejection.
5. The current audit summary has 193 proposals/snapshots, eight attempts, and
   eight events, but no closed outcomes. M20.8 must recover/reconcile that
   open position through a terminal `CLOSED` event and immutable Demo P&L,
   fees, and realised-cost outcome before those fields can be proven.

## Remaining M20 work

- M20.9: the listener is deployed to a hash-checked, versioned ProgramData
  release with a rollback-capable task switch. It still needs current
  five-strategy live-assessment evidence after an active bounded Demo lease.
- M20.7: verify the permanent-listener and read-only-observability artifacts
  against the current M20 contract.
- M20.8: preserve the seven confirmed MT5 `10027` rejection diagnoses and
  recover the one `OPEN_MONITORING` position to a terminal immutable outcome.
- Capture and independently verify current real-world proof.
- Demonstrate a bounded eligible Demo execution and its monitored P&L outcome.
- Obtain the current Triad-plus-domain recommendation required by the M20
  contract. Do not mark M20 complete until its declared proof gates pass.

## Repository image assets

- `docs/assets/m1-breakout-risk-reward.png`
- `docs/assets/m1-candidate-strategies.png`
