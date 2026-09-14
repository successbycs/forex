# M1 event annotations

M1 economic-event context is a separate post-decision observation record.
It does not modify the retained assessment, proposal, order, risk controls,
listener or news eligibility gate. Missing context does not veto a trade and
does not mean the calendar was clear.

`src/forex/m1_event_sidecar.py` accepts one full retained assessment and a
supplied event-context report. It checks the deployed snapshot shape, actual
snapshot body digest, proposal linkage and observation/capture/decision
chronology. It recomputes annotation consistency for explicitly declared
review-window bounds and produces a hash-bound `EVENT_CONTEXT_ONLY` sidecar
with `execution_authority: false`. It does not run or reselect a strategy.

The pure helper is not an authenticity verifier: its source and journal hashes
are caller-supplied. The local command must compute the source digest from
actual bytes and obtain context through the existing verified capture-store
reader. Lifecycle/lineage exports without full snapshot/proposal bodies are
not eligible; missing fields must never be reconstructed from trade history.

The review window is explicit and observational, not a blackout default.
Qualification uses the retained proposal's decision time. Even events dated
earlier than the trade are unavailable to that decision if first captured
later. Quarantines and unknown coverage remain visible.

Observed local check: the retained assessment in
`runs/evidence/M20/20260911T065015Z/demo-trading-operation.json` has decision
time `2026-09-11T06:50:39Z`. The current BLS store first captured its four
records on September 12. For the explicitly selected September 11 UTC review
day, all four records are excluded as lookahead, accepted events are empty,
and coverage remains UNKNOWN. This is a valid missing-context observation,
not proof that no events occurred or a retrospective trading recommendation.

The full sidecar command correctly refuses that earlier assessment: its
snapshot capture is `06:50:40Z`, one second after the recorded decision.
The standalone event-context observation above remains a cutoff query, not
proof that the assessment has valid chronology. Historical bytes are unchanged.

## Local command

```sh
python3 scripts/m1_event_sidecar.py \
  --assessment runs/evidence/M20/20260911T094157Z/demo-trading-operation.json \
  --store runs/local/bls-event-store \
  --window-start 2026-09-11T00:00:00Z \
  --window-end 2026-09-12T00:00:00Z \
  --output runs/local/m1-event-sidecars
```

The output directory must already exist and be trusted/non-symlink, including
its ancestors. The command reads only local inputs, computes the assessment
byte digest, invokes the fixed verified-store event-context command, and
publishes a content-addressed sidecar with exclusive creation and filesystem
synchronization. Exact repeats return `EXISTING`; conflicting bytes refuse.
No input evidence is overwritten. Explicit windows are required.

The example above succeeded on the actual retained later assessment, producing
`sha256:6cef49ab88149583110063fd515e66a8fdaf7d5dab2e81e975ec11b4bed35b5b`.
An immediate repeat returned `EXISTING`. Events first captured on September 12
remain unavailable to this September 11 decision; coverage remains UNKNOWN.
This demonstrates local annotation/persistence, not new trading execution or
the profitability of any strategy. No attachment is written into the M1
trading database or used by its execution path. Automated discovery/report
joining is available through the commands below. Recurring local annotation
processing is now activated as described in [deployment](../deploy/m1-events/README.md).

The deployed service supplies two explicitly trusted roots: the historical M20
evidence root and the current-assessment exporter root. Its first dual-root
pass at 04:11:00.642Z on September 12 retained the existing 20 historical
inputs (five attached, 15 refused) and no current input because the released
listener was waiting for a fresh quote. The immutable report names both roots;
an empty current root is neither a healthy-calendar assertion nor a no-trade.

## Batch discovery and replay joins

`scripts/m1_event_batch.py` takes `--assessment-root`, `--store`, `--output`,
`--window-start` and `--window-end`. It discovers only direct
`<assessment-root>/<child>/demo-trading-operation.json` files, in sorted order,
not arbitrary recursively discovered files. It reads each source once for its
hash and annotation, retains valid sidecars, and reports every discovered
candidate as ATTACHED or INPUT_REFUSED. A bad source or local context timeout
does not stop independent files. Empty discovery reports NO_INPUTS.
COMPLETE means the batch loop finished, not that every input passed or any
milestone is complete. The report is stdout-only; source bytes stay unchanged.

An actual pass over `runs/evidence/M20`, using the September 11 UTC day as an
explicit observation window, discovered 20 candidates: five attached and 15
refused. Four sidecars were newly created and one reused. Refusals retain source
hashes and bounded reason codes, including clock-order, schema, digest, malformed
operation output and other validation failures. This is not a count of wins,
losses or trades. Valid annotations still have unknown calendar coverage.
Independent read-only verification reconciled all 20 inputs: seven unsupported
snapshot schemas, four non-JSON operation outputs and four invalid timestamp
sequences account for the 15 refusals. All five valid sidecars rebuilt exactly;
each contains zero accepted events and four unavailable-at-decision quarantines.

The read-only replay command accepts optional `--event-store`,
`--event-sidecars`, `--event-window-start` and `--event-window-end` together
with `--retained-export`. It independently rebuilds context from the verified
store and looks for the exact matching saved sidecar. Results are ATTACHED,
MISSING, INVALID or UNAVAILABLE, separately from replay and cost results.
It does not create sidecars. The assessment is read once for both report and
source binding. Later calendar captures can change the current journal digest,
requiring a newly matching sidecar; old immutable sidecars remain untouched.

Actual joining for `20260911T094157Z` returned ATTACHED. Independent review
confirmed removing the optional annotation leaves the underlying replay report
identical. Local context timeout likewise reports UNAVAILABLE without turning
an optional annotation into a trading or reporting veto.

The scheduled wrapper uses the canonical `DECISION_UTC_DAY` observation policy:
each proposal's UTC day through `23:59:59.999999Z`, not the day the service runs.
This differs from manual windows ending exactly at the following midnight;
window-specific sidecars coexist immutably. Its hourly timer runs at ten past
on the local orchestrator. It only discovers already-retained full assessment
files—it does not guarantee that every new M1 decision has been exported.
Continuous full-assessment export coverage remains a distinct integration
requirement, and raw-source gaps are not repaired by annotation automation.

## Released latest-assessment export integration

The released listener contains a deliberately bounded bridge toward that
requirement. It atomically replaces one local
`m20_demo_latest_assessment.local.json` record after a successful assessment.
The record contains the full non-secret decision snapshot and its proposal,
but not the PostgreSQL audit object; it is replacement state rather than a
second evidence archive. `m20_listener_latest_assessment` is a fixed,
read-only T480 adapter operation that exports this one record only after
checking its active release ID, current configuration fingerprint,
`GOMarketsMU-Demo` server and `EURUSD` symbol. It returns either an explicit
absence observation or a SHA-256-bound export; it cannot trigger assessment,
restart the listener or submit an order.

`scripts/m20_replay_report.py --retained-export` accepts the resulting fixed
operation envelope and retains its release/timing/hash provenance. An absent
record is not transformed into a no-trade result. The separate read-only
Piwakawaka exporter timer is active every two minutes and currently observes
`LATEST_ASSESSMENT_ABSENT` while the market is closed, so the enabled annotation
timer still operates only on already-retained historical assessment files.

It is not gap-free continuous coverage: any assessment overwritten before an
exporter reads this one-record source is explicitly unretained. The released
listener now puts a monotonic assessment sequence in each source record, and
the local exporter cursor records BASELINE_UNVERIFIED, CONTIGUOUS, DUPLICATE or
GAP_OBSERVED receipts with the exact missed sequence count. That makes sampling
loss auditable; it does not turn sampling into complete per-assessment coverage.
A future acknowledged spool would still be required to retain every assessment.
