# M33 Demo M1 proposal replay repair

This ExecPlan is a living document and follows `PLANS.md`. It repairs one
observed Demo execution-liveness defect without changing the five strategies,
account binding, risk limits, symbol, server, maintenance-hold behaviour, or
Live-trading prohibition.

## Purpose / Big Picture

An eligible EUR/USD Demo BUY or SELL must either create one bounded execution
attempt while its five-minute decision is still valid, or visibly finish as
not submitted. Today an actionable proposal can be written to PostgreSQL and,
if the runner stops before reserving the attempt, every replay returns
`ALREADY_PERSISTED_NO_RESUBMISSION`. The order never reaches MT5.

After this repair, a replayed actionable proposal with no attempt may continue
through the existing reservation and final fresh-input checks only while it is
still valid and its current facts exactly match the immutable persisted
proposal and selection record. A proposal with any attempt remains
non-resubmittable. An expired unattempted proposal is reported as expired and
never sent to MT5. A new closed candle remains independently eligible for a
new proposal.

## Formal milestone dependency map

M32 is proven and remains the reusable prerequisite. M33 is the active
milestone. This is a narrow corrective repair to the existing M1 Demo
execution workflow: it preserves the fixed `GOMarketsMU-Demo` / `EURUSD`
authority rather than granting a new broker route. It does not close M33 or
alter M33-C1 through M33-C8. A governed T480 deployment remains conditional
on focused QA, independent read-only review, release readiness and the fixed
deployment procedure; no Live capability is introduced.

## Demo trading continuity

`CONTINUE`. Local design, tests, review and hash staging do not justify a
hold. The repair may only be deployed through the existing fixed listener
release path. A hold is required only for an independently observed unsafe
runtime condition under the existing governance; this plan cannot create or
release one.

## Design

`t480/m20_demo_trading_session.py:capture()` currently persists a proposal,
then returns immediately for every duplicate. The PostgreSQL uniqueness
constraint already allows at most one `demo_execution_attempt` per proposal.
The runner will therefore read the existing reconciliation first:

- `NO_TRADE`, any existing execution attempt, broker result, open state, or
  uncertain state stays non-resubmittable.
- A `BUY` or `SELL` with no attempt first compares its current action, entry,
  stops, size, decision digest, strategy version, application revision,
  configuration fingerprint, and selection/ownership facts to the immutable
  persisted record. Any difference returns
  `REPLAY_FACT_MISMATCH_NO_RESUBMISSION`. If they match and `expires_at_utc`
  remains valid, it falls through to existing `reserve_execution()` and final
  MT5 permission / M1 freshness checks. The reservation transaction repeats
  those equality and provenance checks before creating an attempt; the unique attempt
  constraint remains the concurrency boundary.
- A `BUY` or `SELL` with no attempt but an expired decision returns an explicit
  `EXPIRED_UNATTEMPTED_NO_RESUBMISSION` result. It never reserves or calls
  `order_send`.

No database migration is required. The repair uses the existing immutable
proposal expiry, reconciliation reader and reservation unique constraint.

## Progress

<!-- forex-work-projection:start task=M33-M1-PROPOSAL-REPLAY-REPAIR schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=defect-contract state=DONE -->
- [x] defect-contract — Specify replay state and failing focused checks (DONE)
<!-- forex-work-item id=implementation state=DONE -->
- [x] implementation — Implement fresh unattempted replay and expired non-submission (DONE)
<!-- forex-work-item id=qa-review state=BLOCKED -->
- [ ] qa-review — Run focused QA and independent read-only review (BLOCKED)
<!-- forex-work-item id=governed-deployment state=PENDING -->
- [ ] governed-deployment — Run readiness, fixed release deployment and fresh listener verification (PENDING)
<!-- forex-work-projection:end -->

## Verification

Run from the repository root:

    python3 -m pytest -q tests/test_t480_adapter.py tests/test_m20_assessment_spool.py tests/test_m20_decision_trace.py -k 'capture or replay or persisted or reservation or trace'
    git diff --check
    python3 scripts/forex_milestones.py validate
    python3 scripts/check_execution_continuation.py --work-plan docs/plans/m33-m1-proposal-replay-repair-work.json

The decisive local test simulates a persisted actionable proposal with no
attempt and proves that exactly one existing reservation path reaches the
order seam. A second test proves an expired proposal never reaches that seam.
The final database proof is intentionally isolated: it requires
`FOREX_W1_TEST_DSN` pointing to a localhost database named `forex_w1_test` on
a nonstandard port. It proves a provenance-mismatched reservation leaves zero
execution attempts. This environment is unavailable in the current WSL
checkout; a broker, shared, or production database must never be substituted.
The real-world deployment check is a fresh listener result with either a
normal bounded execution result or a visible strategy/risk refusal; it must
not claim a trade merely because the listener is running.

## Decision log

- 2026-09-29: The operator trace showed `Decision: BUY` followed by
  `ALREADY_PERSISTED_NO_RESUBMISSION`. Source inspection proved this return
  occurs before `reserve_execution()` and `mt5.order_send()`.
- 2026-09-29: Keep duplicate protection. Do not retry an existing attempt or
  send an expired decision; repair only the missing transition from an
  unattempted fresh proposal to the existing reservation boundary.
- 2026-09-29: Independent review found that a replay must not use facts rebuilt
  from a later capture. The repair therefore refuses a fact mismatch and makes
  the existing reservation transaction independently enforce the same binding.
- 2026-09-29: Second review added release revision and configuration fingerprint
  to the immutable replay binding requirement and requires database-backed
  proof that a mismatch cannot create an attempt.

## Outcomes & Retrospective

Pending implementation, verification, review and governed deployment.
