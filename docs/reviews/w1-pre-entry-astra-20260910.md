# Astra pre-entry review — 10 September 2026

Final disposition: **BLOCK_ENTRY — stale M1 history accepted by the entry gate.**
The initial scoped review found no critical defect in the temporary financing
delta. A bounded ordinary assessment immediately after hold release exposed
the existing freshness defect below; that observation supersedes the initial
entry disposition. Maintenance hold was restored immediately.
This turn reviewed source read-only: no implementation changes were made.
This is a scoped review in the same assistant thread, not an external witness,
independent author identity, Triad recommendation or milestone completion.

Reviewed `352ee84` and `d681d05`; source-derived release
`2329eea2d53bba6d`; governed fingerprint
`sha256:16abde21dc56729b2418f9c48d7091362a3c7622f976e3bb36e49f8492e0fb67`.
Later documentation-only commits do not change these payload bytes.

## Findings

- The temporary policy tests the entire maximum owner horizon against a
  weekday window and dated validity. A horizon reaching 18:00 is refused;
  expiry, missing source, stale conversion, invalid mode and wider hours fail
  closed. It preserves the ten-minute maximum horizon and existing exits.
- AUD 6/lot is an explicitly authorised public-tariff **estimate**, not a
  verified account agreement. The calculator returns DEMO_ESTIMATE; holding
  review rejects this as overnight evidence. No positive credit increases risk.
- `_planned_stop_loss` includes the commission allowance, adverse financing,
  valid technical-stop distance and existing slippage allowance. The fixed
  strategy planner refuses an infeasible minimum lot rather than tightening
  its technical stop. Fresh financing is checked again before reservation.
- The reservation transaction retains fresh account-bound risk checks,
  cumulative notional, global one-position exclusion and proposal idempotency.
  The new status does not waive those gates. Actual outcome accounting sums
  signed broker profit, commission, fees and swap; it does not subtract the
  estimated allowance again.
- Existing failed/partial close handling preserves unresolved exposure and
  protection. The new window is not a guaranteed close during a broker/host
  failure; accidental financing needs actual reconciliation. No overnight or
  profitability qualification is claimed.
- M19 remains PROVEN. Current fixed queries show empty unresolved attempts,
  AVAILABLE/zero broker positions, and no risk pause or pending cash-flow
  approval. No risk reset or lease replacement is needed.

## Evidence and limits

Current raw inspections and focused test output are retained under
`runs/evidence/M20/w1-pre-entry-20260910/raw/`. Existing deployment verification
under `runs/verification/M20/w1-broker-resolution-20260910/` confirms the held
release, its effective policy and unchanged risk anchors. These do not prove
an in-window trade, protected restart or future availability.

No additional operator account questionnaire is an entry prerequisite for this
approved temporary policy. Collect genuine lifecycle, actual costs and protected
restart after ordinary entry eligibility. Final proof must bind its actual
application revision; the generic capture command currently expects HEAD while
the deployed code is bound to d681d05. That capture-binding limitation is a
closeout task, not permission to mislabel evidence or repeatedly redeploy for
documentation commits. Unrelated untracked `home/` remains untouched.

Operational action under the user's explicit authority: remove maintenance
hold after the current prechecks; let the listener assess normally. Before
06:00 UTC it must remain NO_TRADE even when other entry rules are satisfied.
Never force a signal or wait in an AI polling loop for the session to open.

## Blocking runtime finding: M1 age is not checked

At quote/decision time 2026-09-10 03:44:48 UTC, the ordinary assessment's
latest M1 close was 01:12:00 UTC: **9,168 seconds old**. The assessment was
NO_TRADE/NOT_SUBMITTED and NO_TRADE_RECONCILED; it did not submit an order.
Source `capture()` uses `len(raw_bars['M1']) >= 12` for `completed_m1`.
`_bar_rows()` rejects future/incomplete, malformed and unordered bars but sets
no maximum age. Thus a fresh quote plus a sufficiently long stale history can
reach selection during the entry window. The financing window would not
protect against this once the clock reaches 06:00 UTC.

Raw observation: `listener-after-release.json` in the review raw directory.
The separate synthetic parser reproduction accepted 64 rows with the newest
close 6,960 seconds before the quote boundary; the existing completed_m1 gate
was true. This is labelled engineering evidence, not fabricated broker data.

Terra repair required before release:

1. Diagnose stale M1 terminal history from the retained broker diagnostics.
   Do not reinterpret stale history as a market signal or repeatedly restart
   a healthy host. Preserve existing ledger, lease and risk anchors.
2. Add an explicit canonical M1 freshness/continuity requirement for the
   strategy input window; check it against observed/capture UTC and before
   submission. Insufficient, stale, duplicate, out-of-order or future inputs
   must produce a recorded non-actionable outcome. Distinguish missing market
   intervals from legitimate closures; do not fabricate gap-fill candles.
3. Check the existing reversal monitor separately: stale bars must not trigger
   a reversal exit, while broker SL/TP and wall-clock owner time exits remain
   available. Do not disable protective management with an entry-data gate.
4. Verify actual runtime functions with fresh quote plus stale bars, boundary
   ages, gaps and genuine fresh bars. Deploy under hold, retain a current
   broker capture with fresh M1 history, and obtain affected-area re-review.

This finding is the current blocker, replacing the obsolete broker-account
questionnaire. No source implementation was changed in this review turn.

Follow-up observation at 03:47 UTC shows the last completed assessment at
03:45:18 used an M1 close of 03:45:00: history caught up without a terminal
restart. This narrows the operational diagnosis to transient synchronization,
not a confirmed persistent history outage. Historical error-32 lines remain
diagnostic context, not proof of a current lock. The missing freshness gate
still needs repair for future reconnect/startup episodes. Final account query
is AVAILABLE/flat, balance/equity AUD 100994.79; hold restored, release unchanged.
