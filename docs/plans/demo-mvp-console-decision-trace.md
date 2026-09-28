# Demo MVP console sub-ExecPlan — actual decision-event trace

This is a child of `demo-mvp-console-execplan.md`. Its design phase is complete;
Chris authorised implementation on 2026-09-28 under registered M33.5. Its work
record is `docs/plans/demo-mvp-console-decision-trace-work.json`.

## Progress

<!-- forex-work-projection:start task=M33-5-DECISION-TRACE schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=contract-tests state=IN_PROGRESS -->
- [ ] contract-tests — Define atomic event contract and failing focused tests (IN_PROGRESS)
<!-- forex-work-item id=runtime-emitter state=PENDING -->
- [ ] runtime-emitter — Emit atomic redacted phase records from the actual listener (PENDING)
<!-- forex-work-item id=read-surface state=PENDING -->
- [ ] read-surface — Add bounded fixed retrieval and human-readable rendering (PENDING)
<!-- forex-work-item id=verification-review state=PENDING -->
- [ ] verification-review — Run QA checks and independent read-only review (PENDING)
<!-- forex-work-projection:end -->

## Outcome

For every actual M1 listener run, the operator can read an ordered trace such
as the following. Each line originates at the corresponding completed code
phase; it is not inferred by a browser after the fact:

    10:31:05 NZDT | price read | bid 1.23450 | ask 1.23462 | spread 12 points
    10:31:06 NZDT | strategies checked | momentum NO_TRADE; compression BUY; ...
    10:31:06 NZDT | owner/gates | compression selected; cost coverage FEASIBLE
    10:31:06 NZDT | proposal persisted | BUY | planned entry 1.23462 | SL 1.23380 | TP 1.23610
    10:31:06 NZDT | execution result | SUBMITTED or NOT_SUBMITTED, with reason

For `NO_TRADE`, the actual price, strategies, selection/gates and refusal
rationale remain visible; entry/SL/TP display as `NOT PLANNED`.

## Actual-code event contract

`t480/m20_demo_trading_session.py:capture()` writes one structured, redacted
event only after it has actually completed each phase: `QUOTE_READ`,
`INPUTS_VALIDATED`, `STRATEGIES_ASSESSED`, `OWNER_AND_GATES_RESOLVED`,
`PROPOSAL_PERSISTED`, `EXECUTION_RESULT`, and `RECONCILIATION_RESULT`. A safe
failure writes `ASSESSMENT_FAILED` with a classified reason, never exception
text, locals or environment. Events are one canonical, atomically published,
no-overwrite record per `(run_id, sequence)` in a versioned T480-local spool
owned by the fixed listener release. JSON-lines files are prohibited because a
crash or concurrent write can create a partial/interleaved apparent trace.

Every event has `event_id`, strict numeric `sequence`, `run_id`, listener
release ID, configuration fingerprint, capture time, type, and one allowlisted
redacted facts object. It adds `proposal_id`, `snapshot_id` and `decision_key`
as soon as the runtime creates them. The allowlist names bid, ask, spread,
closed-candle reference, freshness, strategy signal/reason, selection, gate
status, final action/rationale, planned entry/SL/TP/size/cost and actual
execution/reconciliation result. A planned price is always labelled `planned`;
a fill can only use broker execution facts.

The terminal `RUN_COMPLETE` or `RUN_INCOMPLETE` record binds the ordered event
IDs and their hashes to the existing immutable completed-assessment record and
its proposal/snapshot identities. A crash, writer error, missing sequence,
retention failure or absent final binding is `TRACE_INCOMPLETE` or
`TRACE_UNAVAILABLE`; it is never repaired from listener status, PostgreSQL or
an inferred calculation. The renderer shows that state instead of a seamless
log.

The event writer runs only after the existing real action for that phase. It is
best-effort: an event-write failure must not change assessment, persistence,
submission, reconciliation, safety gates or broker outcome. The listener
service retains a cursor, trace state and last event ID in status; it must not
fabricate a trace. It has a bounded, observable retention policy that never
rewrites/deletes source events needed by an incomplete or current trace and
fails visibly before disk pressure can affect the listener.

The service currently captures one final JSON result from runner stdout, so
stdout cannot be used for streaming events. Scraping stdout is prohibited. A
fixed, read-only retrieval operation returns a bounded spool tail by cursor or
proposal ID, rejects arbitrary paths, and has no order, MT5-control, SQL or
write capability. The dashboard turns those actual event objects into readable
lines without adding facts.

## Owned implementation paths

`t480/m20_demo_trading_session.py` emits phase events.
`t480/m20_demo_listener_service.py` owns spool lifecycle and status cursor.
`t480/command-catalog.json` and its fixed reader retrieve bounded events.
`scripts/listener_workflow_report.py` creates the read model.
`scripts/m20_listener_dashboard.py` and the future loopback console render it.

This package must not change `_assessment`, `_strategy_assessments`,
`_market_selection`, `_strategy_trade_plan`, risk configuration, submission
order, broker inputs or the trade decision. Any new retained file/location,
schema, catalogue entry or release changes require the parent plan's formal
authorisation and release procedure.

## Acceptance and verification

Use fixtures for BUY, SELL, NO_TRADE, selected-but-cost-blocked,
stale/unavailable source, execution rejection, broker-matched close and an
event-writer failure. Test ordering, phase-to-event correspondence, per-run
identity, redaction, atomic no-overwrite publication, final complete-set binding,
bounded tail retrieval, restart-safe sequence handling and that writer failure
cannot change the runner's normal result. Test an incomplete/missing event set,
retention-pressure warning and that the renderer refuses to fill gaps. Test that a
NO_TRADE has no planned prices, planned values are never called fills, and the
renderer has no order route or side effect.

The real-world acceptance is a fresh listener decision where the actual tail
shows `QUOTE_READ` through its final `NO_TRADE` or execution phase and the final
event identities equal the authoritative status/proposal. It does not require
or authorise a trade.

## Demo trading continuity

`CONTINUE`: events are explanatory output from the existing listener, not a
second worker. A missing event tail is visibly unavailable; it does not hold,
restart or otherwise affect Demo trading.

## Design progress and decisions

- [x] Defined actual listener-emitted events for price → strategy checks →
  decision → planned trade/execution result.
- [x] Selected atomic immutable local event records because the actual service
  reserves stdout for its one final JSON result and a JSON-lines stream cannot
  prove atomic, ordered publication.
- [x] Astra review: require complete-set/hash binding, an allowlisted schema,
  explicit incomplete state and bounded retention before implementation.
- [x] Chris explicitly authorised implementation under registered M33.5.
