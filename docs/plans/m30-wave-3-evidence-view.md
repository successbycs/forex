# M30 Wave 3 — bounded read-only M1 evidence view

This narrow MVP task adds one terminal view of the newest retained M1
assessment. It reads only the fixed `m20_listener_latest_assessment` adapter
operation and the fixed PostgreSQL lifecycle-summary query. It neither starts
an assessment nor has any broker, listener, scheduler, configuration, or
database-write authority.

The view lists the closed-candle timestamp, each of the five recorded signals,
the selected owner, refusal reason, proposal and attempt fields. Lifecycle,
actual costs and outcome are joined only by an exact proposal id. Missing,
ambiguous, or unavailable information is displayed as `UNKNOWN`; terminal
`NO_TRADE` has no execution lifecycle and explicitly displays costs as not
applicable.

## Progress

<!-- forex-work-projection:start task=M30-WAVE-3-EVIDENCE-VIEW schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=bounded-view state=DONE -->
- [x] bounded-view — Render the latest retained M1 assessment with all five signals and terminal decision fields (DONE)
<!-- forex-work-item id=exact-lifecycle-join state=DONE -->
- [x] exact-lifecycle-join — Display lifecycle, actual outcome, costs and unresolved join state only when proposal identity matches exactly (DONE)
<!-- forex-work-item id=verification state=DONE -->
- [x] verification — Run focused tests and an actual read-only observation (DONE)
<!-- forex-work-item id=independent-review state=DONE -->
- [x] independent-review — Obtain independent read-only review of the view and evidence (DONE)
<!-- forex-work-projection:end -->

## Owned paths

- `scripts/m20_listener_evidence_view.py`
- `tests/test_m20_listener_evidence_view.py`
- this plan, work record, and hybrid-plan progress lines

## Acceptance and validation

Run the focused evidence-view and existing dashboard tests, the work-projection
checker, and one actual `--once` read-only observation. Inspect that the
operation returns a terminal M1 decision and that no order is submitted by the
view. An independent read-only review is required before Wave 3 is recorded as
complete. Deployment is not required because this tool reads existing deployed
surfaces locally.
