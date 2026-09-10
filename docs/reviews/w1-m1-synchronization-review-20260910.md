# Wave 1 M1 synchronization repair review

Status: **ENTRY_RELEASE_ALLOWED** for ordinary Demo assessments and only trades
that independently pass all existing runtime prerequisites.

The operator requested Terra implementation and Astra read-only review. Separate
Terra agents implemented and tested the repair; the Astra reviewer inspected the
source without editing it or operating the broker. This is scoped agent review
within one workspace, not an external witness or the M20 Triad completion gate.

## Reviewed behavior

- Capture samples current UTC after blocking candle/context reads. Missing or
  malformed M1 produces an explicit non-actionable assessment without invented
  candles. A valid contiguous window must end at the current minute boundary.
- After reservation, submission rechecks quote age, UTC minute, contiguous M1
  and the original candle digest. A new minute or revised history requires a
  new assessment; newly retrieved bars cannot authorize an old proposal.
- A never-sent reservation receives a `NOT_SUBMITTED` event and terminal
  reconciliation. Migration 023 permits that event without changing existing
  records. Attempt locking rejects contradictory event sequences. The attempt
  still counts toward cumulative notional conservatively.
- Reversal exits require fresh quotes and synchronized candles. Owner time
  exits run before candle checks; broker SL/TP is retained. Missing intervals,
  including market closures, are not filled: the strategy waits for a complete
  contiguous window rather than inferring a broker holiday calendar.

## Source review identity

Astra identified no blocking runtime defect in these implementation hashes:

| File | SHA-256 |
| --- | --- |
| `t480/m20_demo_trading_session.py` | `25f11e190d0523fb2e66569277d22ac5c8e80d198d70372af5f4ab56ee0b618e` |
| `t480/m20_postgres_audit_bridge.py` | `3e02c0d5d38de6509bfc7dc768eb40eec8ca8a3b5856010c9a002edb44f51e9a` |
| `sql/migrations/023_m20_not_submitted_execution_state.sql` | `c61751ce9699caa80c41e24a9b21f29e566650f909fde6ad64d448043b6343e8` |

The verifier was additionally corrected to reject an outcome attached to a
never-submitted attempt. Its final SHA-256 is
`8b78962b8f2a112fcdd11271e9acb4c936f63c886eca8f65c684f3b8e103e6df`.
Implementation commit: `01c7546369e48912f36fa4f72cc25e1b156b97af`.

## Evidence and limits

Raw operating observations and staged release evidence:
`runs/evidence/M20/w1-m1-final-20260910/raw/`.
Engineering tests and separate offline verification:
`runs/verification/M20/w1-m1-final-20260910/`.

Initial passing tests were insufficient: one stubbed the freshness validator,
and a reversal test used pre-entry candles that the old implementation already
rejected. The final tests correct those gaps: real validators run inside
`capture()` with controlled clock changes, blocking history reads, digest drift
and a valid same-minute control reaching `order_send`. Stale post-entry reversal
candles are suppressed while fresh controls close; owner time exits precede
candle reads. Real isolated PostgreSQL tests exercise migration 023, durable
non-submission reconciliation and both forbidden event orderings. Astra
inspected the corrected tests and issued SOURCE+TEST PASS, with 102 targeted
tests passing. Full repository verification also passed with isolated PostgreSQL
enabled, rather than skipping its persistence cases.
Neither tests nor a held deployment prove profitability, genuine lifecycle,
broker fees, protected-position restart, or Wave 1/M20 completion.

## Final deployed-evidence review

Astra reviewed release `97d2bf75679b5ee4`, bound to the source above, and the
hash-verified application of migration 023. The raw evidence inventory matched;
held deployment verification passed. The Demo account was AVAILABLE/flat at
AUD 100994.79, unresolved attempts were empty, and risk anchors were unchanged.
Current M1 availability and fresh quotes were observed; M19 remains PROVEN.

Disposition: **ENTRY_RELEASE_ALLOWED**. Before 06:00 UTC the financing gate
must refuse entries. Later submissions still require current synchronized M1,
fresh quotes, the existing lease, Option B, qualified temporary financing and an
ordinary eligible strategy signal. Preserve the 17 September expiry. The
reviewer performed no deployment or hold operation. This resolves the reviewed
M1 blocker only; it is not a Triad or milestone-completion recommendation.
