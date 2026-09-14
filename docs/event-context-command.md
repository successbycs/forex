# Retained economic-event context

Run from any working directory using the script's absolute path, or from the
repository using:

```bash
python3 scripts/event_context.py --input /path/to/retained-events.json \
  --decision-at 2026-09-14T00:00:00Z \
  --window-start 2026-09-14T00:00:00Z \
  --window-end 2026-09-15T00:00:00Z
```

The input is a JSON array of event metadata objects accepted by
`forex.event_quality.qualify_events`. Each record identifies its event,
source URL, source identifier, licence, revision, availability time, status
and schedule precision. Exact local schedules additionally supply
`scheduled_at_local` and an IANA `timezone`; ambiguous clocks require an
explicit fold. Date-only records remain quarantined.

The command prints one JSON report with the original file's byte-level
SHA-256, qualification results and a decision-time annotation. It preserves
quarantine reasons and reports calendar coverage as unknown. The command
does not alter the input. Malformed input returns exit code 2 with a reason
on stderr and no report on stdout.

This integrates the existing qualification and annotation functions for
retained-data research and reporting. Source authenticity, licence
qualification, publisher collection and complete calendar coverage require
their own evidence; a source URL or supplied availability field does not
prove them. The command has no broker connection or order influence.

Deployment status: runnable in the repository's Python environment. Remote
service installation and attachment to M1/H_SLOW operating records remain
integration work. CLI fixture tests are implementation checks only.

## Retaining BLS captures

The collection boundary can pass an original BLS family-schedule response to:

```bash
python3 scripts/bls_capture.py /path/to/original-response.html \
  --store /path/to/machine-local/event-captures \
  --capture-id cpi-20260914T010000Z --family CPI \
  --capture-completed-at 2026-09-14T01:00:00Z
```

For the monthly list, replace `--family CPI` with
`--monthly-url https://www.bls.gov/schedule/2026/09_sched_list.htm` and supply
that page's retained original bytes. Only CPI and Employment Situation rows
are selected. The exact visible Eastern-time declaration is required for
precise timestamps; a newer target with missing/TBD time remains a date-only
revision and cannot resurrect an older precise schedule. Store reads and
`--resume` use the same source-specific parser and URL binding.

The store path is an explicit machine-local value; do not put retained captures
or machine-specific paths into tracked configuration. The command does not
download data. The supplying collector must retain the actual source URL and
acquisition timing; a supplied filename or timestamp is not authentication.
The result reports raw-byte and journal digests, counts, parser quarantine,
unknown calendar coverage and no execution authority. Unknown page layouts
are preserved as quarantined observations, never a healthy empty calendar.

The current store uses POSIX advisory locking on a trusted local filesystem.
It publishes exclusive raw files, metadata and immutable journal generations;
it does not protect against a malicious local owner replacing directories.
Malformed encoding is refused and the caller's original input stays unchanged.
A crash after raw and metadata publication can be reconstructed on read;
incomplete raw-only publication reports a recovery requirement. A late/equal
capture that would rewrite published history is retained but reports a recovery
requirement rather than changing earlier revisions. Such failures must not be
reported by a future scheduler as successful current coverage.

For an interrupted capture, repeat the same command and retained input with
`--resume`. Recovery requires existing identical raw bytes. If metadata exists,
its family and timestamp must also match; if metadata was never published,
those fields remain explicitly caller-declared and cannot authenticate the
lost request. Only missing metadata and journal generations are published.
Repeating an already completed request with `--resume` is idempotent. A missing
raw capture is refused without creating a new store. Unrelated corrupt or late
capture state remains an explicit error, not something resume bypasses.

Publication now flushes a hidden staging file before atomically linking its
final name without replacement. Interrupted staging files remain under
`.pending-*` and are not consumed as finished captures. Complete published
artifacts are never overwritten. Directory-sync failures are reported, not
treated as successful durable writes. Failure-injection tests are not a claim
of verified physical power-loss durability.

This command prepares the local storage boundary for scheduled collection.
It does not install a scheduler, attach context to orders or prove an official
publisher was contacted. Source qualification and deployed collection remain
separate work.

Read the verified store through the same annotation path:

```bash
python3 scripts/event_context.py --store /path/to/machine-local/event-captures \
  --decision-at 2026-09-14T02:00:00Z \
  --window-start 2026-09-14T02:00:00Z --window-end 2026-09-15T02:00:00Z
```

This read-only mode verifies the stored capture lineage and reports its journal
digest separately from a raw input-file digest. Qualification remains as-of
the decision cutoff. Parser quarantine is reported only for captures available
by that cutoff; future revisions cannot supply an earlier event schedule.

## Isolating an already-retained late capture

When a valid raw/metadata pair arrived too late to append without rewriting a
published journal, explicitly isolate that capture:

```bash
python3 scripts/bls_isolate_capture.py \
  --store /path/to/machine-local/event-captures --capture-id late-capture-id
```

This publishes a separate immutable quarantine marker bound to the exact
capture metadata and an existing journal generation. It does not delete,
rewrite or backdate raw bytes, metadata, events or published journal history.
Already-published captures and captures that are not late are ineligible.
Unmarked late data still raises a recovery error; corrupt data is not silently
excluded. After valid isolation, later valid captures can append normally.

`event_context.py --store` reports `store_isolated_captures` with
`store_health_scope: CURRENT_RETAINED_STATE_NOT_DECISION_TIME`. This is current
storage-health information, not a claim that the quarantine was known at the
historical decision cutoff. It does not enter the strategy annotation, clear
calendar coverage, or grant order authority. Original late responses remain
available for inspection; their revisions are not applied to the journal.
