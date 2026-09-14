# Retained M1 annotation service

These source units are templates. Substitute absolute plain local paths and
validate with `systemd-analyze --user verify` before linking them into the
authorised orchestrator's user manager. Machine-local units belong under
ignored `runs/local/`, not tracked configuration. No transport credentials or
Windows environment are required: this service reads existing local files only.

The one-shot wrapper `scripts/m1_event_service.py` reads canonical
`config/m1_event_annotations.json`, processes each explicitly configured,
bounded one-level retained assessment root, and saves a run-start marker before
invoking the batches. The second root is the read-only current-assessment export
store; roots are independently validated and their counts/records are combined
only after each batch validates.
The final immutable report binds that marker, actual start/completion times,
policy bytes and per-input results. A missing final report means an unfinished
run, not success. Filesystem locking prevents overlapping batches using the
same reports directory. Sidecar publication remains idempotent and immutable.

The policy selects each proposal decision's UTC calendar day, from midnight
through `23:59:59.999999Z` because annotation bounds are inclusive. This is an
observational review window, not an eligibility rule. Event availability still
uses the actual decision cutoff, not the day end or service execution time.

The timer runs hourly at ten minutes past, without missed-run catch-up. The
15-minute watchdog bounds a service invocation; it is not a guarantee that an
unbounded growing archive fits. If it interrupts a run, already-published
sidecars and the start record remain. Investigate repeated unfinished runs
and improve incremental processing before enlarging workload. No raw history
is deleted and no failed input blocks unrelated valid files.

Deployment scope: independent W2 annotation/reporting on Piwakawaka, covered
by the owner's existing component deployment instruction. This does not add a
T480 service, read a broker, modify the M1 listener/strategy/risk configuration,
enable trade vetoes or satisfy the active M29 market-recovery contract. No
milestone proof or human sign-off is inferred from technical tests or review.
The host and user manager must remain running for timers to execute.

Status: independent pre-activation review passed. Reviewed local units were
linked into Piwakawaka's user manager on September 12. The first service run
at 03:35:50.813Z completed successfully, reporting 20 inputs, five attached
and 15 refused. Its report digest is
`sha256:dbd7a37f4024a53b54277a2e5bad8bb7820b07cabea6361434f50de590a9224c`.
The timer is enabled/active, with the first scheduled trigger reported at
16:10 NZST. Run starts/finals are retained under ignored
`runs/local/m1-event-reports`. This establishes one successful service pass
and current timer configuration, not sustained recurring reliability.
