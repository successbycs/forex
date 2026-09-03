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

- MT5 History confirms that the executor has completed Demo trades. The
  reconciliation defect was isolated to an invalid mixed-overload
  `history_deals_get` call: it supplied a date range and `position` together,
  which can return unrelated accounting rows. The fixed runner queries the
  position-history overload by position identifier only before it writes a
  matched outcome and realised AUD P&L.

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

### Deferred fix list — do not execute overnight

1. Complete a controlled T480 deployment of the corrected MT5 position-history
   lookup, then verify it against one newly closed Demo position before any
   ledger outcome is claimed.
2. Harden the immutable-release staging procedure so a runner source change
   cannot make the final fixed transport fragment exceed the T480 command-size
   limit. Re-stage and hash-verify all three release payloads before activation.
3. Design a narrow, broker-backed reconciliation repair for the four already
   closed Demo positions visible in MT5 History. Do not alter immutable rows or
   infer P&L from screenshots; use the broker records and append-only outcome
   path only.
4. Re-check the trade-lifecycle dashboard against the corrected reconciliation
   data. It must show `MONITORING` only while T480 reports an owned open
   position, and `SOLD / VERIFIED` with realised AUD P&L only after a matched
   outcome exists.
5. Investigate why completed MT5 History rows do not yet create PostgreSQL
   realised P&L outcomes. `Pending` is correct for an actively monitored open
   trade; it is a defect for a completed broker trade once reconciliation has
   had its bounded retry opportunity. Retain the broker-derived entry, exit,
   fees, and realised AUD P&L rather than copying values from a screen.
   Update the trade-ledger terminal table to include a dedicated `Exit` price
   column for every verified closed trade, rather than placing that value only
   in the explanatory line below the row.
6. Finish the separate Markdown-table readability sweep without changing
   operating rules or evidence claims.
7. Design and test a later multi-position Demo rule set before changing the
   current one-position cap. It must define: a total portfolio loss limit
   (not merely a per-trade limit); maximum concurrent positions and maximum
   same-direction EURUSD exposure; duplicate-signal and cooldown rules;
   strategy ownership for each position; independent SL/TP, monitoring, and
   P&L reconciliation; and an explicit rule that one strategy's SELL signal
   cannot close every other strategy's position. Keep the one-position rule
   enabled until that work is approved and proven on Demo.
8. Make listener assessment counts durable across a Scheduled Task restart,
   or display both the current-process count and a persisted total clearly.
   Investigate why a saved open-position protection record can coexist with an
   `IDLE` monitor result after restart; the dashboard must distinguish a
   confirmed broker-open position from stale local monitor state.
9. Correct the terminal classification rule: `SOLD / VERIFIED` may appear
   only when the entry and exit deal share the exact MT5 position identifier,
   the exit price is from that closing deal, and realised AUD P&L excludes all
   balance/deposit records. Otherwise display `RECONCILIATION ERROR`, retain
   the raw diagnostic, and never present the amount as trading profit.
10. Diagnose the newly observed rejected BUY attempts. For every rejection,
    persist and display the exact MT5 return code and broker message, proposal
    time, requested price/volume, current bid/ask and spread, and whether the
    position cap or proposal expiry was involved. Treat a rejection as a
    terminal non-trade: do not retry it blindly or count it as a completed
    strategy result.

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
