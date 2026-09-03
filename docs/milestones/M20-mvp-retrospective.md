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

## Remaining M20 work

- Capture and independently verify current real-world proof.
- Demonstrate a bounded eligible Demo execution and its monitored P&L outcome.
- Obtain the current Triad-plus-domain recommendation required by the M20
  contract. Do not mark M20 complete until its declared proof gates pass.

## Repository image assets

- `docs/assets/m1-breakout-risk-reward.png`
- `docs/assets/m1-candidate-strategies.png`
